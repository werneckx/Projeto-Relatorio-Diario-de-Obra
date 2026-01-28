import base64
import hashlib
from math import e
import os
from flask import Blueprint, Config, abort, json, render_template, request, redirect, url_for, flash, session, send_file
from itsdangerous import SignatureExpired, URLSafeTimedSerializer
from werkzeug.security import check_password_hash
from app import db
from app import db, login_manager
from flask_login import UserMixin, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from app.models import usuario
from app.models import rdo
from app.models.empresa import Empresa
from app.models.lista_opcoes import Clima
from app.models.obra import Frente_Trabalho, Obra
from app.models.rdo import RDO, Assinatura, Equipamentos
from app.utils.rdo_pdf import regenerar_pdf_rdo
from app.utils.qrcode_utils import gerar_qrcode_b64
from sqlalchemy import extract, func, or_
from datetime import date, datetime, timedelta, timezone
from functools import wraps
from sqlalchemy.orm import aliased
from flask import request, jsonify
from app import db
from app.models.obra import Frente_Trabalho
from werkzeug.utils import secure_filename
from flask import make_response
from app.utils.pdf_service import render_rdo_pdf, render_rdo_pdf_compact
import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from werkzeug.utils import secure_filename

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

# Configuração permitida de extensões
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Página Inicial do Blueprint (Redirecionamento)
@auth_bp.get("/")
def index():
    if "user_id" in session:
        return redirect(url_for("auth.inicio"))
    return redirect(url_for("auth.login"))

#######################################################################################################
####################################################################################################### Login e Logout
#######################################################################################################

# Decorator para proteger rotas que exigem login
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            # Melhoria: usa flash message para indicar a necessidade de login
            flash("Você precisa estar logado para acessar esta página.", "warning")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)

    return decorated

# Tela de Login (Renderização)
@auth_bp.get("/login")
def login():
    return render_template("login.html")

# Tela de Login (Logar)
@auth_bp.post("/login")
def login_post():
    email = request.form.get("email")
    senha = request.form.get("senha")

    # Importar Usuario aqui, apenas onde é usado na rota
    from app.models.usuario import Usuario

    # 1. Adicionar o filtro 'ativo=1'
    user = Usuario.query.filter_by(email=email, status=1).first()

    # 2. Verificar se o usuário existe e se a senha está correta
    if not user or not check_password_hash(user.senha, senha):
        flash("E-mail, senha ou status de usuário inválido.", "error")
        return redirect(url_for("auth.login"))
    
    session["user_id"] = user.id
    session["user_name"] = user.nome
    session["user_email"] = user.email
    session["user_role"] = user.papel

    flash("Bem vindo " + user.nome, "success")

    return redirect(url_for("auth.inicio"))

# Logout
@auth_bp.get("/logout")
def logout():
    session.clear()
    flash("Você foi desconectado com sucesso.", "info")
    return redirect(url_for("auth.login"))

# --- ROTAS DE RECUPERAÇÃO DE SENHA ---

@auth_bp.route("/esqueci-senha", methods=["GET", "POST"])
def esqueci_senha():
    # Busca o administrador para exibir no template como contato de suporte
    from app.models.usuario import Usuario
    admin_contato = Usuario.query.filter_by(papel='Admin').first()

    if request.method == "GET":
        return render_template("esqueci_senha.html", admin=admin_contato)
    
    email = request.form.get("email")
    user = Usuario.query.filter_by(email=email).first()
    
    if user:
        # Gera token seguro válido por 1 hora
        s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        token = s.dumps(email, salt='recuperacao-senha')
        
        # Link para resetar
        link = url_for('auth.redefinir_senha', token=token, _external=True)
        
        # AQUI VOCÊ DEVE INTEGRAR SEU SERVIÇO DE EMAIL
        print(f"========================================")
        print(f"LINK DE RECUPERAÇÃO PARA {email}:")
        print(f"{link}")
        print(f"========================================")
        
        flash("Um link de recuperação foi enviado para seu e-mail.", "success")
    else:
        # Por segurança, não informamos se o email não existe
        flash("Se o e-mail estiver cadastrado, você receberá um link.", "success")
        
    # Mantém o admin no render mesmo após o POST em caso de redirect ou render
    return redirect(url_for("auth.login"))

@auth_bp.route("/redefinir-senha/<token>", methods=["GET", "POST"])
def redefinir_senha(token):
    s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        email = s.loads(token, salt='recuperacao-senha', max_age=3600) # 1 hora de validade
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
        
    from app.models.usuario import Usuario
    user = Usuario.query.filter_by(email=email).first()
    
    if user:
        user.set_senha(nova_senha)
        db.session.commit()
        flash("Sua senha foi redefinida com sucesso! Faça login.", "success")
        return redirect(url_for("auth.login"))
        
    flash("Erro ao redefinir senha.", "danger")
    return redirect(url_for("auth.login"))

#######################################################################################################
####################################################################################################### Inicio
#######################################################################################################

# Página inicio
@auth_bp.get("/inicio")
@login_required
def inicio():
    from app.models.obra import Obra
    from app.models.rdo import RDO, RDOMaoObra, TagsOcorrencias
    
    # Data de referência
    hoje = date.today()
    ano_atual = hoje.year
    mes_atual = hoje.month

    # --- 1. KPIs PRINCIPAIS ---
    
    # KPI 1: Obras Ativas (Status 1)
    kpi_obras = Obra.query.filter_by(status=1).count()
    
    # KPI 2: RDOs Pendentes (Geral)
    kpi_pendentes = RDO.query.filter_by(status='Pendente').count()
    
    # KPI 3: Efetivo Total (Hoje)
    # Soma a quantidade própria + terceirizada de todos os RDOs com data de hoje
    kpi_efetivo = db.session.query(
        func.sum(RDOMaoObra.quantidade_propria + RDOMaoObra.quantidade_terceirizada)
    ).join(RDO).filter(RDO.data == hoje).scalar() or 0
    
    # KPI 4: Ocorrências (No Mês Atual)
    # Conta quantos registros de ocorrências existem em RDOs deste mês/ano
    kpi_ocorrencias = db.session.query(func.count(TagsOcorrencias.id_tag_rdo))\
        .join(RDO)\
        .filter(extract('year', RDO.data) == ano_atual)\
        .filter(extract('month', RDO.data) == mes_atual)\
        .scalar() or 0

    # --- 2. DADOS PARA INTERATIVIDADE (POWER BI STYLE) ---
    # Buscamos metadados de todos os RDOs do ano para enviar ao Frontend (Chart.js).
    # O JavaScript fará a filtragem dinâmica (clique no mês filtra status, clique no status filtra mês).
    raw_rdos = db.session.query(RDO.id, RDO.status, RDO.data).filter(extract('year', RDO.data) == ano_atual).all()
    
    # Serializa para JSON (Lista de dicionários simples)
    dados_graficos_json = [
        {
            'status': rdo.status,
            'mes': rdo.data.month, # Inteiro 1 a 12
            'data_iso': rdo.data.isoformat()
        } 
        for rdo in raw_rdos
    ]

    # --- 3. TABELA DE RESUMO (Últimos Registros) ---
    ultimos_rdos = RDO.query.order_by(RDO.data.desc(), RDO.id.desc()).limit(5).all()

    return render_template(
        "inicio.html",
        # KPIs
        kpi_obras=kpi_obras,
        kpi_pendentes=kpi_pendentes,
        kpi_efetivo=int(kpi_efetivo),
        kpi_ocorrencias=kpi_ocorrencias,
        
        # Tabelas e Gráficos
        ultimos_rdos=ultimos_rdos,
        dados_graficos_json=dados_graficos_json # Dados brutos para o Chart.js manipular
    )
    
#######################################################################################################
####################################################################################################### Empresa
#######################################################################################################

# Injetar nome da empresa globalmente
@auth_bp.app_context_processor
def inject_company_info():
    from app.models.empresa import Empresa
    nome_empresa = Empresa.query.first().nome_empresa if Empresa.query.first() else "Não definido" 
    
    return dict(nome_empresa_global=nome_empresa)

# Página Empresa (Configurações)
@auth_bp.get("/empresa")
@login_required
def empresa():
    from app.models.empresa import Empresa
    config_data = {
        'nome_empresa': Empresa.query.first().nome_empresa if Empresa.query.first() else '',
        'logo_path': 'logo/logo.png',
        'icone_path': 'logo/icone.png'
    } # Carrega dados da empresa do banco de dados
    return render_template('empresa.html', config_data=config_data, view_mode=True)

