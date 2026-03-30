# ==============================================================================
# 1. BIBLIOTECAS PADRÃO DO PYTHON
# Ferramentas nativas para manipulação de sistema, data, texto e criptografia.
# ==============================================================================
import os
import re
import json
import base64
import hashlib
import difflib                 # Biblioteca para comparação de textos
import unicodedata
from math import e
from io import BytesIO
from functools import wraps
from datetime import date, datetime, timedelta, timezone

# ==============================================================================
# 2. FRAMEWORK FLASK E EXTENSÕES
# Funcionalidades principais da web, segurança e banco de dados (SQLAlchemy).
# ==============================================================================
from flask import (
    Blueprint, Config, abort, render_template, request, redirect, 
    url_for, flash, session, send_file, current_app, jsonify, make_response
)
from flask_login import UserMixin, current_user
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import extract, func, or_
from sqlalchemy.orm import aliased

# ==============================================================================
# 3. CONFIGURAÇÕES DA APLICAÇÃO
# Importações do objeto de aplicação principal e extensões iniciadas.
# ==============================================================================
from app import db, login_manager

# ==============================================================================
# 4. MODELOS DO BANCO DE DADOS (MODELS)
# Definições das tabelas e objetos do sistema.
# ==============================================================================
from app.models import usuario
from app.models.usuario import Usuario
from app.models.empresa import Empresa
from app.models.lista_opcoes import Clima, MaoObra, Equipamento, TagOcorrencia
from app.models.obra import Frente_Trabalho, Obra
from app.models.rdo import RDO, Assinatura, Equipamentos, RDOMaoObra, Atividades, Fotos, TagsOcorrencias

# ==============================================================================
# 5. UTILITÁRIOS E SERVIÇOS
# Funções auxiliares para geração de PDF, QR Codes e lógica de negócios.
# ==============================================================================
from app.utils.qrcode_utils import gerar_qrcode_b64
from app.utils.rdo_pdf import regenerar_pdf_rdo
from app.utils.pdf_service import render_rdo_pdf, render_rdo_pdf_compact
from app.utils.security_pdf import travar_edicao_pdf

# Tenta importar PyMuPDF para highlighting, caso não tenha, segue sem
try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

# Configuração permitida de extensões
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# ==============================================================================
# 6. CONSTANTES DE PERMISSÃO (RBAC) - DEFINIÇÃO DE PAPÉIS
# ==============================================================================
ROLE_ADMIN = 'Admin'
ROLE_GESTOR = 'Gestor'
ROLE_OPERADOR = 'Operador'
ROLE_LEITOR = 'Leitor'
ROLE_CLIENTE = 'Cliente Obra'

# Grupos de Permissão
# Quem pode escrever dados operacionais (RDO, Equipamentos, etc)
PERM_WRITE_BASIC = [ROLE_ADMIN, ROLE_GESTOR, ROLE_OPERADOR]
# Quem pode gerenciar estrutura (Obras, Usuários)
PERM_MANAGEMENT = [ROLE_ADMIN, ROLE_GESTOR]
# Quem pode apenas visualizar
PERM_VIEW_ONLY = [ROLE_LEITOR, ROLE_CLIENTE]
# Quem pode assinar
PERM_SIGNATURE = [ROLE_ADMIN, ROLE_GESTOR, ROLE_OPERADOR, ROLE_CLIENTE]

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

#######################################################################################################
####################################################################################################### SECURITY DECORATORS
#######################################################################################################

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Você precisa estar logado para acessar esta página.", "warning")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated

def role_required(allowed_roles):
    """
    Decorator para verificar se o usuário tem um dos papéis permitidos.
    Uso: @role_required([ROLE_ADMIN, ROLE_GESTOR])
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if "user_id" not in session:
                return redirect(url_for('auth.login'))
            
            user_role = session.get("user_role")
            
            if user_role not in allowed_roles:
                # Log de segurança (opcional)
                print(f"[SECURITY] Acesso negado. User ID: {session.get('user_id')}, Role: {user_role}, Endpoint: {request.endpoint}")
                flash("Acesso não autorizado para o seu perfil de usuário.", "danger")
                return redirect(url_for('auth.inicio'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Helper para verificação de escopo (Scoping)
def get_user_scope_ids():
    """Retorna lista de IDs de obras permitidas para o usuário atual"""
    user_id = session.get("user_id")
    if not user_id: return []
    user = Usuario.query.get(user_id)
    if user.papel == ROLE_ADMIN:
        return None # None significa "Acesso Total"
    return [obra.id for obra in user.obras_permitidas]

#######################################################################################################
####################################################################################################### Rota Raiz
#######################################################################################################

@auth_bp.get("/")
def index():
    if "user_id" in session:
        return redirect(url_for("auth.inicio"))
    return redirect(url_for("auth.login"))

#######################################################################################################
####################################################################################################### Login e Logout
#######################################################################################################

@auth_bp.get("/login")
def login():
    return render_template("login.html")

@auth_bp.post("/login")
def login_post():
    email = request.form.get("email")
    senha = request.form.get("senha")

    # 1. Adicionar o filtro 'ativo=1'
    user = Usuario.query.filter_by(email=email, status=1).first()

    # 2. Verificar se o usuário existe e se a senha está correta
    if not user or not check_password_hash(user.senha, senha):
        flash("E-mail, senha ou status de usuário inválido.", "error")
        return redirect(url_for("auth.login"))
    
    # --- NOVO: REGISTRAR LOG DE ACESSO ---
    try:
        # Captura o IP real, mesmo se estiver atrás de Proxy (Nginx/Cloudflare)
        user_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        if user_ip and ',' in user_ip:
            user_ip = user_ip.split(',')[0].strip()

        # Atualiza os campos no objeto usuário
        # IMPORTANTE: Seu model Usuario deve ter as colunas 'ultimo_acesso' e 'ip_ultimo_acesso'
        user.ultimo_acesso = datetime.now()
        user.ip_ultimo_acesso = user_ip
        
        # Salva no banco de dados
        db.session.commit()
    except Exception as e:
        # Se der erro ao salvar o log (ex: coluna não existe), faz rollback mas permite o login
        db.session.rollback()
        print(f"Erro ao salvar log de acesso: {e}")
    # -------------------------------------
    
    session["user_id"] = user.id
    session["user_name"] = user.nome
    session["user_email"] = user.email
    session["user_role"] = user.papel
    
    if getattr(user, 'primeiro_acesso', False):
        return redirect(url_for("auth.alterar_senha_obrigatoria"))

    return redirect(url_for("auth.inicio"))

@auth_bp.get("/logout")
def logout():
    session.clear()
    flash("Você foi desconectado com sucesso.", "info")
    return redirect(url_for("auth.login"))

# --- ROTAS DE RECUPERAÇÃO DE SENHA ---

@auth_bp.route("/esqueci-senha", methods=["GET", "POST"])
def esqueci_senha():
    admin_contato = Usuario.query.filter_by(papel=ROLE_ADMIN).first()

    if request.method == "GET":
        return render_template("esqueci_senha.html", admin=admin_contato)
    
    email = request.form.get("email")
    user = Usuario.query.filter_by(email=email).first()
    
    if user:
        s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        token = s.dumps(email, salt='recuperacao-senha')
        link = url_for('auth.redefinir_senha', token=token, _external=True)
        
        print(f"========================================")
        print(f"LINK DE RECUPERAÇÃO PARA {email}:")
        print(f"{link}")
        print(f"========================================")
        
        flash("Um link de recuperação foi enviado para seu e-mail.", "success")
    else:
        flash("Se o e-mail estiver cadastrado, você receberá um link.", "success")
        
    return redirect(url_for("auth.login"))

@auth_bp.route("/redefinir-senha/<token>", methods=["GET", "POST"])
def redefinir_senha(token):
    s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        email = s.loads(token, salt='recuperacao-senha', max_age=3600)
    except SignatureExpired:
        flash("O link de recuperação expirou.", "danger")
        return redirect(url_for("auth.esqueci_senha"))
    except Exception:
        flash("Link de recuperação inválido.", "danger")
        return redirect(url_for("auth.esqueci_senha"))
    
    if request.method == "GET":
        return render_template("redefinir_senha.html", token=token)
    
    nova_senha = request.form.get("nova_senha")
    confirmar_senha = request.form.get("confirmar_senha")
    
    if nova_senha != confirmar_senha:
        flash("As senhas não conferem.", "danger")
        return render_template("redefinir_senha.html", token=token)
        
    user = Usuario.query.filter_by(email=email).first()
    
    if user:
        user.set_senha(nova_senha)
        db.session.commit()
        flash("Sua senha foi redefinida com sucesso! Faça login.", "success")
        return redirect(url_for("auth.login"))
        
    flash("Erro ao redefinir senha.", "danger")
    return redirect(url_for("auth.login"))

#######################################################################################################
####################################################################################################### Rotas Institucionais
#######################################################################################################

@auth_bp.get("/termos")
def termos():
    return render_template("termos.html")

@auth_bp.get("/privacidade")
def privacidade():
    return render_template("privacidade.html")

@auth_bp.get("/suporte")
def suporte():
    email_usuario = session.get("user_email", "")
    return render_template("suporte.html", email_usuario=email_usuario)

#######################################################################################################
####################################################################################################### Inicio (Dashboard)
#######################################################################################################

@auth_bp.get("/inicio")
@login_required
def inicio():
    hoje = date.today()
    ano_atual = hoje.year
    mes_atual = hoje.month
    
    # SCOPING: Filtra KPIs baseados nas obras permitidas do usuário
    user_id = session.get("user_id")
    user = Usuario.query.get(user_id)
    scope_ids = [o.id for o in user.obras_permitidas] if user.papel != ROLE_ADMIN else None

    # --- 1. KPIs PRINCIPAIS ---
    
    # Query base para Obras
    q_obras = Obra.query.filter_by(status=1)
    if scope_ids is not None:
        q_obras = q_obras.filter(Obra.id.in_(scope_ids))
    kpi_obras = q_obras.count()
    
    # Query base para RDOs
    q_rdos = RDO.query
    if scope_ids is not None:
        q_rdos = q_rdos.filter(RDO.id_obra.in_(scope_ids))
        
    kpi_pendentes = q_rdos.filter_by(status='Pendente').count()
    
    # KPI 3: Efetivo Total (Hoje)
    query_efetivo = db.session.query(
        func.sum(RDOMaoObra.quantidade_propria + RDOMaoObra.quantidade_terceirizada)
    ).join(RDO).filter(RDO.data == hoje)
    
    if scope_ids is not None:
        query_efetivo = query_efetivo.filter(RDO.id_obra.in_(scope_ids))
        
    kpi_efetivo = query_efetivo.scalar() or 0
    
    # KPI 4: Ocorrências (No Mês Atual)
    query_ocorrencias = db.session.query(func.count(TagsOcorrencias.id_tag_rdo))\
        .join(RDO)\
        .filter(extract('year', RDO.data) == ano_atual)\
        .filter(extract('month', RDO.data) == mes_atual)
        
    if scope_ids is not None:
        query_ocorrencias = query_ocorrencias.filter(RDO.id_obra.in_(scope_ids))

    kpi_ocorrencias = query_ocorrencias.scalar() or 0

    # --- 2. DADOS PARA INTERATIVIDADE ---
    q_raw = db.session.query(RDO.id, RDO.status, RDO.data).filter(extract('year', RDO.data) == ano_atual)
    if scope_ids is not None:
        q_raw = q_raw.filter(RDO.id_obra.in_(scope_ids))
    raw_rdos = q_raw.all()
    
    dados_graficos_json = [
        {'status': rdo.status, 'mes': rdo.data.month, 'data_iso': rdo.data.isoformat()} 
        for rdo in raw_rdos
    ]

    # --- 3. TABELA DE RESUMO (Últimos Registros) ---
    ultimos_rdos = q_rdos.order_by(RDO.data.desc(), RDO.id.desc()).limit(5).all()

    return render_template(
        "inicio.html",
        kpi_obras=kpi_obras,
        kpi_pendentes=kpi_pendentes,
        kpi_efetivo=int(kpi_efetivo),
        kpi_ocorrencias=kpi_ocorrencias,
        ultimos_rdos=ultimos_rdos,
        dados_graficos_json=dados_graficos_json
    )
    
#######################################################################################################
####################################################################################################### Empresa
#######################################################################################################

@auth_bp.app_context_processor
def inject_company_info():
    nome_empresa = Empresa.query.first().nome_empresa if Empresa.query.first() else "Não definido" 
    return dict(nome_empresa_global=nome_empresa)

@auth_bp.get("/empresa")
@login_required
@role_required([ROLE_ADMIN]) # SECURITY: Apenas Admin acessa configs da empresa
def empresa():
    config_data = {
        'nome_empresa': Empresa.query.first().nome_empresa if Empresa.query.first() else '',
        'logo_path': 'logo/logo.png',
        'icone_path': 'logo/icone.png'
    } 
    return render_template('empresa.html', config_data=config_data, view_mode=True)

@auth_bp.route('/salvar-empresa', methods=['POST'])
@login_required
@role_required([ROLE_ADMIN]) # SECURITY: Apenas Admin salva
def salvar_empresa():
    nome_empresa = request.form.get('nome_empresa')
    logo_file = request.files.get('logo_empresa')
    icone_file = request.files.get('icone_empresa')

    try:
        empresa_db = Empresa.query.first()
        if not empresa_db:
            empresa_db = Empresa(nome_empresa=nome_empresa)
            db.session.add(empresa_db)
        else:
            db.session.query(Empresa).update({'nome_empresa': nome_empresa})
        
        upload_folder = os.path.join(current_app.root_path, 'static', 'logo')
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)

        if logo_file and logo_file.filename != '':
            if allowed_file(logo_file.filename):
                logo_file.save(os.path.join(upload_folder, "logo.png"))

        if icone_file and icone_file.filename != '':
            if allowed_file(icone_file.filename):
                icone_file.save(os.path.join(upload_folder, "icone.png"))

        db.session.commit()
        flash('Configurações da empresa atualizadas com sucesso!', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao salvar configurações: {str(e)}', 'danger')

    return redirect(url_for('auth.empresa'))

#######################################################################################################
####################################################################################################### PDF
#######################################################################################################

@auth_bp.get("/gerar-pdf/<int:rdo_id>")
@login_required
def gerar_pdf_rdo_view(rdo_id):
    # SECURITY: Verificar se usuário tem acesso a este RDO
    rdo = RDO.query.get_or_404(rdo_id)
    scope_ids = get_user_scope_ids()
    if scope_ids is not None and rdo.id_obra not in scope_ids:
        abort(403) # Forbidden

    pdf_content = render_rdo_pdf(rdo_id) 
    try:
        pdf_content = travar_edicao_pdf(pdf_content)
    except Exception as e:
        print(f"Erro ao aplicar segurança no PDF: {e}")
    
    response = make_response(pdf_content)
    response.headers['Content-Type'] = 'application/pdf'
    filename = f"{rdo.data.strftime('%d-%m-%Y')} - RDO#{rdo_id} - {rdo.obra.nome if rdo.obra else 'Obra'}.pdf"
    response.headers['Content-Disposition'] = f'inline; filename={filename}'
    
    return response

@auth_bp.get("/gerar-pdf-compacto/<int:rdo_id>")
@login_required
def gerar_pdf_rdo_compacto_view(rdo_id):
    # SECURITY: Verificar scope
    rdo = RDO.query.get_or_404(rdo_id)
    scope_ids = get_user_scope_ids()
    if scope_ids is not None and rdo.id_obra not in scope_ids:
        abort(403)

    pdf_content = render_rdo_pdf_compact(rdo_id)
    pdf_content = travar_edicao_pdf(pdf_content)
    
    response = make_response(pdf_content)
    response.headers['Content-Type'] = 'application/pdf'
    filename = f"RDO_Compacto_{rdo_id}_Bloqueado.pdf"
    response.headers['Content-Disposition'] = f'inline; filename={filename}'
    
    return response

#######################################################################################################
####################################################################################################### RDO (Gestão)
#######################################################################################################

@auth_bp.get("/criar-rdo")
@login_required
@role_required(PERM_WRITE_BASIC) # Leitor e Cliente NÃO criam RDO
def criar_rdo():
    # Carregar apenas obras permitidas
    user = Usuario.query.get(session.get("user_id"))
    if user.papel == ROLE_ADMIN:
        obras = Obra.query.filter_by(status=1).all()
    else:
        # Filtra na memória as obras ativas do usuário
        obras = [o for o in user.obras_permitidas if o.status == 1]
    
    mao_de_obra_options = [{"id": m.id, "nome": m.nome} for m in MaoObra.query.all()]
    equipamentos_options = [{"id": e.id, "nome": e.nome} for e in Equipamento.query.all()]
    tags_options = [{"id": t.id, "nome": t.nome} for t in TagOcorrencia.query.all()]

    clima = Clima.query.all()
    frente_trabalho = Frente_Trabalho.query.all() 
    usuarios_obra = Usuario.query.all()

    return render_template(
        "form_rdo.html", 
        item=None, 
        obras=obras, 
        clima=clima, 
        frente_trabalho=frente_trabalho, 
        usuarios_obra=usuarios_obra,
        view_mode=False,
        mao_de_obra_options=mao_de_obra_options,
        equipamentos_options=equipamentos_options, 
        tags_options=tags_options 
    )

@auth_bp.get("/api/obra/<int:id>")
@login_required
def get_obra_api(id):
    # SECURITY: Verifica se usuário pode ver detalhes desta obra
    scope_ids = get_user_scope_ids()
    if scope_ids is not None and id not in scope_ids:
        return jsonify({"error": "Acesso não autorizado a esta obra"}), 403

    obra = Obra.query.get_or_404(id)
    frentes = Frente_Trabalho.query.filter_by(id_obra=id).all()
    
    data_inicio_fmt = obra.inicio.strftime('%d/%m/%Y') if obra.inicio else "-"
    data_inicio_iso = obra.inicio.isoformat() if obra.inicio else ""
    data_fim_fmt = obra.termino.strftime('%d/%m/%Y') if obra.termino else "-"
    data_fim_iso = obra.termino.isoformat() if obra.termino else ""
    nome_responsavel = obra.responsavel.nome if obra.responsavel else "Não definido"

    lista_frentes = []
    for f in frentes:
        nome_resp_frente = f.responsavel.nome if f.responsavel else "Sem responsável"
        id_resp_frente = f.id_responsavel if f.id_responsavel else ""
        lista_frentes.append({
            "id": f.id_frente_trabalho, 
            "nome": f.nome_frente,
            "responsavel_nome": nome_resp_frente,
            "responsavel_id": id_resp_frente,
            "unidade": f.unidade or "",
            "qtd_planejada": f.qtd_planejada or 0,
            "data_planejada": f.data_planejada or 0,
            "qtd_realizada": f.qtd_realizada or 0
        })

    return jsonify({
        "num_contrato": obra.contrato,
        "cliente": obra.contratante,         
        "data_inicio": data_inicio_fmt,
        "data_inicio_iso": data_inicio_iso,
        "data_fim": data_fim_fmt,
        "data_fim_iso": data_fim_iso,
        "responsavel": nome_responsavel,
        "frentes": lista_frentes
    })

@auth_bp.get("/api/frente/<int:id>")
@login_required
def get_frente_api(id):
    # SECURITY: Validação básica
    frente = Frente_Trabalho.query.get_or_404(id)
    # Verifica scope da obra pai da frente
    scope_ids = get_user_scope_ids()
    if scope_ids is not None and frente.id_obra not in scope_ids:
        return jsonify({"error": "Forbidden"}), 403

    return jsonify({
        "responsavel": frente.responsavel_tecnico.nome if frente.responsavel_tecnico else None
    })

@auth_bp.post("/gerar-rdo")
@login_required
@role_required(PERM_WRITE_BASIC) # Leitor e Cliente não podem postar
def gerar_rdo():
    try:
        sp_tz = timezone(timedelta(hours=-3))
        now_br = datetime.now(sp_tz).replace(tzinfo=None)
        current_user_id = session.get("user_id")

        # Helpers
        def _get_int(key):
            v = request.form.get(key)
            return int(v) if v and v.isdigit() else None
        
        def _get_time(key):
            v = request.form.get(key)
            if not v: return None
            try: return datetime.strptime(v, '%H:%M').time()
            except: return None
            
        def _get_float(key):
            v = request.form.get(key)
            if not v: return None
            try: return float(v.replace(',', '.'))
            except: return None

        rdo_id_original = _get_int("rdo_id")
        id_obra = _get_int("obra_id")

        # SECURITY: Validação de Escopo (Data Scoping)
        # Verifica se o usuário tem permissão na Obra alvo
        scope_ids = get_user_scope_ids()
        if scope_ids is not None:
            if id_obra not in scope_ids:
                flash("Você não tem permissão para criar/editar RDO nesta obra.", "danger")
                abort(403)

        # SECURITY: Se for edição, verifica status e permissões extras
        if rdo_id_original:
            item_rdo = RDO.query.get(rdo_id_original)
            if not item_rdo:
                abort(404)
            
            # Se já aprovado, apenas Admin/Gestor podem revisar (Operador não revisa aprovado, cria novo geralmente)
            if item_rdo.status == 'Aprovado' and session.get("user_role") == ROLE_OPERADOR:
                 flash("Operadores não podem alterar RDOs já aprovados. Solicite ao Gestor.", "danger")
                 return redirect(url_for('auth.visualizar_rdo', rdo_id=rdo_id_original))

            # UPDATE (EDIÇÃO / NOVA REVISÃO)
            rev_atual = item_rdo.id_revisao if item_rdo.id_revisao is not None else 0
            item_rdo.id_revisao = rev_atual + 1
            item_rdo.status = "Pendente"

            # Reset workflow
            assinaturas_existentes = Assinatura.query.filter_by(id_rdo=item_rdo.id).all()
            for ass in assinaturas_existentes:
                ass.img_assinatura = None
                ass.motivo_rejeicao = None
                ass.status = 'Pendente'
                ass.criado = None
                ass.ip_endereco = None
                ass.validacao = None

        else:
            # INSERT (NOVO RDO)
            max_seq = db.session.query(func.max(RDO.id_sequencial)).filter_by(id_obra=id_obra).scalar()
            proximo_seq = (max_seq if max_seq is not None else 0) + 1
            
            item_rdo = RDO(
                id_obra=id_obra,
                id_sequencial=proximo_seq,
                id_revisao=0
            )
            item_rdo.criado = now_br
            item_rdo.id_criado_por = current_user_id
            item_rdo.status = "Pendente"

        # Popular campos comuns
        item_rdo.id_frente_trabalho = _get_int("frente_trabalho_id")
        item_rdo.id_climas_manha = _get_int("climas_manha")
        item_rdo.id_climas_tarde = _get_int("climas_tarde")
        data_rdo_str = request.form.get("data_rdo")
        item_rdo.data = datetime.strptime(data_rdo_str, '%Y-%m-%d').date() if data_rdo_str else date.today()
        item_rdo.modificado = now_br
        item_rdo.id_modificado_por = current_user_id
        item_rdo.comentarios_gerais = request.form.get("comentarios_gerais")
        item_rdo.qtd_produzida = _get_float("qtd_produzida")
        item_rdo.hora_entrada = _get_time("hora_entrada")
        item_rdo.hora_saida = _get_time("hora_saida")
        item_rdo.intervalo_entrada = _get_time("intervalo_entrada")
        item_rdo.intervalo_saida = _get_time("intervalo_saida")
        
        if not rdo_id_original:
            db.session.add(item_rdo)
        
        db.session.flush()

        # [Criação] Assinatura do criador
        if not rdo_id_original: 
            existe_ass = Assinatura.query.filter_by(id_rdo=item_rdo.id, id_usuario=current_user_id).first()
            if not existe_ass:
                assinatura_criador = Assinatura(
                    id_rdo=item_rdo.id,
                    id_usuario=current_user_id,
                    ordem=1,
                    status='Pendente',
                    criado=now_br,
                    ip_endereco=request.remote_addr
                )
                db.session.add(assinatura_criador)

        # Limpeza de filhos para recriação
        if rdo_id_original:
            Atividades.query.filter_by(id_rdo=item_rdo.id).delete()
            RDOMaoObra.query.filter_by(id_rdo=item_rdo.id).delete()
            Equipamentos.query.filter_by(id_rdo=item_rdo.id).delete()
            TagsOcorrencias.query.filter_by(id_rdo=item_rdo.id).delete()

        # 1. Atividades
        descricoes = request.form.getlist("atividade_descricao[]")
        status_list = request.form.getlist("atividade_status[]")
        for i, desc in enumerate(descricoes):
            if desc and desc.strip():
                st = status_list[i] if i < len(status_list) else "Não iniciada"
                db.session.add(Atividades(id_rdo=item_rdo.id, descricao=desc, status=st))

        # 2. Mão de Obra
        funcoes = request.form.getlist("mo_funcao[]")
        qtd_prop = request.form.getlist("mo_qtd_propria[]")
        qtd_terc = request.form.getlist("mo_qtd_terceirizada[]")
        tempos = request.form.getlist("mo_tempo[]")
        for i, mo_func in enumerate(funcoes):
            if mo_func and mo_func.strip():
                qp = int(qtd_prop[i]) if i < len(qtd_prop) and qtd_prop[i] else 0
                qt = int(qtd_terc[i]) if i < len(qtd_terc) and qtd_terc[i] else 0
                tempo_str = tempos[i] if i < len(tempos) else None
                tempo_obj = datetime.strptime(tempo_str, '%H:%M').time() if tempo_str else None
                db.session.add(RDOMaoObra(id_rdo=item_rdo.id, nome_funcao=mo_func, quantidade_propria=qp, quantidade_terceirizada=qt, tempo=tempo_obj))

        # 3. Equipamentos
        eq_ids = request.form.getlist("eq_id[]")
        eq_qts = request.form.getlist("eq_qtd[]")
        for i, eid in enumerate(eq_ids):
            if eid:
                qtd = int(eq_qts[i]) if i < len(eq_qts) and eq_qts[i] else 0
                eq_obj = Equipamento.query.get(eid)
                db.session.add(Equipamentos(id_rdo=item_rdo.id, id_equipamento_lista=eid, nome_equipamento=eq_obj.nome if eq_obj else "", quantidade=qtd))

        # 4. Ocorrências
        oc_tags = request.form.getlist("oc_tag[]")
        oc_descs = request.form.getlist("oc_desc[]")
        oc_tempos = request.form.getlist("oc_tempo_parado[]")
        for i, tid in enumerate(oc_tags):
            if not tid: continue
            tempo_obj = None
            tempo_str = oc_tempos[i] if i < len(oc_tempos) else None
            if tempo_str and tempo_str.strip():
                try: tempo_obj = datetime.strptime(tempo_str, '%H:%M').time()
                except ValueError: tempo_obj = None
            desc = oc_descs[i] if i < len(oc_descs) else ""
            db.session.add(TagsOcorrencias(id_rdo=item_rdo.id, id_tag_lista=tid, descricao=desc, tempo_parado=tempo_obj))

        # 5. Fotos
        UPLOAD_FOLDER = os.path.join(current_app.root_path, 'static', 'uploads', 'rdo')
        if not os.path.exists(UPLOAD_FOLDER): os.makedirs(UPLOAD_FOLDER)
            
        ids_remover = request.form.getlist("fotos_remover[]")
        if ids_remover:
            for id_rem in ids_remover:
                try:
                    if not id_rem: continue
                    foto_del = Fotos.query.get(int(id_rem))
                    if foto_del and foto_del.id_rdo == item_rdo.id:
                        try:
                            caminho_arquivo = os.path.join(UPLOAD_FOLDER, foto_del.arquivo)
                            if os.path.exists(caminho_arquivo): os.remove(caminho_arquivo)
                        except Exception: pass
                        db.session.delete(foto_del)
                except Exception: pass
            
        ids_existentes = request.form.getlist("fotos_existentes_ids[]")
        comentarios_existentes = request.form.getlist("comentarios_existentes_list[]")
        for foto_id_str, nova_legenda in zip(ids_existentes, comentarios_existentes):
            try:
                if not foto_id_str: continue
                foto_id = int(foto_id_str)
                foto_obj = Fotos.query.get(foto_id)
                if foto_obj and foto_obj.id_rdo == item_rdo.id:
                    if foto_obj.comentario != nova_legenda:
                        foto_obj.comentario = nova_legenda
                        db.session.add(foto_obj)
            except Exception: pass

        arquivos = request.files.getlist("fotos[]")
        legendas = request.form.getlist("novas_fotos_comentarios[]")
        idx_file = 0
        for arquivo in arquivos:
            if arquivo and arquivo.filename:
                fname = secure_filename(arquivo.filename)
                ext = os.path.splitext(fname)[1].lower()
                if ext in ['.jpg', '.jpeg', '.png', '.webp']:
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S%f')
                    novo_nome = f"{timestamp}_{idx_file}{ext}"
                    arquivo.save(os.path.join(UPLOAD_FOLDER, novo_nome))
                    comentario = legendas[idx_file] if idx_file < len(legendas) else ""
                    db.session.add(Fotos(id_rdo=item_rdo.id, arquivo=novo_nome, comentario=comentario))
                    idx_file += 1

        db.session.commit()
        msg_acao = "revisado" if rdo_id_original else "salvo"
        flash(f"RDO Nº {item_rdo.id_sequencial} (Rev {item_rdo.id_revisao}) {msg_acao} com sucesso!", "success")
        return redirect(url_for('auth.visualizar_rdo', rdo_id=item_rdo.id))

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erro ao gerar RDO: {e}")
        import traceback
        traceback.print_exc()
        flash(f"Erro ao salvar RDO: {str(e)}", "danger")
        return redirect(request.referrer)
    
@auth_bp.get("/visualizar-rdo/<int:rdo_id>")
@login_required
def visualizar_rdo(rdo_id):
    item = RDO.query.get_or_404(rdo_id)

    # SECURITY: Verifica permissão na obra para leitura
    scope_ids = get_user_scope_ids()
    if scope_ids is not None and item.id_obra not in scope_ids:
        flash("Você não tem permissão para visualizar este RDO.", "danger")
        return redirect(url_for("auth.inicio"))

    mao_de_obra_options = [{"id": m.id, "nome": m.nome} for m in MaoObra.query.all()]
    equipamentos_options = [{"id": e.id, "nome": e.nome} for e in Equipamento.query.all()]
    tags_options = [{"id": t.id, "nome": t.nome} for t in TagOcorrencia.query.all()]
    assinaturas = Assinatura.query.filter_by(id_rdo=rdo_id).order_by(Assinatura.ordem).all()
    
    if item.id_obra:
        usuarios_obra = Usuario.query.filter(
            Usuario.obras_permitidas.any(id=item.id_obra),
            Usuario.status == True 
        ).all()
        if not usuarios_obra:
            usuarios_obra = Usuario.query.filter_by(status=True).all()
    else:
        usuarios_obra = Usuario.query.filter_by(status=True).all()
    
    ass_valida = Assinatura.query.filter_by(id_rdo=rdo_id, status='Aprovado').order_by(Assinatura.ordem.desc()).first()
    if ass_valida and ass_valida.hash_documento:
        url_validacao = url_for('auth.validar_documento_publico', h=ass_valida.hash_documento, _external=True)
    else:
        url_validacao = url_for('auth.visualizar_rdo', rdo_id=rdo_id, _external=True)

    qr_code_img = gerar_qrcode_b64(url_validacao)

    return render_template(
        "form_rdo.html",
        item=item,
        view_mode=True,
        obras=Obra.query.all(),
        clima=Clima.query.all(),
        frente_trabalho=Frente_Trabalho.query.all(),
        equipamentos=Equipamentos.query.all(),
        assinaturas=assinaturas,
        mao_obra=RDOMaoObra.query.all(),
        usuarios=Usuario.query.all(),
        usuarios_obra=usuarios_obra,
        mao_de_obra_options=mao_de_obra_options,
        equipamentos_options=equipamentos_options,
        tags_options=tags_options,
        qr_code_b64=qr_code_img
    )

@auth_bp.get("/editar-rdo/<int:rdo_id>")
@login_required
@role_required(PERM_WRITE_BASIC) # Leitor e Cliente não editam
def editar_rdo(rdo_id):
    item = RDO.query.get_or_404(rdo_id)

    # SECURITY: Verifica se usuario tem acesso à obra deste RDO
    scope_ids = get_user_scope_ids()
    if scope_ids is not None and item.id_obra not in scope_ids:
        abort(403)

    usuarios_obra = Usuario.query.filter(Usuario.obras_permitidas.any(id=item.id_obra)).all()
    assinaturas_realizadas = Assinatura.query.filter_by(id_rdo=rdo_id).all()
    ids_usuarios_que_assinaram = [a.id_usuario for a in assinaturas_realizadas]

    lista_assinaturas_status = []
    for u in usuarios_obra:
        ass_obj = next((a for a in assinaturas_realizadas if a.id_usuario == u.id), None)
        if u.id == item.id_criado_por or u.id in ids_usuarios_que_assinaram or u.papel in [ROLE_ADMIN, 'Engenheiro', 'Supervisor']:
            lista_assinaturas_status.append({
                "usuario": u,
                "assinado": True if ass_obj else False,
                "dados_assinatura": ass_obj
            })

    maos_obra_salvas = item.maos_obra.all()
    equipamentos_salvos = item.equipamentos.all()
    atividades_salvas = item.atividades.all()
    ocorrencias_salvas = item.ocorrencias.all()
    fotos_salvas = item.fotos.all()
    frente_trabalho=Frente_Trabalho.query.all()

    return render_template(
        "form_rdo.html",
        item=item,
        view_mode=False,
        obras=Obra.query.filter_by(status=1).all(),
        frente_trabalho=frente_trabalho,
        clima=Clima.query.all(),
        maos_obra_salvas=maos_obra_salvas,
        equipamentos_salvos=equipamentos_salvos,
        atividades_salvas=atividades_salvas,
        ocorrencias_salvas=ocorrencias_salvas,
        fotos_salvas=fotos_salvas,
        mao_de_obra_options=[{"id": m.id, "nome": m.nome} for m in MaoObra.query.all()],
        equipamentos_options=[{"id": e.id, "nome": e.nome} for e in Equipamento.query.all()],
        tags_options=[{"id": t.id, "nome": t.nome} for t in TagOcorrencia.query.all()],
        usuarios_obra=usuarios_obra,
        lista_assinaturas_status=lista_assinaturas_status,
        assinaturas=assinaturas_realizadas,
        Atividades=Atividades,
        RDOMaoObra=RDOMaoObra,
        Equipamentos=Equipamentos,
        Fotos=Fotos,
        TagsOcorrencias=TagsOcorrencias
    )

@auth_bp.post("/excluir-rdo/<int:rdo_id>")
@login_required
@role_required(PERM_MANAGEMENT) # SECURITY: Apenas Admin/Gestor exclui RDO (Operador não)
def excluir_rdo(rdo_id):
    try:
        item_rdo = RDO.query.get_or_404(rdo_id)
        
        # SECURITY: Scoping Check
        scope_ids = get_user_scope_ids()
        if scope_ids is not None and item_rdo.id_obra not in scope_ids:
            abort(403)

        upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'rdo')
        fotos = Fotos.query.filter_by(id_rdo=item_rdo.id).all()
        for foto in fotos:
            caminho_arquivo = os.path.join(upload_folder, foto.arquivo)
            if os.path.exists(caminho_arquivo):
                os.remove(caminho_arquivo)

        Atividades.query.filter_by(id_rdo=item_rdo.id).delete()
        RDOMaoObra.query.filter_by(id_rdo=item_rdo.id).delete()
        Equipamentos.query.filter_by(id_rdo=item_rdo.id).delete()
        TagsOcorrencias.query.filter_by(id_rdo=item_rdo.id).delete()
        Fotos.query.filter_by(id_rdo=item_rdo.id).delete()
        Assinatura.query.filter_by(id_rdo=item_rdo.id).delete()

        db.session.delete(item_rdo)
        db.session.commit()

        flash(f"RDO Nº {item_rdo.id_sequencial} excluído com sucesso!", "success")
        return redirect(url_for('auth.inicio'))
    except Exception as e:
        db.session.rollback()
        flash(f"Ocorreu um erro ao excluir o RDO: {str(e)}", "danger")
        return redirect(url_for('auth.inicio'))

@auth_bp.get("/lista-rdo")
@login_required
def lista_rdo():
    current_user_id = session.get("user_id")
    user = Usuario.query.get(current_user_id)

    # SCOPING: Filtra RDOs
    if user:
        if user.papel == ROLE_ADMIN:
             rdos = RDO.query.order_by(RDO.data.desc()).all()
        else:
            ids_obras_permitidas = [obra.id for obra in user.obras_permitidas]
            rdos = RDO.query.filter(RDO.id_obra.in_(ids_obras_permitidas)).order_by(RDO.data.desc()).all()
    else:
        rdos = []
    
    lista_pendencias = Assinatura.query.filter_by(
        id_usuario=current_user_id, 
        status='Pendencia'
    ).all()
    
    minhas_pendencias = Assinatura.query.filter_by(
        id_usuario=current_user_id,
        status='Pendente'
    ).count()

    return render_template("list_rdo.html", rdos=rdos, count_minhas_pendencias=minhas_pendencias, lista_pendencias=lista_pendencias)

#######################################################################################################
####################################################################################################### Assinaturas RDO
#######################################################################################################

@auth_bp.route("/assinar-rdo/<int:rdo_id>/salvar-workflow", methods=["POST"])
@login_required
@role_required(PERM_MANAGEMENT) # Apenas Gestor/Admin define fluxo
def salvar_workflow_assinaturas(rdo_id):
    rdo = RDO.query.get_or_404(rdo_id)
    
    # Scoping
    scope_ids = get_user_scope_ids()
    if scope_ids is not None and rdo.id_obra not in scope_ids:
        return jsonify({"success": False, "message": "Sem permissão na obra."}), 403
    
    if rdo.status in ['Aprovado', 'Rejeitado']:
         return jsonify({"success": False, "message": "RDO finalizado, não é possível alterar aprovadores."}), 403

    data = request.get_json()
    novos_assinantes_ids = [int(uid) for uid in data.get('usuarios_ids', [])] 
    
    creator_id = rdo.id_criado_por
    if creator_id in novos_assinantes_ids:
        novos_assinantes_ids.remove(creator_id)
    novos_assinantes_ids.insert(0, creator_id)

    try:
        Assinatura.query.filter_by(id_rdo=rdo_id).delete()
        for index, user_id in enumerate(novos_assinantes_ids):
            nova_ass = Assinatura(
                id_rdo=rdo_id,
                id_usuario=user_id,
                ordem=index + 1,
                status='Pendente'
            )
            db.session.add(nova_ass)
        rdo.status = 'Pendente'
        db.session.commit()
        return jsonify({"success": True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500

@auth_bp.route("/assinar-rdo/<int:rdo_id>/aprovar-rdo", methods=["POST"])
@login_required
@role_required(PERM_SIGNATURE) # Todos (exceto Leitor) podem assinar se estiverem no fluxo
def assinar_rdo(rdo_id):
    user_id = session.get("user_id")
    rdo = RDO.query.get_or_404(rdo_id)

    # Scoping check: Tem que ter acesso à obra pra assinar
    scope_ids = get_user_scope_ids()
    if scope_ids is not None and rdo.id_obra not in scope_ids:
         return jsonify({"success": False, "message": "Sem permissão na obra."}), 403

    assinatura_pendente = Assinatura.query.filter_by(
        id_rdo=rdo_id, 
        id_usuario=user_id, 
        status='Pendente'
    ).first()

    if not assinatura_pendente:
        return jsonify({"success": False, "message": "Você não tem assinaturas pendentes para este RDO."}), 400

    passo_anterior_pendente = Assinatura.query.filter(
        Assinatura.id_rdo == rdo_id,
        Assinatura.ordem < assinatura_pendente.ordem,
        Assinatura.status != 'Aprovado'
    ).count()

    if passo_anterior_pendente > 0:
        return jsonify({"success": False, "message": "Aguarde a aprovação do responsável anterior."}), 403

    dados = request.get_json()
    img_data = dados.get('assinatura_b64')
    latitude = dados.get('latitude')
    longitude = dados.get('longitude')
    
    if not img_data:
        return jsonify({"success": False, "message": "Imagem da assinatura não fornecida."}), 400

    try:
        header, encoded = img_data.split(",", 1)
        file_data = base64.b64decode(encoded)
        filename = f"sig_{rdo_id}_{user_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
        
        upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'assinaturas')
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)
            
        with open(os.path.join(upload_folder, filename), "wb") as f:
            f.write(file_data)

        user_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        if user_ip and ',' in user_ip:
            user_ip = user_ip.split(',')[0].strip()

        hash_string = f"{rdo_id}:{user_id}:{datetime.utcnow()}:{current_app.config['SECRET_KEY']}"
        document_hash = hashlib.sha256(hash_string.encode()).hexdigest()

        assinatura_pendente.img_assinatura = filename
        assinatura_pendente.criado = datetime.now()
        assinatura_pendente.status = 'Aprovado'
        assinatura_pendente.ip_endereco = user_ip
        assinatura_pendente.latitude = latitude
        assinatura_pendente.longitude = longitude
        assinatura_pendente.hash_documento = document_hash 
        
        restantes = Assinatura.query.filter(
            Assinatura.id_rdo == rdo_id,
            Assinatura.status == 'Pendente',
            Assinatura.id_assinatura != assinatura_pendente.id_assinatura
        ).count()
        
        if restantes == 0:
            rdo.status = 'Aprovado'
        else:
            rdo.status = 'Pendente'

        db.session.commit()
        return jsonify({"success": True})

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    
@auth_bp.route("/assinar-rdo/<int:id_assinatura>/rejeitar-rdo", methods=["POST"])
@login_required
@role_required(PERM_SIGNATURE)
def rejeitar_assinatura(id_assinatura):
    dados = request.get_json()
    motivo = dados.get('motivo')
    ass = Assinatura.query.get_or_404(id_assinatura)
    
    if ass.id_usuario != session.get('user_id'):
        return jsonify({"success": False, "message": "Não autorizado."}), 403

    try:
        ass.status = 'Rejeitado'
        ass.motivo_rejeicao = motivo
        ass.criado = datetime.now()
        rdo = RDO.query.get(ass.id_rdo)
        rdo.status = 'Rejeitado'
        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    
#######################################################################################################
####################################################################################################### USUARIOS
#######################################################################################################

@auth_bp.get("/lista-usuarios")
@login_required
@role_required(PERM_WRITE_BASIC) # Leitor e Cliente não veem usuários
def lista_usuarios():
    # SCOPING: Gestor/Operador só veem usuários de suas obras
    query = Usuario.query
    if session.get("user_role") != ROLE_ADMIN:
        user = Usuario.query.get(session.get("user_id"))
        ids_permitidos = [o.id for o in user.obras_permitidas]
        # Filtra usuários que tenham intersecção de obras (usuários da mesma obra)
        query = query.filter(Usuario.obras_permitidas.any(Obra.id.in_(ids_permitidos)))

    usuarios = query.order_by(Usuario.id.asc()).all()

    # Preenchimento de supervisor (mantido)
    sup_ids = set()
    for u in usuarios:
        try:
            if u.id_supervisor is not None and str(u.id_supervisor).strip() != '':
                sup_ids.add(int(str(u.id_supervisor).strip()))
        except Exception: continue

    sup_map = {}
    if sup_ids:
        supervisors = Usuario.query.filter(Usuario.id.in_(list(sup_ids))).all()
        sup_map = {s.id: s.nome for s in supervisors}

    for u in usuarios:
        nome_sup = None
        try:
            if u.id_supervisor is not None and str(u.id_supervisor).strip() != '':
                sup_id = int(str(u.id_supervisor).strip())
                nome_sup = sup_map.get(sup_id)
        except Exception: pass
        setattr(u, 'nome_supervisor', nome_sup)

    return render_template("list_usuarios.html", opcoes=usuarios, categoria="usuario")

@auth_bp.get("/criar-usuario")
@login_required
@role_required(PERM_MANAGEMENT) # Apenas Admin e Gestor criam
def criar_usuario():
    # SCOPING: Gestor só pode vincular às suas obras
    user = Usuario.query.get(session.get("user_id"))
    if user.papel == ROLE_ADMIN:
        obras = Obra.query.filter_by(status=1).order_by(Obra.nome).all()
    else:
        obras = [o for o in user.obras_permitidas if o.status == 1]
    
    admin = Usuario.query.filter_by(papel='Admin').first()
    default_supervisor = {'id': admin.id, 'nome': admin.nome, 'email': admin.email} if admin else None

    return render_template(
        "form_usuario.html", 
        categoria="usuario", 
        obras=obras,
        default_supervisor=default_supervisor
    )

@auth_bp.post("/gerar-usuario")
@login_required
@role_required(PERM_MANAGEMENT)
def gerar_usuario():
    categoria = request.form.get("categoria")
    user_id = request.form.get("id")
    current_user_obj = Usuario.query.get(session.get("user_id"))
    
    # SCOPING: Para reload do template em caso de erro
    if current_user_obj.papel == ROLE_ADMIN:
        obras_ativas = Obra.query.filter_by(status=1).order_by(Obra.nome).all()
    else:
        obras_ativas = [o for o in current_user_obj.obras_permitidas if o.status == 1]

    if categoria == "usuario":
        nome = request.form.get("nome")
        email = request.form.get("email")
        papel = request.form.get("papel")
        cpf = request.form.get("cpf") 
        senha = request.form.get("senha")
        status = True if request.form.get("status") == "on" else False
        obras_ids = request.form.getlist("obras_permitidas")
        id_supervisor_raw = request.form.get('id_supervisor')

        # SECURITY: Gestor não pode criar Admin
        if current_user_obj.papel == ROLE_GESTOR and papel == ROLE_ADMIN:
            flash("Gestores não podem criar usuários Administradores.", "danger")
            return render_template("form_usuario.html", item=None, obras=obras_ativas)

        item_form = {'id': user_id, 'nome': nome, 'email': email, 'papel': papel, 'cpf': cpf}

        if user_id:
            user = Usuario.query.get_or_404(user_id)
            # Validar se Gestor pode editar este usuário
            if current_user_obj.papel != ROLE_ADMIN:
                # Simplificação: Se o usuário alvo tem alguma obra em comum, permite (ou restringe mais conforme regra)
                # Por segurança, impede edição de admin por gestor
                if user.papel == ROLE_ADMIN:
                    flash("Gestores não podem editar Admins.", "danger")
                    return redirect(url_for('auth.lista_usuarios'))

            if Usuario.query.filter(Usuario.cpf == cpf, Usuario.id != user_id).first():
                flash("Este CPF já está cadastrado.", "danger")
                return render_template("form_usuario.html", item=item_form, obras=obras_ativas)
            
            user.nome, user.email, user.papel, user.cpf, user.status = nome, email, papel, cpf, status
            try: user.id_supervisor = int(id_supervisor_raw) if id_supervisor_raw else None
            except Exception: user.id_supervisor = None
        else:
            if Usuario.query.filter_by(cpf=cpf).first():
                flash("CPF já cadastrado.", "danger")
                return render_template("form_usuario.html", item=item_form, obras=obras_ativas)

            user = Usuario(nome=nome, email=email, papel=papel, cpf=cpf, status=status, primeiro_acesso=True)
            try: user.id_supervisor = int(id_supervisor_raw) if id_supervisor_raw else None
            except Exception: user.id_supervisor = None
            user.set_senha(senha if senha else "Usuario123")
            db.session.add(user)

        if papel == 'Admin':
            user.obras_permitidas = Obra.query.all()
        else:
            obras_selecionadas = []
            if obras_ids:
                # SECURITY: Garantir que Gestor só vincula obras que ele tem acesso
                allowed_ids = [o.id for o in obras_ativas]
                for oid in obras_ids:
                    if oid:
                        if current_user_obj.papel == ROLE_ADMIN or int(oid) in allowed_ids:
                            obra = Obra.query.get(int(oid))
                            if obra: obras_selecionadas.append(obra)
            user.obras_permitidas = obras_selecionadas

        if not getattr(user, 'id_supervisor', None):
            try:
                admin = Usuario.query.filter_by(papel='Admin').first()
                if admin: user.id_supervisor = admin.id
            except Exception: pass

        try:
            db.session.commit()
            flash("Usuário salvo com sucesso!", "success")
            return render_template("form_usuario.html", item=user, obras=obras_ativas, view_mode=True)
        except Exception as e:
            db.session.rollback()
            flash(f"Erro: {str(e)}", "danger")
            return render_template("form_usuario.html", item=item_form, obras=obras_ativas)

@auth_bp.post("/mudar-status-usuario/<int:userId>")
@login_required
@role_required(PERM_MANAGEMENT)
def toggle_user_status(userId):
    # SECURITY: Verifica permissão sobre o usuário alvo
    user_alvo = Usuario.query.get_or_404(userId)
    if session.get("user_role") == ROLE_GESTOR:
        if user_alvo.papel == ROLE_ADMIN:
            return jsonify({"message": "Proibido alterar Admin"}), 403
    
    user_alvo.status = not user_alvo.status 
    try:
        db.session.commit()
        return jsonify({"message": "Status atualizado", "status": user_alvo.status}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": str(e)}), 500
     
@auth_bp.post("/usuario-resetar-senha/<int:id>")
@login_required
@role_required(PERM_MANAGEMENT)
def reset_senha_usuario(id):
    user = Usuario.query.get_or_404(id)
    # SECURITY
    if session.get("user_role") == ROLE_GESTOR and user.papel == ROLE_ADMIN:
         return {"message": "Gestor não reseta senha de Admin"}, 403

    user.set_senha("Usuario123")
    user.primeiro_acesso = True
    db.session.commit()
    return {"message": "Sucesso"}, 200
    

@auth_bp.route("/editar-usuario/<int:id>", methods=['GET', 'POST'])
@login_required
@role_required(PERM_MANAGEMENT)
def editar_usuario(id):
    user_edit = Usuario.query.get_or_404(id)
    current_user_obj = Usuario.query.get(session.get("user_id"))

    # SECURITY Scope
    if current_user_obj.papel == ROLE_GESTOR:
        if user_edit.papel == ROLE_ADMIN:
            flash("Acesso negado.", "danger")
            return redirect(url_for('auth.lista_usuarios'))
        obras = [o for o in current_user_obj.obras_permitidas if o.status == 1]
    else:
        obras = Obra.query.filter_by(status=1).order_by(Obra.nome).all()

    return render_template("form_usuario.html", item=user_edit, categoria="usuario", obras=obras)
    
@auth_bp.get("/visualizar-usuario/<int:id>")
@login_required
@role_required(PERM_WRITE_BASIC)
def visualizar_usuario(id):
    user_view = Usuario.query.get_or_404(id)
    current_user_obj = Usuario.query.get(session.get("user_id"))
    
    # SECURITY Scope check
    if current_user_obj.papel != ROLE_ADMIN:
        # Verifica se tem obras em comum
        meus_ids = {o.id for o in current_user_obj.obras_permitidas}
        alvo_ids = {o.id for o in user_view.obras_permitidas}
        if not meus_ids.intersection(alvo_ids) and current_user_obj.id != user_view.id:
             flash("Você não tem permissão para visualizar este usuário.", "danger")
             return redirect(url_for('auth.lista_usuarios'))
        obras = [o for o in current_user_obj.obras_permitidas if o.status == 1]
    else:
        obras = Obra.query.filter_by(status=1).order_by(Obra.nome).all()
    
    view_mode = True
    supervisor_chain = get_supervisor_chain_for_user(user_view)

    nome_supervisor = None
    if getattr(user_view, 'id_supervisor', None):
        try:
            sup = Usuario.query.get(int(user_view.id_supervisor))
            nome_supervisor = sup.nome if sup else None
        except Exception: pass
    setattr(user_view, 'nome_supervisor', nome_supervisor)

    default_supervisor = None
    try:
        admin = Usuario.query.filter_by(papel='Admin').first()
        if admin: default_supervisor = {'id': admin.id, 'nome': admin.nome, 'email': admin.email}
    except Exception: pass

    return render_template(
        "form_usuario.html", 
        item=user_view, 
        categoria="usuario", 
        obras=obras, 
        view_mode=view_mode, 
        supervisor_chain=supervisor_chain, 
        default_supervisor=default_supervisor
    )

def get_supervisor_chain_for_user(user):
    chain = []
    visited = set()
    current = user
    while current and getattr(current, 'id_supervisor', None):
        try: sup_id = int(getattr(current, 'id_supervisor'))
        except Exception: break
        if sup_id in visited: break
        sup = Usuario.query.get(sup_id)
        if not sup: break
        chain.append({'id': sup.id, 'nome': sup.nome, 'email': sup.email})
        visited.add(sup.id)
        current = sup
    return chain

@auth_bp.get('/supervisores')
@login_required
def lista_supervisores():
    users = Usuario.query.order_by(Usuario.nome.asc()).all()
    result = [{'id': u.id, 'nome': u.nome, 'papel': u.papel, 'email': u.email} for u in users]
    return jsonify(result)

@auth_bp.before_app_request
def check_primeiro_acesso():
    user_id = session.get("user_id")
    if user_id:
        user = Usuario.query.get(user_id)
        if user and getattr(user, 'primeiro_acesso', False):
            rotas_permitidas = ['auth.alterar_senha_obrigatoria', 'auth.logout', 'static', 'auth.login']
            if request.endpoint not in rotas_permitidas:
                flash("Por segurança, você deve alterar sua senha no primeiro acesso.", "warning")
                return redirect(url_for('auth.alterar_senha_obrigatoria'))
        
@auth_bp.route("/alterar-senha-obrigatoria", methods=["GET", "POST"])
@login_required
def alterar_senha_obrigatoria():
    if request.method == "POST":
        nova_senha = request.form.get("nova_senha")
        confirmar_senha = request.form.get("confirmar_senha")

        if not nova_senha or not confirmar_senha:
            flash("Preencha todos os campos.", "danger")
            return render_template("alterar_senha_obrigatoria.html")

        if nova_senha != confirmar_senha:
            flash("As senhas não conferem.", "danger")
            return render_template("alterar_senha_obrigatoria.html")
            
        if len(nova_senha) < 6:
             flash("A senha deve ter no mínimo 6 caracteres.", "danger")
             return render_template("alterar_senha_obrigatoria.html")

        user = Usuario.query.get(session.get("user_id"))
        user.set_senha(nova_senha)
        user.primeiro_acesso = False 
        try:
            db.session.commit()
            flash("Senha alterada com sucesso! Bem-vindo.", "success")
            return redirect(url_for("auth.inicio"))
        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao salvar senha: {str(e)}", "danger")

    return render_template("alterar_senha_obrigatoria.html")

#######################################################################################################
####################################################################################################### LISTAS AUXILIARES (Clima, Equip, MaoObra, Tags)
#######################################################################################################
# RBAC: Visualizar = Todos | Criar/Editar = Admin, Gestor, Operador | Excluir = Admin, Gestor

@auth_bp.get("/lista-climas")
@login_required
def lista_climas():
    climas = Clima.query.order_by(Clima.nome.asc()).all()
    return render_template("list_climas.html", opcoes=climas, categoria="clima")

@auth_bp.get('/criar-clima')
@login_required
@role_required(PERM_WRITE_BASIC)
def criar_clima():
    return render_template('form_clima.html', item=None, view_mode=False)

@auth_bp.post('/gerar-clima')
@login_required
@role_required(PERM_WRITE_BASIC)
def gerar_clima():
    clima_id = request.form.get('id')
    tipo_lista = "Climas"
    nome = request.form.get('nome', '').strip()
    if not nome:
        flash('Nome do clima é obrigatório.', 'danger')
        if clima_id: return redirect(url_for('auth.editar_clima', id=clima_id))
        return redirect(url_for('auth.criar_clima'))

    if clima_id:
        clima = Clima.query.get(clima_id)
        if not clima: return redirect(url_for('auth.lista_climas'))
        clima.nome = nome
        db.session.add(clima)
        db.session.commit()
        return redirect(url_for('auth.lista_climas'))

    novo = Clima(nome=nome, tipo_lista=tipo_lista)
    db.session.add(novo)
    db.session.commit()
    return redirect(url_for('auth.lista_climas'))

@auth_bp.get('/visualizar-clima/<int:id>')
@login_required
def visualizar_clima(id):
    clima = Clima.query.get_or_404(id)
    return render_template('form_clima.html', item=clima, view_mode=True)

@auth_bp.get('/editar-clima/<int:id>')
@login_required
@role_required(PERM_WRITE_BASIC)
def editar_clima(id):
    clima = Clima.query.get_or_404(id)
    return render_template('form_clima.html', item=clima, view_mode=False)

@auth_bp.post('/excluir-clima/<int:id>')
@login_required
@role_required(PERM_MANAGEMENT)
def excluir_clima(id):
    clima = Clima.query.get(id)
    if clima:
        db.session.delete(clima)
        db.session.commit()
    return redirect(url_for('auth.lista_climas'))

# --- EQUIPAMENTOS ---
@auth_bp.get("/lista-equipamentos")
@login_required
def lista_equipamentos():
    equipamentos = Equipamento.query.order_by(Equipamento.nome.asc()).all()
    return render_template("list_equipamentos.html", opcoes=equipamentos, categoria="equipamento")

@auth_bp.get('/criar-equipamento')
@login_required
@role_required(PERM_WRITE_BASIC)
def criar_equipamento():
    return render_template('form_equipamento.html', item=None, view_mode=False)

@auth_bp.post('/gerar-equipamento')
@login_required
@role_required(PERM_WRITE_BASIC)
def gerar_equipamento():
    equipamento_id = request.form.get('id')
    tipo_lista = "Equipamentos"
    nome = request.form.get('nome', '').strip()
    if not nome:
        flash('Nome do equipamento é obrigatório.', 'danger')
        return redirect(url_for('auth.lista_equipamentos'))

    if equipamento_id:
        equipamento = Equipamento.query.get(equipamento_id)
        equipamento.nome = nome
        db.session.add(equipamento)
    else:
        novo = Equipamento(nome=nome, tipo_lista=tipo_lista)
        db.session.add(novo)
    db.session.commit()
    return redirect(url_for('auth.lista_equipamentos'))

@auth_bp.get('/visualizar-equipamento/<int:id>')
@login_required
def visualizar_equipamento(id):
    equipamento = Equipamento.query.get_or_404(id)
    return render_template('form_equipamento.html', item=equipamento, view_mode=True)

@auth_bp.get('/editar-equipamento/<int:id>')
@login_required
@role_required(PERM_WRITE_BASIC)
def editar_equipamento(id):
    equipamento = Equipamento.query.get_or_404(id)
    return render_template('form_equipamento.html', item=equipamento, view_mode=False)

@auth_bp.post('/excluir-equipamento/<int:id>')
@login_required
@role_required(PERM_MANAGEMENT)
def excluir_equipamento(id):
    equipamento = Equipamento.query.get(id)
    if equipamento:
        db.session.delete(equipamento)
        db.session.commit()
    return redirect(url_for('auth.lista_equipamentos'))

# --- TAGS ---
@auth_bp.get("/lista-tags-ocorrencias")
@login_required
def lista_tags_ocorrencias():
    tagsOcorrencias = TagOcorrencia.query.order_by(TagOcorrencia.nome.asc()).all()
    return render_template("list_tags_ocorrencias.html", opcoes=tagsOcorrencias, categoria="tagsOcorrencias")

@auth_bp.get('/criar-tags-ocorrencias')
@login_required
@role_required(PERM_WRITE_BASIC)
def criar_tags_ocorrencias():
    return render_template('form_tags_ocorrencias.html', item=None, view_mode=False)

@auth_bp.post('/gerar-tags-ocorrencias')
@login_required
@role_required(PERM_WRITE_BASIC)
def gerar_tags_ocorrencias():
    tag_id = request.form.get('id')
    nome = request.form.get('nome', '').strip()
    if not nome: return redirect(url_for('auth.lista_tags_ocorrencias'))

    if tag_id:
        tag = TagOcorrencia.query.get(tag_id)
        tag.nome = nome
        db.session.add(tag)
    else:
        db.session.add(TagOcorrencia(nome=nome, tipo_lista="Tags Ocorrencias"))
    db.session.commit()
    return redirect(url_for('auth.lista_tags_ocorrencias'))

@auth_bp.get('/visualizar-tags-ocorrencias/<int:id>')
@login_required
def visualizar_tags_ocorrencias(id):
    tag = TagOcorrencia.query.get_or_404(id)
    return render_template('form_tags_ocorrencias.html', item=tag, view_mode=True)

@auth_bp.get('/editar-tags-ocorrencias/<int:id>')
@login_required
@role_required(PERM_WRITE_BASIC)
def editar_tags_ocorrencias(id):
    tag = TagOcorrencia.query.get_or_404(id)
    return render_template('form_tags_ocorrencias.html', item=tag, view_mode=False)

@auth_bp.post('/excluir-tags-ocorrencias/<int:id>')
@login_required
@role_required(PERM_MANAGEMENT)
def excluir_tags_ocorrencias(id):
    tag = TagOcorrencia.query.get(id)
    if tag:
        db.session.delete(tag)
        db.session.commit()
    return redirect(url_for('auth.lista_tags_ocorrencias'))

# --- MAO DE OBRA ---
@auth_bp.get("/lista-mao-obra")
@login_required
def lista_mao_obra():
    mao_obra = MaoObra.query.order_by(MaoObra.nome.asc()).all()
    return render_template("list_mao_obra.html", opcoes=mao_obra, categoria="mao_obra")

@auth_bp.get('/criar-mao-obra')
@login_required
@role_required(PERM_WRITE_BASIC)
def criar_mao_obra():
    return render_template('form_mao_obra.html', item=None, view_mode=False)

@auth_bp.post('/gerar-mao-obra')
@login_required
@role_required(PERM_WRITE_BASIC)
def gerar_mao_obra():
    mo_id = request.form.get('id')
    nome = request.form.get('nome', '').strip()
    if not nome: return redirect(url_for('auth.lista_mao_obra'))

    if mo_id:
        mo = MaoObra.query.get(mo_id)
        mo.nome = nome
        db.session.add(mo)
    else:
        db.session.add(MaoObra(nome=nome, tipo_lista="Mao de Obra"))
    db.session.commit()
    return redirect(url_for('auth.lista_mao_obra'))

@auth_bp.get('/visualizar-mao-obra/<int:id>')
@login_required
def visualizar_mao_obra(id):
    mo = MaoObra.query.get_or_404(id)
    return render_template('form_mao_obra.html', item=mo, view_mode=True)

@auth_bp.get('/editar-mao-obra/<int:id>')
@login_required
@role_required(PERM_WRITE_BASIC)
def editar_mao_obra(id):
    mo = MaoObra.query.get_or_404(id)
    return render_template('form_mao_obra.html', item=mo, view_mode=False)

@auth_bp.post('/excluir-mao-obra/<int:id>')
@login_required
@role_required(PERM_MANAGEMENT)
def excluir_mao_obra(id):
    mo = MaoObra.query.get(id)
    if mo:
        db.session.delete(mo)
        db.session.commit()
    return redirect(url_for('auth.lista_mao_obra'))

#######################################################################################################
####################################################################################################### OBRAS
#######################################################################################################

@auth_bp.get("/lista-obras")
@login_required
def lista_obras():
    # SCOPING:
    user = Usuario.query.get(session.get("user_id"))
    query = Obra.query.order_by(Obra.id.asc())
    
    if user.papel != ROLE_ADMIN:
        meus_ids = [o.id for o in user.obras_permitidas]
        query = query.filter(Obra.id.in_(meus_ids))
        
    resultados = query.all()
    obras_formatadas = []
    for obra_obj in resultados:
        obra_dict = {
            'id': obra_obj.id,
            'nome': obra_obj.nome,
            'cnpj': obra_obj.cnpj,
            'cliente': obra_obj.contratante,
            'cidade': obra_obj.cidade,
            'estado': obra_obj.estado,
            'endereco': obra_obj.endereco,
            'numero': obra_obj.numero,
            'complemento': obra_obj.complemento,
            'bairro': obra_obj.bairro,
            'cep': obra_obj.cep,
            'status': obra_obj.status,
            'frentes_trabalho': obra_obj.frentes_trabalho
        }
        obras_formatadas.append(obra_dict)
    
    return render_template("list_obras.html", opcoes=obras_formatadas, categoria="obra")

@auth_bp.get("/criar-obra")
@login_required
@role_required(PERM_MANAGEMENT) # Apenas Admin e Gestor
def criar_obra():
    usuarios = Usuario.query.filter_by(status=1).all()
    return render_template("form_obra.html", item=None, usuarios=usuarios)

@auth_bp.post("/mudar-status-obras/<int:obraid>")
@login_required
@role_required(PERM_MANAGEMENT)
def toggle_user_obras(obraid):
    # Security scope check
    scope_ids = get_user_scope_ids()
    if scope_ids is not None and obraid not in scope_ids:
        return {"message": "Forbidden"}, 403

    obra = Obra.query.get_or_404(obraid)
    obra.status = not obra.status 
    try:
        db.session.commit()
        return {"message": "Status atualizado com sucesso"}, 200
    except Exception as e:
        db.session.rollback()
        return {"message": f"Erro ao atualizar: {str(e)}"}, 500
    
@auth_bp.route('/gerar-obra', methods=['POST'])
@login_required
@role_required(PERM_MANAGEMENT)
def gerar_obra():
    id_obra = request.form.get("id")
    if id_obra:
        # Security scope
        scope_ids = get_user_scope_ids()
        if scope_ids is not None and int(id_obra) not in scope_ids:
             flash("Sem permissão para editar esta obra", "danger")
             return redirect(url_for('auth.lista_obras'))

    cnpj = request.form.get('cnpj')
    obra_existente = Obra.query.filter_by(cnpj=cnpj).first()
    if obra_existente:
        if not id_obra or str(obra_existente.id) != str(id_obra):
            flash(f"Erro: O CNPJ {cnpj} já está cadastrado.", "danger")
            return redirect(url_for('auth.lista_obras'))

    nome = request.form.get('nome')
    contratante = request.form.get('contratante')
    contrato = request.form.get('contrato')
    id_responsavel = request.form.get('id_responsavel')
    inicio_str = request.form.get('inicio')
    termino_str = request.form.get('termino')
    cep = request.form.get('cep')
    endereco = request.form.get('endereco')
    numero = request.form.get('numero')
    complemento = request.form.get('complemento')
    bairro = request.form.get('bairro')
    cidade = request.form.get('cidade')
    estado = request.form.get('estado')
    status = 1 if request.form.get('status') == 'on' else 0
    frentes_payload = request.form.get('frentes_json')

    try:
        inicio = datetime.strptime(inicio_str, '%Y-%m-%d').date() if inicio_str else None
        termino = datetime.strptime(termino_str, '%Y-%m-%d').date() if termino_str else None

        if id_obra:
            obra = Obra.query.get(id_obra)
            obra.nome = nome
            obra.cnpj = cnpj
            obra.contratante = contratante
            obra.contrato = contrato
            obra.id_responsavel = id_responsavel if id_responsavel else None
            obra.inicio = inicio
            obra.termino = termino
            obra.cep = cep
            obra.endereco = endereco
            obra.numero = numero
            obra.complemento = complemento
            obra.bairro = bairro
            obra.cidade = cidade
            obra.estado = estado
            obra.status = status
            flash("Obra atualizada com sucesso!", "success")
        else:
            obra = Obra(
                nome=nome, cnpj=cnpj, contratante=contratante, contrato=contrato,
                id_responsavel=id_responsavel if id_responsavel else None,
                inicio=inicio, termino=termino,
                cep=cep, endereco=endereco, numero=numero, complemento=complemento,
                bairro=bairro, cidade=cidade, estado=estado, status=status
            )
            db.session.add(obra)
            db.session.flush() 
            flash("Obra cadastrada com sucesso!", "success")

            # Se quem criou foi um Gestor, adiciona automaticamente permissão pra ele
            current_user_obj = Usuario.query.get(session.get("user_id"))
            if current_user_obj.papel == ROLE_GESTOR:
                current_user_obj.obras_permitidas.append(obra)

        if frentes_payload:
            data = json.loads(frentes_payload)
            for f_id in data.get('removidas', []):
                if f_id: Frente_Trabalho.query.filter_by(id_frente_trabalho=f_id, id_obra=obra.id).delete()
            
            for f_nova in data.get('novas', []):
                nova_frente = Frente_Trabalho(
                    id_obra=obra.id,
                    nome_frente=f_nova['nome_frente'],
                    id_responsavel=f_nova['id_responsavel'] if f_nova['id_responsavel'] else None,
                    unidade=f_nova.get('unidade'),
                    qtd_planejada=float(f_nova.get('qtd_planejada')) if f_nova.get('qtd_planejada') else 0,
                    data_inicio=datetime.strptime(f_nova.get('data_inicio'), '%Y-%m-%d').date() if f_nova.get('data_inicio') else None,
                    data_planejada=datetime.strptime(f_nova.get('data_planejada'), '%Y-%m-%d').date() if f_nova.get('data_planejada') else None
                )
                db.session.add(nova_frente)

            for f_edit in data.get('editadas', []):
                frente_existente = Frente_Trabalho.query.get(f_edit['id_frente_trabalho'])
                if frente_existente and frente_existente.id_obra == obra.id:
                    frente_existente.nome_frente = f_edit['nome_frente']
                    frente_existente.id_responsavel = f_edit['id_responsavel'] if f_edit['id_responsavel'] else None
                    frente_existente.unidade = f_edit.get('unidade')
                    frente_existente.qtd_planejada = float(f_edit.get('qtd_planejada')) if f_edit.get('qtd_planejada') else 0
                    frente_existente.data_inicio = datetime.strptime(f_edit.get('data_inicio'), '%Y-%m-%d').date() if f_edit.get('data_inicio') else None
                    frente_existente.data_planejada = datetime.strptime(f_edit.get('data_planejada'), '%Y-%m-%d').date() if f_edit.get('data_planejada') else None

        db.session.commit()
        return redirect(url_for('auth.lista_obras'))

    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao processar a solicitação: {str(e)}", "danger")
        return redirect(url_for('auth.lista_obras'))
    
@auth_bp.get("/editar-obra/<int:id>")
@login_required
@role_required(PERM_MANAGEMENT)
def editar_obra(id):
    # Security scope
    scope_ids = get_user_scope_ids()
    if scope_ids is not None and id not in scope_ids:
        abort(403)

    obra = Obra.query.get_or_404(id)
    frentes = Frente_Trabalho.query.filter_by(id_obra=id).all()
    usuarios = Usuario.query.filter_by(status=1).all() 
    return render_template("form_obra.html", item=obra, frentes=frentes, usuarios=usuarios)

@auth_bp.get("/visualizar-obra/<int:id>")
@login_required
def visualizar_obra(id):
    # Security scope
    scope_ids = get_user_scope_ids()
    if scope_ids is not None and id not in scope_ids:
        flash("Acesso restrito.", "danger")
        return redirect(url_for('auth.lista_obras'))

    item = Obra.query.get_or_404(id) 
    usuarios = Usuario.query.filter_by(status=1).all()
    frentes = Frente_Trabalho.query.filter_by(id_obra=id).all()
    usuario = Usuario.query.order_by(Usuario.nome).all()
    
    return render_template(
        "form_obra.html", 
        item=item, 
        view_mode=True, 
        categoria="obra",
        frentes=frentes,
        usuario=usuario,
        usuarios=usuarios
    )

@auth_bp.post("/obra/toggle-status/<int:id>")
@login_required
@role_required(PERM_MANAGEMENT)
def toggle_obra_status(id):
    # Security scope
    scope_ids = get_user_scope_ids()
    if scope_ids is not None and id not in scope_ids:
        return '', 403

    obra = Obra.query.get_or_404(id)
    if obra.status == 1: obra.status = 0
    else: obra.status = 1
    try:
        db.session.commit()
        return '', 200 
    except Exception:
        db.session.rollback()
        return '', 500
      
#######################################################################################################
####################################################################################################### MEU PERFIL (Todos os users)
#######################################################################################################

@auth_bp.get("/meu-perfil")
@login_required
def meu_perfil():
    user = Usuario.query.get(session.get("user_id"))
    return render_template("configuracoes_perfil.html", current_user=user)

@auth_bp.post("/atualizar-meu-perfil")
@login_required
def atualizar_perfil():
    user = Usuario.query.get(session.get("user_id"))
    nome = request.form.get("nome")
    telefone = request.form.get("telefone") 
    departamento = request.form.get("departamento") 
    
    if user:
        user.nome = nome
        user.departamento = departamento
        if hasattr(user, 'telefone'): user.telefone = telefone
        try:
            db.session.commit()
            session["user_name"] = user.nome
            flash("Perfil atualizado com sucesso!", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Erro: {str(e)}", "danger")
    return redirect(url_for("auth.meu_perfil"))

@auth_bp.post("/alterar-minha-senha")
@login_required
def alterar_minha_senha():
    senha_atual = request.form.get("senha_atual")
    nova_senha = request.form.get("nova_senha")
    confirmar_senha = request.form.get("confirmar_senha")
    
    if nova_senha != confirmar_senha:
        flash("A confirmação da nova senha não confere.", "danger")
        return redirect(url_for("auth.meu_perfil"))
        
    user = Usuario.query.get(session.get("user_id"))
    if not user or not check_password_hash(user.senha, senha_atual):
        flash("A senha atual está incorreta.", "danger")
        return redirect(url_for("auth.meu_perfil"))
        
    try:
        user.set_senha(nova_senha)
        db.session.commit()
        flash("Senha alterada com sucesso! Use a nova senha no próximo login.", "success")
    except Exception:
        db.session.rollback()
        flash("Erro ao alterar senha.", "danger")
    return redirect(url_for("auth.meu_perfil"))

#######################################################################################################
####################################################################################################### EASTER EGG
#######################################################################################################

@auth_bp.get("/dev-access")
def creator_secret():
    perfil = {
        "nome": "Edson Rodrigues",
        "role": "Fullstack Developer & Tech Planner",
        "stack": ["Python", "Microsoft 365", "SQL", "JavaScript", "Java", "HTML/CSS"],
        "projetos": ["Sistema RDO", "Automação de Relatórios", "Dashboard Interativo"],
        "local": "São Paulo, SP",
        "status": "Construindo o futuro, linha por linha.",
        "links": {
            "linkedin": "https://www.linkedin.com/in/edson-rodrigues-5a1a46345/",
            "github": "https://github.com/werneckx", 
            "instagram": "https://instagram.com/werneckx", 
            "email": "mailto:er4273270@gmail.com"
        }
    }
    return render_template("criador.html", dev=perfil)

#######################################################################################################
####################################################################################################### VALIDAÇÃO PUBLICA (PÚBLICO)
#######################################################################################################

def normalizar_texto(texto):
    if not texto: return ""
    nfkd_form = unicodedata.normalize('NFKD', str(texto))
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)]).lower().strip()

def extrair_dados_pdf_fitz(pdf_bytes):
    if not fitz: return []
    dados = []
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        for i, page in enumerate(doc):
            palavras = page.get_text("words")
            for p in palavras:
                text_norm = normalizar_texto(p[4])
                if not text_norm: continue
                dados.append({
                    'text': text_norm,
                    'text_raw': p[4],
                    'page': i,
                    'rect': fitz.Rect(p[0], p[1], p[2], p[3])
                })
    except Exception as e: print(f"Erro extração fitz: {e}")
    return dados

def gerar_diff_visual(dados_orig, dados_up):
    diff_cards = []
    rects_to_highlight_orig = []
    rects_to_highlight_up = []
    
    textos_orig = [d['text'] for d in dados_orig]
    textos_up = [d['text'] for d in dados_up]
    
    matcher = difflib.SequenceMatcher(None, textos_orig, textos_up)
    
    ignore_list = ["criado:", "modificado:", "impressão:", "gerado", "id:", "hash:", "ip:", "rev."]
    def eh_ignoravel(t): return any(ign in t.lower() for ign in ignore_list)

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal': continue
        frag_orig_list = [dados_orig[x]['text_raw'] for x in range(i1, i2)]
        frag_up_list = [dados_up[x]['text_raw'] for x in range(j1, j2)]
        frag_orig_str = " ".join(frag_orig_list)
        frag_up_str = " ".join(frag_up_list)
        if eh_ignoravel(frag_orig_str) or eh_ignoravel(frag_up_str): continue
        if frag_orig_str.replace(" ", "") == frag_up_str.replace(" ", ""): continue
        
        if tag == 'replace':
            diff_cards.append({'tipo': 'alteracao', 'original': frag_orig_str, 'enviado': frag_up_str})
            rects_to_highlight_orig.extend([d for d in dados_orig[i1:i2]])
            rects_to_highlight_up.extend([d for d in dados_up[j1:j2]])
        elif tag == 'delete':
            diff_cards.append({'tipo': 'remocao', 'original': frag_orig_str, 'enviado': ""})
            rects_to_highlight_orig.extend([d for d in dados_orig[i1:i2]])
        elif tag == 'insert':
            diff_cards.append({'tipo': 'adicao', 'original': "", 'enviado': frag_up_str})
            rects_to_highlight_up.extend([d for d in dados_up[j1:j2]])
            
    return diff_cards, rects_to_highlight_orig, rects_to_highlight_up

def aplicar_highlights(pdf_bytes, lista_dados, color):
    if not fitz or not lista_dados: return pdf_bytes
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        por_pagina = {}
        for item in lista_dados:
            p = item['page']
            if p not in por_pagina: por_pagina[p] = []
            por_pagina[p].append(item['rect'])
        for page_idx, rects in por_pagina.items():
            if page_idx < len(doc):
                page = doc[page_idx]
                for r in rects:
                    annot = page.add_highlight_annot(r)
                    annot.set_colors(stroke=color)
                    annot.update()
        output = BytesIO()
        doc.save(output)
        return output.getvalue()
    except Exception: return pdf_bytes

@auth_bp.route("/validar-documento", methods=["GET", "POST"])
def validar_documento_publico():
    from app.models.rdo import RDO, Assinatura
    try:
        from pypdf import PdfReader
        from io import BytesIO
    except ImportError: PdfReader = None
    
    resultado = None
    erro = None
    hash_buscado = ""
    status_auditoria = "pendente"
    diff_data = [] 
    pdf_original_b64 = None
    pdf_enviado_b64 = None
    texto_pdf_enviado = ""
    bytes_original = None
    bytes_enviado = None

    if request.method == 'POST':
        if 'pdf_file' in request.files and request.files['pdf_file'].filename != '':
            if PdfReader is None:
                 erro = "Erro interno: Biblioteca 'pypdf' não instalada."
            else:
                try:
                    arquivo_pdf = request.files['pdf_file']
                    bytes_enviado = arquivo_pdf.read()
                    stream_enviado = BytesIO(bytes_enviado)
                    leitor = PdfReader(stream_enviado)
                    for pagina in leitor.pages: texto_pdf_enviado += pagina.extract_text() + "\n"
                    texto_norm = normalizar_texto(texto_pdf_enviado)
                    match = re.search(r"id:\s*([a-fa-f0-9]{64})", texto_norm)
                    if match: hash_buscado = match.group(1)
                    else:
                        match_solto = re.search(r"([a-fa-f0-9]{64})", texto_norm)
                        if match_solto: hash_buscado = match_solto.group(1)
                        else: erro = "Código de autenticidade (Hash) não encontrado no arquivo."
                    pdf_enviado_b64 = base64.b64encode(bytes_enviado).decode('utf-8')
                except Exception as e: erro = f"Erro ao processar arquivo: {str(e)}"

    if hash_buscado:
        assinatura = Assinatura.query.filter_by(hash_documento=hash_buscado).first()
        if assinatura:
            if assinatura.status == 'Aprovado':
                rdo = assinatura.rdo
                if texto_pdf_enviado:
                    try:
                        bytes_original = render_rdo_pdf(rdo.id)
                        if fitz:
                            dados_orig = extrair_dados_pdf_fitz(bytes_original)
                            dados_up = extrair_dados_pdf_fitz(bytes_enviado)
                            diff_data, rects_orig, rects_up = gerar_diff_visual(dados_orig, dados_up)
                            if rects_orig: bytes_original = aplicar_highlights(bytes_original, rects_orig, (1, 0, 0))
                            if rects_up: bytes_enviado = aplicar_highlights(bytes_enviado, rects_up, (0, 1, 0))
                        
                        status_auditoria = "aprovado" if len(diff_data) == 0 else "alerta"
                        pdf_original_b64 = base64.b64encode(bytes_original).decode('utf-8')
                        pdf_enviado_b64 = base64.b64encode(bytes_enviado).decode('utf-8')
                    except Exception as e:
                        print(f"Erro Auditoria: {e}")
                        status_auditoria = "erro"
                
                resultado = {
                    "valido": True,
                    "rdo_id": rdo.id_sequencial,
                    "revisao": rdo.id_revisao,
                    "obra": rdo.obra.nome,
                    "data_rdo": rdo.data,
                    "assinante_nome": assinatura.usuario.nome,
                    "assinante_papel": assinatura.usuario.papel,
                    "data_assinatura": assinatura.criado,
                    "hash_completo": assinatura.hash_documento,
                    "status_auditoria": status_auditoria,
                    "diff_data": diff_data,
                    "pdf_original_b64": pdf_original_b64,
                    "pdf_enviado_b64": pdf_enviado_b64
                }
            else: erro = "Este documento foi invalidado no sistema."
        else: erro = "Código de autenticidade (Hash) não encontrado na base de dados."

    return render_template("public_validacao.html", resultado=resultado, erro=erro, hash_buscado=hash_buscado)