# Salvar Configurações da Empresa
@auth_bp.route('/salvar-empresa', methods=['POST'])
def salvar_empresa():
    nome_empresa = request.form.get('nome_empresa')
    logo_file = request.files.get('logo_empresa')
    icone_file = request.files.get('icone_empresa')

    try:
        # 1. Atualizar Nome no Banco de Dados
        db.session.query(Empresa).update({'nome_empresa': nome_empresa})
        
        upload_folder = os.path.join(current_app.root_path, 'static', 'logo')
        
        # Garante que a pasta de destino existe
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)

        # 2. Processar Logotipo (logo.png)
        if logo_file and logo_file.filename != '':
            if allowed_file(logo_file.filename):
                logo_path = os.path.join(upload_folder, "logo.png")
                # O save do Flask sobrescreve arquivos existentes por padrão
                logo_file.save(logo_path)
            else:
                flash('Extensão de logotipo não permitida (use PNG, JPG ou GIF).', 'danger')
                return redirect(url_for('auth.empresa'))

        # 3. Processar Ícone/Favicon (icone.png)
        if icone_file and icone_file.filename != '':
            if allowed_file(icone_file.filename):
                icone_path = os.path.join(upload_folder, "icone.png")
                icone_file.save(icone_path)
            else:
                flash('Extensão de ícone não permitida (use PNG, ICO ou JPG).', 'danger')
                return redirect(url_for('auth.empresa'))

        # Commit das alterações de texto no banco
        db.session.commit()
        flash('Configurações da empresa atualizadas com sucesso!', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao salvar configurações: {str(e)}', 'danger')

    return redirect(url_for('auth.empresa'))

#######################################################################################################
####################################################################################################### PDF
#######################################################################################################

# Gerar PDF RDO
@auth_bp.get("/gerar-pdf/<int:rdo_id>")
@login_required
def gerar_pdf_rdo_view(rdo_id):
    try:
        # Gera os bytes do PDF
        pdf_content = render_rdo_pdf(rdo_id)
        
        # Cria a resposta HTTP com os headers corretos
        response = make_response(pdf_content)
        response.headers['Content-Type'] = 'application/pdf'
        
        # 'inline' abre no navegador. 'attachment' forçaria o download.
        filename = f"RDO_{rdo_id}.pdf"
        response.headers['Content-Disposition'] = f'inline; filename={filename}'
        
        return response
        
    except Exception as e:
        # Log do erro para debug
        print(f"Erro ao gerar PDF: {e}")
        flash("Erro ao gerar o PDF. Verifique se as imagens e dados estão corretos.", "danger")
        return redirect(url_for('auth.visualizar_rdo', rdo_id=rdo_id))

# Gerar PDF RDO Compacto
@auth_bp.get("/gerar-pdf-compacto/<int:rdo_id>")
@login_required
def gerar_pdf_rdo_compacto_view(rdo_id):
    try:
        # Gera os bytes do PDF
        pdf_content = render_rdo_pdf_compact(rdo_id)
        
        # Cria a resposta HTTP com os headers corretos
        response = make_response(pdf_content)
        response.headers['Content-Type'] = 'application/pdf'
        
        # 'inline' abre no navegador. 'attachment' forçaria o download.
        filename = f"RDO_{rdo_id}.pdf"
        response.headers['Content-Disposition'] = f'inline; filename={filename}'
        
        return response
        
    except Exception as e:
        # Log do erro para debug
        print(f"Erro ao gerar PDF: {e}")
        flash("Erro ao gerar o PDF. Verifique se as imagens e dados estão corretos.", "danger")
        return redirect(url_for('auth.visualizar_rdo', rdo_id=rdo_id))

#######################################################################################################
####################################################################################################### RDO
#######################################################################################################

# Criar RDO
@auth_bp.get("/criar-rdo")
@login_required
def criar_rdo():
    from app.models.obra import Obra, Frente_Trabalho 
    from app.models.lista_opcoes import Clima 
    from app.models.usuario import Usuario
    from app.models.lista_opcoes import MaoObra, Equipamento, TagOcorrencia, Clima

    # Filtra apenas obras ATIVAS (assumindo 1 para ativo)
    obras = Obra.query.filter_by(status=1).all()
    
    # Essas são as variáveis que o seu JS está tentando ler com | tojson
    mao_de_obra_options = [{"id": m.id, "nome": m.nome} for m in MaoObra.query.all()]
    equipamentos_options = [{"id": e.id, "nome": e.nome} for e in Equipamento.query.all()]
    tags_options = [{"id": t.id, "nome": t.nome} for t in TagOcorrencia.query.all()]

    clima = Clima.query.all()
    # Enviamos todas as frentes; o JavaScript no seu HTML já filtra por obra
    
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

# API Obra JSON
@auth_bp.get("/api/obra/<int:id>")
@login_required
def get_obra_api(id):
    from app.models.obra import Obra, Frente_Trabalho
    from flask import jsonify # Garanta que jsonify está importado
    
    # 1. Busca a obra com segurança (retorna 404 se não existir)
    obra = Obra.query.get_or_404(id)
    
    # 2. Busca as frentes de trabalho vinculadas
    frentes = Frente_Trabalho.query.filter_by(id_obra=id).all()
    
    # 3. Formatação segura de datas (previne erro se data for None)
    data_inicio_fmt = obra.inicio.strftime('%d/%m/%Y') if obra.inicio else "-"
    data_inicio_iso = obra.inicio.isoformat() if obra.inicio else ""
    data_fim_fmt = obra.termino.strftime('%d/%m/%Y') if obra.termino else "-"
    data_fim_iso = obra.termino.isoformat() if obra.termino else ""

    # 4. Acesso seguro ao relacionamento Responsável
    # O modelo define: responsavel = db.relationship('Usuario', ...)
    nome_responsavel = obra.responsavel.nome if obra.responsavel else "Não definido"

    # 5. Montagem da lista de frentes
    lista_frentes = []
    for f in frentes:
        # O modelo Frente_Trabalho também usa 'responsavel'
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

    # 6. Retorno do JSON com os nomes de campos corretos
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

# API Frente de Trabalho JSON
@auth_bp.get("/api/frente/<int:id>")
@login_required
def get_frente_api(id):
    from app.models.obra import Frente_Trabalho
    frente = Frente_Trabalho.query.get_or_404(id)
    return jsonify({
        "responsavel": frente.responsavel_tecnico.nome if frente.responsavel_tecnico else None
        
    })

# Gerar ou Editar RDO (POST)
@auth_bp.post("/gerar-rdo")
@login_required
def gerar_rdo():
    from app.models.rdo import RDO, RDOMaoObra, Atividades, Equipamentos, Fotos, TagsOcorrencias, Assinatura
    from app.models.lista_opcoes import Equipamento
    from flask import current_app
    from app import db
    
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

        # Dados Básicos
        rdo_id_original = _get_int("rdo_id")
        id_obra = _get_int("obra_id")
        data_rdo_str = request.form.get("data_rdo")
        data_rdo = datetime.strptime(data_rdo_str, '%Y-%m-%d').date() if data_rdo_str else date.today()
        
        # --- Lógica Principal ---
        if rdo_id_original:
            # ==============================
            # UPDATE (EDIÇÃO / NOVA REVISÃO)
            # ==============================
            item_rdo = RDO.query.get(rdo_id_original)
            if not item_rdo:
                abort(404, description="RDO não encontrado para edição.")
            
            # 1. Incrementa a Revisão
            rev_atual = item_rdo.id_revisao if item_rdo.id_revisao is not None else 0
            item_rdo.id_revisao = rev_atual + 1
            
            # 2. Reseta o status do RDO para Pendente
            item_rdo.status = "Pendente"

            # 3. REINICIAR WORKFLOW (Resetar assinaturas existentes)
            assinaturas_existentes = Assinatura.query.filter_by(id_rdo=item_rdo.id).all()
            
            for ass in assinaturas_existentes:
                # Reseta TUDO para Pendente, inclusive o editor atual
                ass.img_assinatura = None
                ass.motivo_rejeicao = None
                ass.status = 'Pendente'
                ass.criado = None # Limpa a data de assinatura
                ass.ip_endereco = None # Limpa o IP
                ass.validacao = None # Limpa a validacao

        else:
            # ==============================
            # INSERT (NOVO RDO)
            # ==============================
            # CORREÇÃO: Usar MAX(id_sequencial) em vez de COUNT para evitar erros se houver exclusões
            # Buscamos o maior id_sequencial usado nesta obra, independente de revisão ou exclusão
            max_seq = db.session.query(func.max(RDO.id_sequencial)).filter_by(id_obra=id_obra).scalar()
            
            # Se não houver nenhum, começa do 1. Se houver, soma 1.
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
        item_rdo.data = data_rdo
        item_rdo.modificado = now_br
        item_rdo.id_modificado_por = current_user_id
        item_rdo.comentarios_gerais = request.form.get("comentarios_gerais")
        # ALTERAÇÃO AQUI: Usando _get_float para converter corretamente
        item_rdo.qtd_produzida = _get_float("qtd_produzida")
        
        # Horários
        item_rdo.hora_entrada = _get_time("hora_entrada")
        item_rdo.hora_saida = _get_time("hora_saida")
        item_rdo.intervalo_entrada = _get_time("intervalo_entrada")
        item_rdo.intervalo_saida = _get_time("intervalo_saida")
        
        if not rdo_id_original:
            db.session.add(item_rdo)
        
        db.session.flush()

        # [Criação Apenas] Adiciona assinatura do criador se não existir
        # Nota: Na criação (novo), geralmente o criador já nasce aprovado.
        # Se você quiser que até na criação ele tenha que ir lá assinar depois, 
        # mude status='Aprovado' para 'Pendente' aqui também.
        if not rdo_id_original: 
            existe_ass = Assinatura.query.filter_by(id_rdo=item_rdo.id, id_usuario=current_user_id).first()
            if not existe_ass:
                assinatura_criador = Assinatura(
                    id_rdo=item_rdo.id,
                    id_usuario=current_user_id,
                    ordem=1,
                    status='Pendente', # Mantive Aprovado só na CRIAÇÃO DO ZERO
                    criado=now_br,
                    ip_endereco=request.remote_addr
                )
                db.session.add(assinatura_criador)

        # --- Limpeza de filhos para recriação ---
        if rdo_id_original:
            Atividades.query.filter_by(id_rdo=item_rdo.id).delete()
            RDOMaoObra.query.filter_by(id_rdo=item_rdo.id).delete()
            Equipamentos.query.filter_by(id_rdo=item_rdo.id).delete()
            TagsOcorrencias.query.filter_by(id_rdo=item_rdo.id).delete()

        # --- 1. Atividades ---
        descricoes = request.form.getlist("atividade_descricao[]")
        status_list = request.form.getlist("atividade_status[]")
        for i, desc in enumerate(descricoes):
            if desc and desc.strip():
                st = status_list[i] if i < len(status_list) else "Não iniciada"
                nova_atv = Atividades(id_rdo=item_rdo.id, descricao=desc, status=st)
                db.session.add(nova_atv)

        # --- 2. Mão de Obra ---
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
                nova_mo = RDOMaoObra(
                    id_rdo=item_rdo.id, nome_funcao=mo_func,
                    quantidade_propria=qp, quantidade_terceirizada=qt, tempo=tempo_obj
                )
                db.session.add(nova_mo)

        # --- 3. Equipamentos ---
        eq_ids = request.form.getlist("eq_id[]")
        eq_qts = request.form.getlist("eq_qtd[]")
        for i, eid in enumerate(eq_ids):
            if eid:
                qtd = int(eq_qts[i]) if i < len(eq_qts) and eq_qts[i] else 0
                eq_obj = Equipamento.query.get(eid)
                novo_eq = Equipamentos(
                    id_rdo=item_rdo.id, id_equipamento_lista=eid,
                    nome_equipamento=eq_obj.nome if eq_obj else "", quantidade=qtd
                )
                db.session.add(novo_eq)

        # --- 4. Ocorrências ---
        oc_tags = request.form.getlist("oc_tag[]")
        oc_descs = request.form.getlist("oc_desc[]")
        oc_tempos = request.form.getlist("oc_tempo_parado[]")

        for i, tid in enumerate(oc_tags):
            if not tid: continue  # Pula se o ID da tag for vazio

            # Inicia variável do tempo como None
            tempo_obj = None
            
            # Pega o valor do input (string HH:MM ou vazio)
            tempo_str = oc_tempos[i] if i < len(oc_tempos) else None
            
            # Tenta converter se houver string
            if tempo_str and tempo_str.strip():
                try:
                    tempo_obj = datetime.strptime(tempo_str, '%H:%M').time()
                except ValueError:
                    tempo_obj = None  # Formato inválido ou vazio
            
            # Descrição
            desc = oc_descs[i] if i < len(oc_descs) else ""

            # Cria objeto com o campo tempo_parado
            nova_oc = TagsOcorrencias(
                id_rdo=item_rdo.id, 
                id_tag_lista=tid, 
                descricao=desc,
                tempo_parado=tempo_obj  # Correção aplicada aqui
            )
            db.session.add(nova_oc)

        # --- 5. Fotos ---
        UPLOAD_FOLDER = os.path.join(current_app.root_path, 'static', 'uploads', 'rdo')
        if not os.path.exists(UPLOAD_FOLDER):
            os.makedirs(UPLOAD_FOLDER)
            
        # --- [CORREÇÃO] 5.1 Processar EXCLUSÕES de fotos ---
        # Deve ser feito ANTES de atualizar legendas para evitar conflitos
        # --- 5.1 Processar EXCLUSÕES de fotos ---
        ids_remover = request.form.getlist("fotos_remover[]")
        if ids_remover:
            for id_rem in ids_remover:
                try:
                    if not id_rem: continue # Pula se o ID estiver vazio
                    
                    # Busca pelo id_foto correto
                    foto_del = Fotos.query.get(int(id_rem))
                    
                    # Garante que a foto pertence ao RDO atual (segurança)
                    if foto_del and foto_del.id_rdo == item_rdo.id:
                        # Remover arquivo físico
                        try:
                            caminho_arquivo = os.path.join(UPLOAD_FOLDER, foto_del.arquivo)
                            if os.path.exists(caminho_arquivo):
                                os.remove(caminho_arquivo)
                        except Exception as e_file:
                            print(f"Erro ao deletar arquivo físico da foto {id_rem}: {e_file}")
                        
                        # Remove do banco
                        db.session.delete(foto_del)
                except ValueError:
                    print(f"Erro de conversão de ID: {id_rem}")
                except Exception as e:
                    print(f"Erro ao excluir foto {id_rem}: {e}")
            
        # --- 5.2 ATUALIZAÇÃO DE LEGENDAS EXISTENTES ---
        ids_existentes = request.form.getlist("fotos_existentes_ids[]")
        comentarios_existentes = request.form.getlist("comentarios_existentes_list[]")
        
        # Usamos ZIP para garantir paridade entre ID e Comentário
        for foto_id_str, nova_legenda in zip(ids_existentes, comentarios_existentes):
            try:
                if not foto_id_str: continue

                foto_id = int(foto_id_str)
                foto_obj = Fotos.query.get(foto_id)
                
                # Verificação de segurança: a foto pertence a este RDO?
                if foto_obj and foto_obj.id_rdo == item_rdo.id:
                    # Só atualiza se mudou, evita writes desnecessários
                    if foto_obj.comentario != nova_legenda:
                        foto_obj.comentario = nova_legenda
                        db.session.add(foto_obj)
            except Exception as e:
                print(f"Erro ao atualizar legenda da foto {foto_id_str}: {e}")

        # PROCESSAMENTO DE NOVAS FOTOS (MANTIDO)
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
                    nova_foto = Fotos(id_rdo=item_rdo.id, arquivo=novo_nome, comentario=comentario)
                    db.session.add(nova_foto)
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
    
# Visualizar RDO (redireciona)
@auth_bp.get("/visualizar-rdo/<int:rdo_id>")
@login_required
def visualizar_rdo(rdo_id):
    from app.models.rdo import RDO, RDOMaoObra, Equipamentos, Assinatura
    from app.models.obra import Obra, Frente_Trabalho
    from app.models.lista_opcoes import Clima, MaoObra, Equipamento, TagOcorrencia
    from app.models.usuario import Usuario

    item = RDO.query.get_or_404(rdo_id)
    
    # Dados auxiliares
    mao_de_obra_options = [{"id": m.id, "nome": m.nome} for m in MaoObra.query.all()]
    equipamentos_options = [{"id": e.id, "nome": e.nome} for e in Equipamento.query.all()]
    tags_options = [{"id": t.id, "nome": t.nome} for t in TagOcorrencia.query.all()]
    
    # IMPORTANTE: Carregar as assinaturas para exibir o status
    assinaturas = Assinatura.query.filter_by(id_rdo=rdo_id).order_by(Assinatura.ordem).all()
    
    # Carregar usuários da obra para o Modal de Workflow (Apenas ATIVOS)
    if item.id_obra:
        # Filtra por Obra E Status Ativo (assumindo que True/1 é ativo)
        usuarios_obra = Usuario.query.filter(
            Usuario.obras_permitidas.any(id=item.id_obra),
            Usuario.status == True 
        ).all()
        
        # Fallback: Se não houver usuários específicos vinculados, pega todos os ativos
        if not usuarios_obra:
            usuarios_obra = Usuario.query.filter_by(status=True).all()
    else:
        usuarios_obra = Usuario.query.filter_by(status=True).all()
        
    url_rdo = url_for('auth.visualizar_rdo', rdo_id=rdo_id, _external=True)
    qr_code_img = gerar_qrcode_b64(url_rdo)

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

# Editar RDO
@auth_bp.get("/editar-rdo/<int:rdo_id>")
@login_required
def editar_rdo(rdo_id):
    from app.models.rdo import RDO, Atividades, RDOMaoObra, Assinatura, Equipamentos, Fotos, TagsOcorrencias
    from app.models.obra import Frente_Trabalho, Obra
    from app.models.lista_opcoes import Clima, MaoObra, Equipamento, TagOcorrencia
    from app.models.usuario import Usuario
    from app import db

    # 1. Busca o RDO ou retorna 404
    item = RDO.query.get_or_404(rdo_id)

    # 2. Busca utilizadores vinculados a esta obra para o fluxo de assinatura
    usuarios_obra = Usuario.query.filter(Usuario.obras_permitidas.any(id=item.id_obra)).all()

    
    # 3. Lógica para o Grid de Assinaturas Dinâmico
    assinaturas_realizadas = Assinatura.query.filter_by(id_rdo=rdo_id).all()
    ids_usuarios_que_assinaram = [a.id_usuario for a in assinaturas_realizadas]

    lista_assinaturas_status = []
    for u in usuarios_obra:
        ass_obj = next((a for a in assinaturas_realizadas if a.id_usuario == u.id), None)
        # Exibe no grid o emitente, quem já assinou ou perfis de gestão
        if u.id == item.id_criado_por or u.id in ids_usuarios_que_assinaram or u.papel in ['Admin', 'Engenheiro', 'Supervisor']:
            lista_assinaturas_status.append({
                "usuario": u,
                "assinado": True if ass_obj else False,
                "dados_assinatura": ass_obj
            })

    # 4. Dados pré-carregados do RDO para edição
    # O SQLAlchemy carrega os relacionamentos definidos no model RDO (maos_obra, equipamentos, atividades, etc.)
    # Se o seu template usa loops como 'for linha in maos_obra_salvas', passamos aqui:
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
        # Tabelas de referência para preencher os selects
        obras=Obra.query.filter_by(status=1).all(),
        frente_trabalho=frente_trabalho,
        clima=Clima.query.all(),
        
        # Dados específicos já salvos neste RDO
        maos_obra_salvas=maos_obra_salvas,
        equipamentos_salvos=equipamentos_salvos,
        atividades_salvas=atividades_salvas,
        ocorrencias_salvas=ocorrencias_salvas,
        fotos_salvas=fotos_salvas,
        
        # Opções para os componentes de adição (Modais/Autocomplete)
        mao_de_obra_options=[{"id": m.id, "nome": m.nome} for m in MaoObra.query.all()],
        equipamentos_options=[{"id": e.id, "nome": e.nome} for e in Equipamento.query.all()],
        tags_options=[{"id": t.id, "nome": t.nome} for t in TagOcorrencia.query.all()],
        
        # Assinaturas e Utilizadores
        usuarios_obra=usuarios_obra,
        lista_assinaturas_status=lista_assinaturas_status,
        assinaturas=assinaturas_realizadas,
        
        # Classes dos modelos (caso o template precise instanciar algo ou referenciar tipos)
        Atividades=Atividades,
        RDOMaoObra=RDOMaoObra,
        Equipamentos=Equipamentos,
        Fotos=Fotos,
        TagsOcorrencias=TagsOcorrencias
    )

# Excluir RDO
@auth_bp.post("/excluir-rdo/<int:rdo_id>")
@login_required
def excluir_rdo(rdo_id):
    from app.models.rdo import RDO, Atividades, RDOMaoObra, Equipamentos, Fotos, TagsOcorrencias, Assinatura
    from app import db  
    try:
        item_rdo = RDO.query.get_or_404(rdo_id)

        # Excluir fotos fisicamente
        upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'rdo')
        fotos = Fotos.query.filter_by(id_rdo=item_rdo.id).all()
        for foto in fotos:
            caminho_arquivo = os.path.join(upload_folder, foto.arquivo)
            if os.path.exists(caminho_arquivo):
                os.remove(caminho_arquivo)

        # Excluir registros relacionados
        Atividades.query.filter_by(id_rdo=item_rdo.id).delete()
        RDOMaoObra.query.filter_by(id_rdo=item_rdo.id).delete()
        Equipamentos.query.filter_by(id_rdo=item_rdo.id).delete()
        TagsOcorrencias.query.filter_by(id_rdo=item_rdo.id).delete()
        Fotos.query.filter_by(id_rdo=item_rdo.id).delete()
        Assinatura.query.filter_by(id_rdo=item_rdo.id).delete()

        # Excluir o RDO
        db.session.delete(item_rdo)
        db.session.commit()

        flash(f"RDO Nº {item_rdo.id_sequencial} excluído com sucesso!", "success")
        return redirect(url_for('auth.inicio'))
    except Exception as e:
        db.session.rollback()
        flash(f"Ocorreu um erro ao excluir o RDO: {str(e)}", "danger")
        return redirect(url_for('auth.inicio'))

# Lista RDO (placeholder)
@auth_bp.get("/lista-rdo")
@login_required
def lista_rdo():
    from app.models.rdo import RDO
    from app.models.usuario import Usuario  # Importar o modelo para acessar as permissões

    current_user_id = session.get("user_id")
    
    # 1. Buscar o objeto do usuário completo para ter acesso ao relacionamento obras_permitidas
    user = Usuario.query.get(current_user_id)

    if user:
        # 2. Extrair os IDs de todas as obras que o usuário tem permissão
        # 'obras_permitidas' foi definido no seu modelo Usuario
        ids_obras_permitidas = [obra.id for obra in user.obras_permitidas]

        # 3. Filtrar os RDOs: onde a id_obra do RDO está dentro da lista de permitidas
        rdos = RDO.query.filter(RDO.id_obra.in_(ids_obras_permitidas)).order_by(RDO.data.desc()).all()
    else:
        rdos = []
    
    # Buscar pendências de assinatura (não usadas na view, mas podem ser úteis)
    lista_pendencias = Assinatura.query.filter_by(
        id_usuario=current_user_id, 
        status='Pendencia'
    ).all()
    
    # Contar pendências de assinatura para o usuário atual
    minhas_pendencias = Assinatura.query.filter_by(
        id_usuario=current_user_id,
        status='Pendente'
    ).count()

    return render_template("list_rdo.html", rdos=rdos, count_minhas_pendencias=minhas_pendencias, lista_pendencias=lista_pendencias)

#######################################################################################################
####################################################################################################### Assinaturas RDO
#######################################################################################################

# Salvar NOVO Workflow (Definir Sequência)
@auth_bp.route("/assinar-rdo/<int:rdo_id>/salvar-workflow", methods=["POST"])
@login_required
def salvar_workflow_assinaturas(rdo_id):
    from app.models.rdo import RDO, Assinatura
    
    rdo = RDO.query.get_or_404(rdo_id)
    
    # Só permite editar workflow se não estiver finalizado
    if rdo.status in ['Aprovado', 'Rejeitado']:
         return jsonify({"success": False, "message": "RDO finalizado, não é possível alterar aprovadores."}), 403

    data = request.get_json()
    # IDs vindo do checkbox (ex: [5, 9])
    novos_assinantes_ids = [int(uid) for uid in data.get('usuarios_ids', [])] 
    
    creator_id = rdo.id_usuario

    # REGRA DE OURO: O criador DEVE estar na lista e DEVE ser o primeiro.
    # 1. Se o criador já estiver na lista vinda do front, removemos para evitar duplicidade
    if creator_id in novos_assinantes_ids:
        novos_assinantes_ids.remove(creator_id)
    
    # 2. Inserimos o criador forçadamente na posição 0
    novos_assinantes_ids.insert(0, creator_id)

    try:
        # Limpa assinaturas anteriores (Reinicia fluxo)
        Assinatura.query.filter_by(id_rdo=rdo_id).delete()
        
        # Cria novos registros na ordem correta
        for index, user_id in enumerate(novos_assinantes_ids):
            nova_ass = Assinatura(
                id_rdo=rdo_id,
                id_usuario=user_id,
                ordem=index + 1, # Ordem 1, 2, 3...
                status='Pendente'
            )
            db.session.add(nova_ass)
            
        # Garante que status do RDO volta a Pendente se o workflow reiniciou
        rdo.status = 'Pendente'
            
        db.session.commit()
        return jsonify({"success": True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500

# Assinar RDO (Execução da assinatura)
@auth_bp.route("/assinar-rdo/<int:rdo_id>/aprovar-rdo", methods=["POST"])
@login_required 
def assinar_rdo(rdo_id):
    from app.models.rdo import RDO, Assinatura
    
    user_id = session.get("user_id")
    rdo = RDO.query.get_or_404(rdo_id)

    # 1. Localiza a assinatura PENDENTE deste usuário neste RDO
    assinatura_pendente = Assinatura.query.filter_by(
        id_rdo=rdo_id, 
        id_usuario=user_id, 
        status='Pendente'
    ).first()

    if not assinatura_pendente:
        return jsonify({"success": False, "message": "Você não tem assinaturas pendentes para este RDO."}), 400

    # 2. CHECK DE SEQUÊNCIA: Verifica se existe alguém com ordem MENOR que ainda não aprovou
    passo_anterior_pendente = Assinatura.query.filter(
        Assinatura.id_rdo == rdo_id,
        Assinatura.ordem < assinatura_pendente.ordem,
        Assinatura.status != 'Aprovado'
    ).count()

    if passo_anterior_pendente > 0:
        return jsonify({"success": False, "message": "Aguarde a aprovação do responsável anterior."}), 403

    # 3. Processa Imagem
    dados = request.get_json()
    img_data = dados.get('assinatura_b64')
    
    if not img_data:
        return jsonify({"success": False, "message": "Imagem da assinatura não fornecida."}), 400

    try:
        # Salva o arquivo físico
        header, encoded = img_data.split(",", 1)
        file_data = base64.b64decode(encoded)
        filename = f"sig_{rdo_id}_{user_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
        
        upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'assinaturas')
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)
            
        with open(os.path.join(upload_folder, filename), "wb") as f:
            f.write(file_data)

        # 4. Atualiza Registro
        assinatura_pendente.img_assinatura = filename
        assinatura_pendente.criado = datetime.now()
        assinatura_pendente.status = 'Aprovado'
        
        # 5. Verifica se o RDO foi totalmente aprovado
        restantes = Assinatura.query.filter(
            Assinatura.id_rdo == rdo_id,
            Assinatura.status == 'Pendente',
            Assinatura.id_assinatura != assinatura_pendente.id_assinatura
        ).count()
        
        if restantes == 0:
            rdo.status = 'Aprovado'
        else:
            # Se era Pendente, continua Pendente. Se estava Rejeitado, volta a Pendente? 
            # Geralmente se assina, o fluxo está ativo.
            rdo.status = 'Pendente'

        db.session.commit()
        return jsonify({"success": True})

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    
# Rota de Rejeição
@auth_bp.route("/assinar-rdo/<int:id_assinatura>/rejeitar-rdo", methods=["POST"])
@login_required
def rejeitar_assinatura(id_assinatura):
    from app.models.rdo import RDO, Assinatura
    
    dados = request.get_json()
    motivo = dados.get('motivo')
    
    ass = Assinatura.query.get_or_404(id_assinatura)
    
    # Valida se quem está rejeitando é o dono da assinatura
    if ass.id_usuario != session.get('user_id'):
        return jsonify({"success": False, "message": "Não autorizado."}), 403

    try:
        # 1. Rejeita a assinatura específica
        ass.status = 'Rejeitado'
        ass.motivo_rejeicao = motivo
        ass.criado = datetime.now()
        
        # 2. Rejeita o RDO inteiro
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

# Rota para a lista de usuários
@auth_bp.get("/lista-usuarios")
@login_required
def lista_usuarios():
    from app.models.usuario import Usuario
    # Busca todos os usuários ordenados por ID crescente
    usuarios = Usuario.query.order_by(Usuario.id.asc()).all()

    # Coleta ids de supervisor (campo `id_supervisor` pode ser string vazio)
    sup_ids = set()
    for u in usuarios:
        try:
            if u.id_supervisor is not None and str(u.id_supervisor).strip() != '':
                sup_ids.add(int(str(u.id_supervisor).strip()))
        except Exception:
            continue

    # Busca os usuários que são supervisores em um único query
    sup_map = {}
    if sup_ids:
        supervisors = Usuario.query.filter(Usuario.id.in_(list(sup_ids))).all()
        sup_map = {s.id: s.nome for s in supervisors}

    # Injeta atributo dinâmico 'nome_supervisor' em cada usuário
    for u in usuarios:
        nome_sup = None
        try:
            if u.id_supervisor is not None and str(u.id_supervisor).strip() != '':
                sup_id = int(str(u.id_supervisor).strip())
                nome_sup = sup_map.get(sup_id)
        except Exception:
            nome_sup = None
        setattr(u, 'nome_supervisor', nome_sup)

    return render_template("list_usuarios.html", opcoes=usuarios, categoria="usuario")

# Abrir Formulário de Cadastro de Usuario
@auth_bp.get("/criar-usuario")
@login_required
def criar_usuario():
    from app.models.obra import Obra
    from app.models.usuario import Usuario
    
    # [CORREÇÃO] Busca plana de obras ativas (sem hierarquia)
    obras = Obra.query.filter_by(status=1).order_by(Obra.nome).all()
    
    # Determina o Admin padrão para uso no template
    admin = Usuario.query.filter_by(papel='Admin').first()
    default_supervisor = {'id': admin.id, 'nome': admin.nome, 'email': admin.email} if admin else None

    return render_template(
        "form_usuario.html", 
        categoria="usuario", 
        obras=obras, # Passa lista simples
        default_supervisor=default_supervisor
    )

# Salvar/Gerar Usuario (POST)
@auth_bp.post("/gerar-usuario")
@login_required
def gerar_usuario():
    from app.models.usuario import Usuario
    from app.models.obra import Obra
    
    categoria = request.form.get("categoria")
    user_id = request.form.get("id")
    
    # [CORREÇÃO] Busca obras ativas para repassar ao template em caso de erro
    obras_ativas = Obra.query.filter_by(status=1).order_by(Obra.nome).all()

    if categoria == "usuario":
        nome = request.form.get("nome")
        email = request.form.get("email")
        papel = request.form.get("papel")
        cpf = request.form.get("cpf") 
        senha = request.form.get("senha")
        status = True if request.form.get("status") == "on" else False
        obras_ids = request.form.getlist("obras_permitidas")
        id_supervisor_raw = request.form.get('id_supervisor')

        item_form = {'id': user_id, 'nome': nome, 'email': email, 'papel': papel, 'cpf': cpf}

        if user_id:
            user = Usuario.query.get_or_404(user_id)
            # Validação CPF duplicado
            if Usuario.query.filter(Usuario.cpf == cpf, Usuario.id != user_id).first():
                flash("Este CPF já está cadastrado.", "danger")
                return render_template("form_usuario.html", item=item_form, obras=obras_ativas)
            
            user.nome, user.email, user.papel, user.cpf, user.status = nome, email, papel, cpf, status
            try:
                user.id_supervisor = int(id_supervisor_raw) if id_supervisor_raw else None
            except Exception:
                user.id_supervisor = None
        else:
            if Usuario.query.filter_by(cpf=cpf).first():
                flash("CPF já cadastrado.", "danger")
                return render_template("form_usuario.html", item=item_form, obras=obras_ativas)

            user = Usuario(nome=nome, email=email, papel=papel, cpf=cpf, status=status)
            try:
                user.id_supervisor = int(id_supervisor_raw) if id_supervisor_raw else None
            except Exception:
                user.id_supervisor = None
            user.set_senha(senha if senha else "Usuario123")
            db.session.add(user)

        # [CORREÇÃO] Lógica de vínculo de obras (sem matrizes)
        if papel == 'Admin':
            # Admin tem acesso a tudo (pode vincular todas explicitamente ou deixar vazio se a lógica da app permitir)
            # Aqui vinculamos todas as ativas para garantir acesso visual nos relatórios que dependem dessa tabela
            user.obras_permitidas = Obra.query.all()
        else:
            obras_selecionadas = []
            if obras_ids:
                for oid in obras_ids:
                    if oid:
                        obra = Obra.query.get(int(oid))
                        if obra:
                            obras_selecionadas.append(obra)
            
            user.obras_permitidas = obras_selecionadas

        # Supervisor padrão
        if not getattr(user, 'id_supervisor', None):
            try:
                admin = Usuario.query.filter_by(papel='Admin').first()
                if admin:
                    user.id_supervisor = admin.id
            except Exception:
                pass

        try:
            db.session.commit()
            flash("Usuário salvo com sucesso!", "success")
            return render_template("form_usuario.html", item=user, obras=obras_ativas, view_mode=True)
        except Exception as e:
            db.session.rollback()
            flash(f"Erro: {str(e)}", "danger")
            return render_template("form_usuario.html", item=item_form, obras=obras_ativas)

# Mudar Status do Usuário (POST)
@auth_bp.post("/mudar-status-usuario/<int:userId>")
@login_required
def toggle_user_status(userId):
    from app.models.usuario import Usuario
    
    user = Usuario.query.get_or_404(userId)
    user.status = not user.status 
    
    try:
        db.session.commit()
        return jsonify({"message": "Status atualizado com sucesso", "status": user.status}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Erro ao atualizar: {str(e)}"}), 500
     
# Rota de Reset de Senha
@auth_bp.post("/usuario-resetar-senha/<int:id>")
@login_required
def reset_senha_usuario(id):
    from app.models.usuario import Usuario
    user = Usuario.query.get_or_404(id)
    user.set_senha("Usuario123")
    db.session.commit()
    return {"message": "Sucesso"}, 200
    

# Editar Usuário 
@auth_bp.route("/editar-usuario/<int:id>", methods=['GET', 'POST'])
@login_required
def editar_usuario(id):
    from app.models.usuario import Usuario 
    from app.models.obra import Obra
    
    user = Usuario.query.get_or_404(id)
    
    # [CORREÇÃO] Busca apenas a lista simples de obras
    obras = Obra.query.filter_by(status=1).order_by(Obra.nome).all()

    return render_template(
        "form_usuario.html", 
        item=user, 
        categoria="usuario", 
        obras=obras 
    )
    
# Visualizar Usuário
@auth_bp.get("/visualizar-usuario/<int:id>")
@login_required
def visualizar_usuario(id):
    from app.models.usuario import Usuario
    from app.models.obra import Obra
    
    user = Usuario.query.get_or_404(id)
    
    # [CORREÇÃO] Busca apenas a lista simples de obras
    obras = Obra.query.filter_by(status=1).order_by(Obra.nome).all()
    
    view_mode = True
    
    # Monta a cadeia de supervisores para exibição
    # Função get_supervisor_chain_for_user deve estar importada ou definida neste arquivo
    supervisor_chain = get_supervisor_chain_for_user(user)

    nome_supervisor = None
    if getattr(user, 'id_supervisor', None):
        try:
            sup = Usuario.query.get(int(user.id_supervisor))
            nome_supervisor = sup.nome if sup else None
        except Exception:
            nome_supervisor = None

    setattr(user, 'nome_supervisor', nome_supervisor)

    default_supervisor = None
    try:
        admin = Usuario.query.filter_by(papel='Admin').first()
        if admin:
            default_supervisor = {'id': admin.id, 'nome': admin.nome, 'email': admin.email}
    except Exception:
        default_supervisor = None

    return render_template(
        "form_usuario.html", 
        item=user, 
        categoria="usuario", 
        obras=obras, 
        view_mode=view_mode, 
        supervisor_chain=supervisor_chain, 
        default_supervisor=default_supervisor
    )

# Helper function para supervisores (caso não esteja em utils)
def get_supervisor_chain_for_user(user):
    from app.models.usuario import Usuario
    chain = []
    visited = set()
    current = user
    while current and getattr(current, 'id_supervisor', None):
        try:
            sup_id = int(getattr(current, 'id_supervisor'))
        except Exception:
            break
        if sup_id in visited:
            break
        sup = Usuario.query.get(sup_id)
        if not sup:
            break
        chain.append({'id': sup.id, 'nome': sup.nome, 'email': sup.email})
        visited.add(sup.id)
        current = sup
    return chain

# Endpoint que retorna lista de usuários para selecionar como supervisor
@auth_bp.get('/supervisores')
@login_required
def lista_supervisores():
    from app.models.usuario import Usuario
    users = Usuario.query.order_by(Usuario.nome.asc()).all()
    result = [{'id': u.id, 'nome': u.nome, 'papel': u.papel, 'email': u.email} for u in users]
    return jsonify(result)

#######################################################################################################
####################################################################################################### CLIMAS
#######################################################################################################

# Rota para a lista de climas
@auth_bp.get("/lista-climas")
@login_required
def lista_climas():
    from app.models.lista_opcoes import Clima
    # Busca todos os climas
    climas = Clima.query.order_by(Clima.nome.asc()).all()
    return render_template("list_climas.html", opcoes=climas, categoria="clima")

# Criar Clima
@auth_bp.get('/criar-clima')
@login_required
def criar_clima():
    # Mostra formulário para criação
    return render_template('form_clima.html', item=None, view_mode=False)

# Salvar/Gerar Clima (POST)
@auth_bp.post('/gerar-clima')
@login_required
def gerar_clima():
    from app.models.lista_opcoes import Clima
    clima_id = request.form.get('id')
    tipo_lista = "Climas"
    nome = request.form.get('nome', '').strip()
    if not nome:
        flash('Nome do clima é obrigatório.', 'danger')
        if clima_id:
            return redirect(url_for('auth.editar_clima', id=clima_id))
        return redirect(url_for('auth.criar_clima'))

    if clima_id:
        clima = Clima.query.get(clima_id)
        if not clima:
            flash('Clima não encontrado.', 'danger')
            return redirect(url_for('auth.lista_climas'))
        clima.nome = nome
        db.session.add(clima)
        db.session.commit()
        flash('Clima atualizado com sucesso.', 'success')
        return redirect(url_for('auth.lista_climas'))

    novo = Clima(nome=nome, tipo_lista=tipo_lista)
    db.session.add(novo)
    db.session.commit()
    flash('Clima criado com sucesso.', 'success')
    return redirect(url_for('auth.lista_climas'))

# Visualizar Clima
@auth_bp.get('/visualizar-clima/<int:id>')
@login_required
def visualizar_clima(id):
    from app.models.lista_opcoes import Clima
    clima = Clima.query.get_or_404(id)
    return render_template('form_clima.html', item=clima, view_mode=True)

# Editar Clima
@auth_bp.get('/editar-clima/<int:id>')
@login_required
def editar_clima(id):
    from app.models.lista_opcoes import Clima
    clima = Clima.query.get_or_404(id)
    return render_template('form_clima.html', item=clima, view_mode=False)

# Excluir Clima
@auth_bp.post('/excluir-clima/<int:id>')
@login_required
def excluir_clima(id):
    from app.models.lista_opcoes import Clima
    clima = Clima.query.get(id)
    if not clima:
        flash('Clima não encontrado.', 'danger')
        return redirect(url_for('auth.lista_climas'))
    # TODO: verificar dependências (RDOs) antes de excluir
    db.session.delete(clima)
    db.session.commit()
    return redirect(url_for('auth.lista_climas'))

#######################################################################################################
####################################################################################################### EQUIPAMENTOS
#######################################################################################################

# Rota para a lista de equipamentos
@auth_bp.get("/lista-equipamentos")
@login_required
def lista_equipamentos():
    from app.models.lista_opcoes import Equipamento
    # Busca todos os equipamentos
    equipamentos = Equipamento.query.order_by(Equipamento.nome.asc()).all()
    return render_template("list_equipamentos.html", opcoes=equipamentos, categoria="equipamento")

# Criar Equipamento
@auth_bp.get('/criar-equipamento')
@login_required
def criar_equipamento():
    # Mostra formulário para criação
    return render_template('form_equipamento.html', item=None, view_mode=False)

# Salvar/Gerar Equipamento (POST)
@auth_bp.post('/gerar-equipamento')
@login_required
def gerar_equipamento():
    from app.models.lista_opcoes import Equipamento
    equipamento_id = request.form.get('id')
    tipo_lista = "Equipamentos"
    nome = request.form.get('nome', '').strip()
    if not nome:
        flash('Nome do equipamento é obrigatório.', 'danger')
        if equipamento_id:
            return redirect(url_for('auth.editar_equipamento', id=equipamento_id))
        return redirect(url_for('auth.criar_clima'))

    if equipamento_id:
        equipamento = Equipamento.query.get(equipamento_id)
        if not equipamento:
            flash('Equipamento não encontrado.', 'danger')
            return redirect(url_for('auth.lista_equipamentos'))
        equipamento.nome = nome
        db.session.add(equipamento)
        db.session.commit()
        flash('Equipamento atualizado com sucesso.', 'success')
        return redirect(url_for('auth.lista_equipamentos'))

    novo = Equipamento(nome=nome, tipo_lista=tipo_lista)
    db.session.add(novo)
    db.session.commit()
    flash('Equipamento criado com sucesso.', 'success')
    return redirect(url_for('auth.lista_equipamentos'))

# Visualizar Equipamento
@auth_bp.get('/visualizar-equipamento/<int:id>')
@login_required
def visualizar_equipamento(id):
    from app.models.lista_opcoes import Equipamento
    equipamento = Equipamento.query.get_or_404(id)
    return render_template('form_equipamento.html', item=equipamento, view_mode=True)

# Editar Equipamento
@auth_bp.get('/editar-equipamento/<int:id>')
@login_required
def editar_equipamento(id):
    from app.models.lista_opcoes import Equipamento
    equipamento = Equipamento.query.get_or_404(id)
    return render_template('form_equipamento.html', item=equipamento, view_mode=False)

# Excluir Equipamento
@auth_bp.post('/excluir-equipamento/<int:id>')
@login_required
def excluir_equipamento(id):
    from app.models.lista_opcoes import Equipamento
    equipamento = Equipamento.query.get(id)
    if not equipamento:
        flash('Equipamento não encontrado.', 'danger')
        return redirect(url_for('auth.lista_equipamentos'))
    # TODO: verificar dependências (RDOs) antes de excluir
    db.session.delete(equipamento)
    db.session.commit()
    return redirect(url_for('auth.lista_equipamentos'))

#######################################################################################################
####################################################################################################### TAGS OCORRENCIAS
#######################################################################################################

# Rota para a lista de tagsOcorrencias
@auth_bp.get("/lista-tags-ocorrencias")
@login_required
def lista_tags_ocorrencias():
    from app.models.lista_opcoes import TagOcorrencia
    # Busca todos os tagsOcorrencias
    tagsOcorrencias = TagOcorrencia.query.order_by(TagOcorrencia.nome.asc()).all()
    return render_template("list_tags_ocorrencias.html", opcoes=tagsOcorrencias, categoria="tagsOcorrencias")

# Criar TagOcorrencia
@auth_bp.get('/criar-tags-ocorrencias')
@login_required
def criar_tags_ocorrencias():
    # Mostra formulário para criação
    return render_template('form_tags_ocorrencias.html', item=None, view_mode=False)

# Salvar/Gerar TagOcorrencia (POST)
@auth_bp.post('/gerar-tags-ocorrencias')
@login_required
def gerar_tags_ocorrencias():
    from app.models.lista_opcoes import TagOcorrencia
    tag_ocorrencia_id = request.form.get('id')
    tipo_lista = "Tags Ocorrencias"
    nome = request.form.get('nome', '').strip()
    if not nome:
        flash('Nome do tag de ocorrência é obrigatório.', 'danger')
        if tag_ocorrencia_id:
            return redirect(url_for('auth.editar_tags_ocorrencias', id=tag_ocorrencia_id))
        return redirect(url_for('auth.criar_tags_ocorrencias'))

    if tag_ocorrencia_id:
        tag_ocorrencia = TagOcorrencia.query.get(tag_ocorrencia_id)
        if not tag_ocorrencia:
            flash('Tag de ocorrência não encontrada.', 'danger')
            return redirect(url_for('auth.lista_tags_ocorrencias'))
        tag_ocorrencia.nome = nome
        db.session.add(tag_ocorrencia)
        db.session.commit()
        flash('Tag de ocorrência atualizado com sucesso.', 'success')
        return redirect(url_for('auth.lista_tags_ocorrencias'))

    novo = TagOcorrencia(nome=nome, tipo_lista=tipo_lista)
    db.session.add(novo)
    db.session.commit()
    flash('Tag de ocorrência criada com sucesso.', 'success')
    return redirect(url_for('auth.lista_tags_ocorrencias'))

# Visualizar TagOcorrencia
@auth_bp.get('/visualizar-tags-ocorrencias/<int:id>')
@login_required
def visualizar_tags_ocorrencias(id):
    from app.models.lista_opcoes import TagOcorrencia
    tag_ocorrencia = TagOcorrencia.query.get_or_404(id)
    return render_template('form_tags_ocorrencias.html', item=tag_ocorrencia, view_mode=True)

# Editar TagOcorrencia
@auth_bp.get('/editar-tags-ocorrencias/<int:id>')
@login_required
def editar_tags_ocorrencias(id):
    from app.models.lista_opcoes import TagOcorrencia
    tag_ocorrencia = TagOcorrencia.query.get_or_404(id)
    return render_template('form_tags_ocorrencias.html', item=tag_ocorrencia, view_mode=False)

# Excluir TagOcorrencia
@auth_bp.post('/excluir-tags-ocorrencias/<int:id>')
@login_required
def excluir_tags_ocorrencias(id):
    from app.models.lista_opcoes import TagOcorrencia
    tag_ocorrencia = TagOcorrencia.query.get(id)
    if not tag_ocorrencia:
        flash('Tag de ocorrência não encontrada.', 'danger')
        return redirect(url_for('auth.lista_tags_ocorrencias'))
    # TODO: verificar dependências (RDOs) antes de excluir
    db.session.delete(tag_ocorrencia)
    db.session.commit()
    return redirect(url_for('auth.lista_tags_ocorrencias'))

#######################################################################################################
####################################################################################################### MAO DE OBRA
#######################################################################################################

# Rota para a lista de mão de obra
@auth_bp.get("/lista-mao-obra")
@login_required
def lista_mao_obra():
    from app.models.lista_opcoes import MaoObra
    # Busca toda a mão de obra
    mao_obra = MaoObra.query.order_by(MaoObra.nome.asc()).all()
    return render_template(
        "list_mao_obra.html",
        opcoes=mao_obra,
        categoria="mao_obra"
    )

# Criar Mão de Obra
@auth_bp.get('/criar-mao-obra')
@login_required
def criar_mao_obra():
    # Mostra formulário para criação
    return render_template(
        'form_mao_obra.html',
        item=None,
        view_mode=False
    )

# Salvar/Gerar Mão de Obra (POST)
@auth_bp.post('/gerar-mao-obra')
@login_required
def gerar_mao_obra():
    from app.models.lista_opcoes import MaoObra

    mao_obra_id = request.form.get('id')
    tipo_lista = "Mao de Obra"
    nome = request.form.get('nome', '').strip()

    if not nome:
        flash('Nome da mão de obra é obrigatório.', 'danger')
        if mao_obra_id:
            return redirect(url_for('auth.editar_mao_obra', id=mao_obra_id))
        return redirect(url_for('auth.criar_mao_obra'))

    # Edição
    if mao_obra_id:
        mao_obra = MaoObra.query.get(mao_obra_id)
        if not mao_obra:
            flash('Mão de obra não encontrada.', 'danger')
            return redirect(url_for('auth.lista_mao_obra'))

        mao_obra.nome = nome
        db.session.add(mao_obra)
        db.session.commit()

        flash('Mão de obra atualizada com sucesso.', 'success')
        return redirect(url_for('auth.lista_mao_obra'))

    # Criação
    novo = MaoObra(
        nome=nome,
        tipo_lista=tipo_lista
    )
    db.session.add(novo)
    db.session.commit()

    flash('Mão de obra criada com sucesso.', 'success')
    return redirect(url_for('auth.lista_mao_obra'))

# Visualizar Mão de Obra
@auth_bp.get('/visualizar-mao-obra/<int:id>')
@login_required
def visualizar_mao_obra(id):
    from app.models.lista_opcoes import MaoObra
    mao_obra = MaoObra.query.get_or_404(id)
    return render_template(
        'form_mao_obra.html',
        item=mao_obra,
        view_mode=True
    )

# Editar Mão de Obra
@auth_bp.get('/editar-mao-obra/<int:id>')
@login_required
def editar_mao_obra(id):
    from app.models.lista_opcoes import MaoObra
    mao_obra = MaoObra.query.get_or_404(id)
    return render_template(
        'form_mao_obra.html',
        item=mao_obra,
        view_mode=False
    )

# Excluir Mão de Obra
@auth_bp.post('/excluir-mao-obra/<int:id>')
@login_required
def excluir_mao_obra(id):
    from app.models.lista_opcoes import MaoObra

    mao_obra = MaoObra.query.get(id)
    if not mao_obra:
        flash('Mão de obra não encontrada.', 'danger')
        return redirect(url_for('auth.lista_mao_obra'))

    # TODO: verificar dependências (RDOs) antes de excluir
    db.session.delete(mao_obra)
    db.session.commit()

    flash('Mão de obra excluída com sucesso.', 'success')
    return redirect(url_for('auth.lista_mao_obra'))

#######################################################################################################
####################################################################################################### OBRAS
#######################################################################################################

# Rota para a lista de obras
@auth_bp.get("/lista-obras")
@login_required
def lista_obras():
    from app.models.obra import Obra
    
    # Consulta simplificada sem o JOIN de Matriz
    consulta = Obra.query.order_by(Obra.id.asc())
    resultados = consulta.all()
    
    # Formata os resultados para o Template Jinja
    obras_formatadas = []
    for obra_obj in resultados:
        # Cria um dicionário com os atributos necessários para o template
        obra_dict = {
            'id': obra_obj.id,
            'nome': obra_obj.nome,
            'cnpj': obra_obj.cnpj,
            'cliente': obra_obj.contratante,
            # 'id_matriz': obra_obj.id_matriz, -> Removido
            'cidade': obra_obj.cidade,
            'estado': obra_obj.estado,
            'endereco': obra_obj.endereco,
            'numero': obra_obj.numero,
            'complemento': obra_obj.complemento,
            'bairro': obra_obj.bairro,
            'cep': obra_obj.cep,
            'status': obra_obj.status,
            # 'nome_matriz': nome_matriz, -> Removido
            'frentes_trabalho': obra_obj.frentes_trabalho
        }
        
        obras_formatadas.append(obra_dict)
    
    return render_template("list_obras.html", opcoes=obras_formatadas, categoria="obra")

def get_supervisor_chain_for_user(user):
    """Retorna lista de supervisores ascendentes a partir do usuário.
    Mantido pois refere-se a hierarquia de Usuários, não de Obras.
    """
    from app.models.usuario import Usuario
    chain = []
    visited = set()
    current = user
    while current and getattr(current, 'id_supervisor', None):
        try:
            sup_id = int(getattr(current, 'id_supervisor'))
        except Exception:
            break
        if sup_id in visited:
            break
        sup = Usuario.query.get(sup_id)
        if not sup:
            break
        chain.append({'id': sup.id, 'nome': sup.nome, 'email': sup.email})
        visited.add(sup.id)
        current = sup

    return chain

# Rota para criar nova obra
@auth_bp.get("/criar-obra")
@login_required
def criar_obra():
    from app.models.usuario import Usuario
    # Removida a busca de opcoes_matriz
    
    usuarios = Usuario.query.filter_by(status=1).all()
    
    # Removemos 'opcoes_matriz' do retorno
    return render_template("form_obra.html", item=None, usuarios=usuarios)

# Rota para mudar status da obra (POST)
@auth_bp.post("/mudar-status-obras/<int:obraid>")
@login_required
def toggle_user_obras(obraid):
    from app.models.obra import Obra # Corrigido import (era app.models.usuario)
    
    obra = Obra.query.get_or_404(obraid)
    
    obra.status = not obra.status 
    
    try:
        db.session.commit()
        return {"message": "Status atualizado com sucesso"}, 200
    except Exception as e:
        db.session.rollback()
        return {"message": f"Erro ao atualizar: {str(e)}"}, 500
    
# Rota para salvar obra (POST)
@auth_bp.route('/gerar-obra', methods=['POST'])
@login_required
def gerar_obra():
    from app.models.obra import Obra, Frente_Trabalho
    
    # 1. Obter Dados do Formulário
    id_obra = request.form.get("id")
    if not id_obra: id_obra = None

    cnpj = request.form.get('cnpj')

    # --- VALIDAÇÃO DE DUPLICIDADE DE CNPJ ---
    obra_existente = Obra.query.filter_by(cnpj=cnpj).first()

    if obra_existente:
        if not id_obra or str(obra_existente.id) != str(id_obra):
            flash(f"Erro: O CNPJ {cnpj} já está cadastrado para a obra '{obra_existente.nome}'.", "danger")
            return redirect(url_for('auth.lista_obras'))

    # 2. Coleta dos demais dados
    nome = request.form.get('nome')
    contratante = request.form.get('contratante')
    contrato = request.form.get('contrato')
    id_responsavel = request.form.get('id_responsavel')
    # id_matriz = request.form.get('id_matriz') -> Removido
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
        # Converte datas
        inicio = datetime.strptime(inicio_str, '%Y-%m-%d').date() if inicio_str else None
        termino = datetime.strptime(termino_str, '%Y-%m-%d').date() if termino_str else None

        if id_obra:
            # --- MODO EDIÇÃO ---
            obra = Obra.query.get(id_obra)
            if not obra:
                flash("Obra não encontrada.", "danger")
                return redirect(url_for('auth.lista_obras'))
            
            # Atualiza campos da obra
            obra.nome = nome
            obra.cnpj = cnpj
            obra.contratante = contratante
            obra.contrato = contrato
            obra.id_responsavel = id_responsavel if id_responsavel else None
            # obra.id_matriz = int(id_matriz) if id_matriz else None -> Removido
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
            # --- MODO CRIAÇÃO ---
            obra = Obra(
                nome=nome, cnpj=cnpj, contratante=contratante, contrato=contrato,
                id_responsavel=id_responsavel if id_responsavel else None,
                # id_matriz removido do construtor
                inicio=inicio, termino=termino,
                cep=cep, endereco=endereco, numero=numero, complemento=complemento,
                bairro=bairro, cidade=cidade, estado=estado, status=status
            )
            db.session.add(obra)
            
            db.session.flush() 
            
            flash("Obra cadastrada com sucesso!", "success")

        # --- PROCESSAMENTO DAS FRENTES ---
        if frentes_payload:
            data = json.loads(frentes_payload)
            
            # 1. REMOVIDAS
            for f_id in data.get('removidas', []):
                if f_id:
                    Frente_Trabalho.query.filter_by(id_frente_trabalho=f_id, id_obra=obra.id).delete()
            
            # 2. NOVAS
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

            # 3. EDITADAS
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
        print(f"Erro ao salvar obra: {e}")
        if "Duplicate entry" in str(e):
             flash(f"Erro: CNPJ já existente no sistema.", "danger")
        else:
             flash(f"Erro ao processar a solicitação: {str(e)}", "danger")
        
        return redirect(url_for('auth.lista_obras'))
    
# Rota pra editar obra
@auth_bp.get("/editar-obra/<int:id>")
@login_required
def editar_obra(id):
    from app.models.obra import Obra, Frente_Trabalho
    from app.models.usuario import Usuario

    # Busca a Obra diretamente, sem lógica de Matriz
    obra = Obra.query.get_or_404(id)
    
    # Busca todas as frentes vinculadas a essa obra
    frentes = Frente_Trabalho.query.filter_by(id_obra=id).all()
    
    usuarios = Usuario.query.filter_by(status=1).all() 
    
    # Removido busca de opcoes_matriz
    
    return render_template("form_obra.html", item=obra, frentes=frentes, usuarios=usuarios)

# Rota para visualizar obra
@auth_bp.get("/visualizar-obra/<int:id>")
@login_required
def visualizar_obra(id):
    from app.models.obra import Obra, Frente_Trabalho
    from app.models.usuario import Usuario
    
    # Busca o item de Obra diretamente
    item = Obra.query.get_or_404(id) 

    view_mode = True
        
    # Removido busca de opcoes_matriz
    usuarios = Usuario.query.filter_by(status=1).all()
    
    frentes = Frente_Trabalho.query.filter_by(id_obra=id).all()

    usuario = Usuario.query.order_by(Usuario.nome).all()
    
    return render_template(
        "form_obra.html", 
        item=item, 
        view_mode=view_mode, 
        categoria="obra",
        # opcoes_matriz removido
        frentes=frentes,
        usuario=usuario,
        usuarios=usuarios
    )

# Rota para toggle de status da obra
@auth_bp.post("/obra/toggle-status/<int:id>")
@login_required
def toggle_obra_status(id):
    from app.models.obra import Obra
    
    obra = Obra.query.get_or_404(id)
    
    # Alterna o status (Ativa <-> Inativa)
    if obra.status == 1:
        obra.status = 0
    else:
        obra.status = 1
        
    try:
        db.session.commit()
        return '', 200 
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao alternar status da obra: {e}")
        return '', 500
      
#######################################################################################################
####################################################################################################### MEU PERFIL
#######################################################################################################

# Rota para Visualizar o Perfil
@auth_bp.get("/meu-perfil")
@login_required
def meu_perfil():
    from app.models.usuario import Usuario
    # current_user já é fornecido pelo Flask-Login, mas recarregar do banco garante dados frescos
    user = Usuario.query.get(session.get("user_id"))
    return render_template("configuracoes_perfil.html", current_user=user)

# Rota para Atualizar Dados Pessoais
@auth_bp.post("/atualizar-meu-perfil")
@login_required
def atualizar_perfil():
    from app.models.usuario import Usuario
    
    user = Usuario.query.get(session.get("user_id"))
    nome = request.form.get("nome")
    telefone = request.form.get("telefone") # Novo campo sugerido
    departamento = request.form.get("departamento") # Novo campo sugerido
    
    if user:
        user.nome = nome
        user.departamento = departamento
        
        # Verifica se o atributo existe antes de tentar salvar (segurança contra erro de coluna inexistente)
        if hasattr(user, 'telefone'): 
            user.telefone = telefone
            
        try:
            db.session.commit()
            # Atualiza sessão também
            session["user_name"] = user.nome
            flash("Perfil atualizado com sucesso!", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao atualizar perfil: {str(e)}", "danger")
            
    return redirect(url_for("auth.meu_perfil"))

# Rota para Alterar Senha Logado
@auth_bp.post("/alterar-minha-senha")
@login_required
def alterar_minha_senha():
    from app.models.usuario import Usuario
    
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
    except Exception as e:
        db.session.rollback()
        flash("Erro ao alterar senha.", "danger")
        
    return redirect(url_for("auth.meu_perfil"))