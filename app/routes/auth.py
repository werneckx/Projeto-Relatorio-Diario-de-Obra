import base64
import hashlib
from math import e
import os
from flask import Blueprint, Config, abort, json, render_template, request, redirect, url_for, flash, session, send_file
from werkzeug.security import check_password_hash
from app import db # Importar 'db' para uso no filtro (db.or_)
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
from sqlalchemy import func, or_
from datetime import date, datetime, timedelta
from functools import wraps # Mover a importação para o topo para melhor prática
from sqlalchemy.orm import aliased
from flask import request, jsonify
from app import db
from app.models.obra import Frente_Trabalho
from werkzeug.utils import secure_filename
from flask import make_response
from app.utils.pdf_service import render_rdo_pdf
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

# Decorator: login_required
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            # Melhoria: usa flash message para indicar a necessidade de login
            flash("Você precisa estar logado para acessar esta página.", "warning")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)

    return decorated


# Tela de Login (GET)
@auth_bp.get("/login")
def login():
    return render_template("login.html")


# Tela de Login (POST)
@auth_bp.post("/login")
def login_post():
    email = request.form.get("email")
    senha = request.form.get("senha")

    # Importar Usuario aqui, apenas onde é usado na rota
    from app.models.usuario import Usuario

    # 1. Adicionar o filtro 'ativo=1' (ou outro campo/valor que defina o status ativo)
    # Supondo que 'ativo' é um campo booleano (1 para Ativo, 0 para Inativo)
    user = Usuario.query.filter_by(email=email, status=1).first()

    # Se 'ativo' for o nome do campo de status:
    if not user or not check_password_hash(user.senha, senha):
        # O usuário não existe, a senha está incorreta OU o status não é ativo (ativo != 1)
        flash("E-mail, senha ou status de usuário inválido.", "error")
        return redirect(url_for("auth.login"))

    # Se a lógica for não filtrar no banco, mas checar o status 'ativo' depois:
    # user = Usuario.query.filter_by(email=email).first()
    # if not user or not check_password_hash(user.senha, senha) or user.ativo != 1:
    #     flash("E-mail, senha ou status de usuário inválido.", "error")
    #     return redirect(url_for("auth.login"))
    
    session["user_id"] = user.id
    session["user_name"] = user.nome
    session["user_email"] = user.email
    session["user_role"] = user.papel

    return redirect(url_for("auth.inicio"))

# Logout
@auth_bp.get("/logout")
def logout():
    session.clear()
    flash("Você foi desconectado com sucesso.", "info")
    return redirect(url_for("auth.login"))

#######################################################################################################
####################################################################################################### Inicio
#######################################################################################################

# Página inicio
@auth_bp.get("/inicio")
@login_required
def inicio():
    return render_template("inicio.html")

#######################################################################################################
####################################################################################################### Configurações
#######################################################################################################

@auth_bp.app_context_processor
def inject_company_info():
    from app.models.empresa import Empresa
    # Aqui simulamos a busca no banco. 
    # Se não houver nada no banco, define um nome padrão.
    nome_empresa = Empresa.query.first().nome_empresa if Empresa.query.first() else "Não definido" 
    # No futuro: nome_empresa = Configuracao.query.first().nome_empresa
    
    return dict(nome_empresa_global=nome_empresa)

# Página inicio
@auth_bp.get("/empresa")
@login_required
def empresa():
    from app.models.empresa import Empresa
    config_data = {
        'nome_empresa': Empresa.query.first().nome_empresa if Empresa.query.first() else '',
        'logo_path': 'logo/logo.png',
        'icone_path': 'logo/icone.png'
    }
    return render_template('configuracoes.html', config_data=config_data, view_mode=True)

@auth_bp.route('/salvar-empresa', methods=['POST'])
def salvar_empresa():
    nome_empresa = request.form.get('nome_empresa')
    logo_file = request.files.get('logo_empresa')
    icone_file = request.files.get('icone_empresa')

    try:
        # 1. Atualizar Nome no Banco de Dados
        # Ajuste o filtro se houver mais de uma empresa, ou use .first()
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

#######################################################################################################
####################################################################################################### RDO
#######################################################################################################

@auth_bp.get("/criar-rdo")
@login_required
def criar_rdo():
    from app.models.obra import Obra, Frente_Trabalho # Importe Frente_Trabalho também
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
        mao_de_obra_options=mao_de_obra_options, # ENVIA PARA O HTML
        equipamentos_options=equipamentos_options, # ENVIA PARA O HTML
        tags_options=tags_options # ENVIA PARA O HTML
    )
    
# Adicione ao auth_bp

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
            "responsavel_id": id_resp_frente
        })

    # 6. Retorno do JSON com os nomes de campos corretos
    return jsonify({
        "num_contrato": obra.contrato,       # Correção: usa 'contrato' e não 'num_contrato'
        "cliente": obra.contratante,         # Correção: usa 'contratante'
        "data_inicio": data_inicio_fmt,
        "data_inicio_iso": data_inicio_iso,
        "data_fim": data_fim_fmt,
        "data_fim_iso": data_fim_iso,
        "responsavel": nome_responsavel,     # Valor corrigido no passo 4
        "frentes": lista_frentes
    })
    
@auth_bp.get("/api/frente/<int:id>")
@login_required
def get_frente_api(id):
    from app.models.obra import Frente_Trabalho
    frente = Frente_Trabalho.query.get_or_404(id)
    return jsonify({
        "responsavel": frente.responsavel_tecnico.nome if frente.responsavel_tecnico else None
    })

# Gerar RDO (POST)
 
@auth_bp.post("/gerar-rdo")
@login_required
def gerar_rdo():
    from app.models.rdo import RDO, RDOMaoObra, Atividades, Equipamentos, Fotos, TagsOcorrencias
    from app.models.lista_opcoes import Equipamento
    # CORRETO
    from flask import current_app  # O current_app sim vem do flask
    from app import db             # O db vem da sua aplicação (instância do SQLAlchemy)
    
    try:
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
            try: return float(v.replace(',', '.'))
            except: return None

        # Dados Básicos
        rdo_id_original = _get_int("rdo_id")
        id_obra = _get_int("obra_id")
        data_rdo_str = request.form.get("data_rdo") # YYYY-MM-DD
        data_rdo = datetime.strptime(data_rdo_str, '%Y-%m-%d').date() if data_rdo_str else date.today()
        
        # Criação ou Revisão
        if rdo_id_original:
            # Lógica de revisão: clonar ou atualizar status anterior
            rdo_antigo = RDO.query.get_or_404(rdo_id_original)
            # Para simplificar, estamos editando o próprio objeto se for edição simples,
            # ou criando nova revisão se a regra de negócio exigir. 
            # Assumindo EDIÇÃO do rascunho ou CRIAÇÃO de nova revisão se aprovado.
            # Aqui vou seguir a lógica de criar NOVO objeto (Revisão +1) para preservar histórico
            
            nova_revisao = rdo_antigo.id_revisao + 1
            item_rdo = RDO(
                id_obra=rdo_antigo.id_obra,
                id_sequencial=rdo_antigo.id_sequencial,
                id_revisao=nova_revisao
            )
        else:
            # Novo RDO
            num_existentes = RDO.query.filter_by(id_obra=id_obra, id_revisao=0).count()
            item_rdo = RDO(
                id_obra=id_obra,
                id_sequencial=num_existentes + 1,
                id_revisao=0
            )

        # Popular campos comuns
        item_rdo.id_frente_trabalho = _get_int("frente_trabalho_id")
        item_rdo.id_usuario = session.get("user_id")
        item_rdo.id_climas_manha = _get_int("climas_manha")
        item_rdo.id_climas_tarde = _get_int("climas_tarde")
        item_rdo.data = data_rdo
        item_rdo.modificado = datetime.now()
        item_rdo.status = "Pendente"
        item_rdo.comentarios_gerais = request.form.get("comentarios_gerais")
        
        # Horários
        item_rdo.hora_entrada = _get_time("hora_entrada")
        item_rdo.hora_saida = _get_time("hora_saida")
        item_rdo.intervalo_entrada = _get_time("intervalo_entrada")
        item_rdo.intervalo_saida = _get_time("intervalo_saida")
        
        db.session.add(item_rdo)
        db.session.flush() # Para gerar o ID do RDO

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

        for i, func in enumerate(funcoes):
            if func and func.strip():
                qp = int(qtd_prop[i]) if i < len(qtd_prop) and qtd_prop[i] else 0
                qt = int(qtd_terc[i]) if i < len(qtd_terc) and qtd_terc[i] else 0
                t = _get_time(f"mo_tempo_dummy") # Hack: pegar do valor direto, pois getlist retorna string
                # Parse manual do tempo da lista
                tempo_str = tempos[i] if i < len(tempos) else None
                tempo_obj = datetime.strptime(tempo_str, '%H:%M').time() if tempo_str else None
                
                nova_mo = RDOMaoObra(
                    id_rdo=item_rdo.id, nome_funcao=func,
                    quantidade_propria=qp, quantidade_terceirizada=qt, tempo=tempo_obj
                )
                db.session.add(nova_mo)

        # --- 3. Equipamentos ---
        eq_ids = request.form.getlist("eq_id[]")
        eq_qts = request.form.getlist("eq_qtd[]")
        
        for i, eid in enumerate(eq_ids):
            if eid:
                qtd = int(eq_qts[i]) if i < len(eq_qts) and eq_qts[i] else 0
                # Buscar nome para persistência redundante (opcional) ou usar relacionamento
                eq_obj = Equipamento.query.get(eid)
                novo_eq = Equipamentos(
                    id_rdo=item_rdo.id, id_equipamento_lista=eid,
                    nome_equipamento=eq_obj.nome if eq_obj else "", quantidade=qtd
                )
                db.session.add(novo_eq)

        # --- 4. Ocorrências ---
        oc_tags = request.form.getlist("oc_tag[]")
        oc_descs = request.form.getlist("oc_desc[]")
        
        for i, tid in enumerate(oc_tags):
            if tid:
                desc = oc_descs[i] if i < len(oc_descs) else ""
                nova_oc = TagsOcorrencias(id_rdo=item_rdo.id, id_tag_lista=tid, descricao=desc)
                db.session.add(nova_oc)

        # --- 5. Fotos (Upload e Comentários) ---
        UPLOAD_FOLDER = os.path.join(current_app.root_path, 'static', 'uploads', 'rdo')
        if not os.path.exists(UPLOAD_FOLDER):
            os.makedirs(UPLOAD_FOLDER)
            
        arquivos = request.files.getlist("fotos[]")
        legendas = request.form.getlist("legenda_foto_nova[]")
        
        # Processar fotos antigas (se for revisão, copiar)
        if rdo_id_original:
            rdo_antigo = RDO.query.get(rdo_id_original)
            # Copiar fotos do antigo para o novo
            for f_antiga in rdo_antigo.fotos:
                # Aqui você pode decidir se copia o registro ou mantém referência
                f_nova = Fotos(
                    id_rdo=item_rdo.id, arquivo=f_antiga.arquivo,
                    comentario=f_antiga.comentario
                )
                db.session.add(f_nova)

        # Processar novas fotos
        # Nota: O input file multiple não garante ordem com inputs text separados facilmente.
        # Simplificação: assume que legendas novas vêm na ordem.
        # Melhoria UX: Upload assíncrono seria ideal, mas no submit form tradicional:
        
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
        flash(f"RDO Nº {item_rdo.id_sequencial} (Rev. {item_rdo.id_revisao}) salvo com sucesso!", "success")
        return redirect(url_for('auth.visualizar_rdo', rdo_id=item_rdo.id))

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erro ao gerar RDO: {e}")
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
        tags_options=tags_options
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
        if u.id == item.id_usuario or u.id in ids_usuarios_que_assinaram or u.papel in ['Admin', 'Engenheiro', 'Supervisor']:
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

    return render_template("list_rdo.html", rdos=rdos)

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

    # Injeta atributo dinâmico 'nome_supervisor' em cada usuário (None se admin/sem supervisor)
    for u in usuarios:
        nome_sup = None
        try:
            if u.id_supervisor is not None and str(u.id_supervisor).strip() != '':
                sup_id = int(str(u.id_supervisor).strip())
                nome_sup = sup_map.get(sup_id)
        except Exception:
            nome_sup = None
        setattr(u, 'nome_supervisor', nome_sup)

    # Passamos explicitamente 'opcoes' e 'categoria' para o template
    return render_template("list_usuarios.html", opcoes=usuarios, categoria="usuario")

# Abrir Formulário de Cadastro de Usuario

@auth_bp.get("/criar-usuario")
@login_required
def criar_usuario():
    # from app.models.obra import Obra # Não é necessário
    
    # ADICIONADO: Obter a hierarquia das obras
    obra_hierarchy = get_obra_hierarchy_for_user_form()
    
    # Determina o Admin padrão para uso no template
    from app.models.usuario import Usuario
    admin = Usuario.query.filter_by(papel='Admin').first()
    default_supervisor = {'id': admin.id, 'nome': admin.nome} if admin else None

    # Passamos categoria='usuario' para o template saber qual seção renderizar
    return render_template(
        "form_usuario.html", 
        categoria="usuario", 
        obra_hierarchy=obra_hierarchy,
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
    # Todas as obras é opcional, mas vamos manter o padrão do seu código
    todas_obras = Obra.query.all()
    
    # 1. ADICIONAR: Busca a hierarquia das obras no início da função
    obra_hierarchy = get_obra_hierarchy_for_user_form()

    if categoria == "usuario":
        nome = request.form.get("nome")
        email = request.form.get("email")
        papel = request.form.get("papel")
        cpf = request.form.get("cpf") 
        senha = request.form.get("senha")
        # Captura o status do checkbox (True se marcado, False caso contrário)
        status = True if request.form.get("status") == "on" else False
        obras_ids = request.form.getlist("obras_permitidas")
        # Supervisor (pode ser vazio) - se vazio, será definido como Admin padrão
        id_supervisor_raw = request.form.get('id_supervisor')

        item_form = {'id': user_id, 'nome': nome, 'email': email, 'papel': papel, 'cpf': cpf}

        if user_id:
            user = Usuario.query.get_or_404(user_id)
            # Validação CPF duplicado (exceto o próprio)
            if Usuario.query.filter(Usuario.cpf == cpf, Usuario.id != user_id).first():
                flash("Este CPF já está cadastrado.", "danger")
                # 2. CORRIGIDO: Passa obra_hierarchy em caso de erro
                return render_template("form_usuario.html", item=item_form, todas_obras=todas_obras, obra_hierarchy=obra_hierarchy)
            
            user.nome, user.email, user.papel, user.cpf, user.status = nome, email, papel, cpf, status
            # Atualiza id_supervisor se fornecido
            try:
                user.id_supervisor = int(id_supervisor_raw) if id_supervisor_raw else None
            except Exception:
                user.id_supervisor = None
        else:
            if Usuario.query.filter_by(cpf=cpf).first():
                flash("CPF já cadastrado.", "danger")
                # 3. CORRIGIDO: Passa obra_hierarchy em caso de erro
                return render_template("form_usuario.html", item=item_form, todas_obras=todas_obras, obra_hierarchy=obra_hierarchy)

            user = Usuario(nome=nome, email=email, papel=papel, cpf=cpf, status=status)
            try:
                user.id_supervisor = int(id_supervisor_raw) if id_supervisor_raw else None
            except Exception:
                user.id_supervisor = None
            user.set_senha(senha if senha else "EnfilSA@")
            db.session.add(user)

        # MODIFICADO: Diferencia entre Admin e outros papéis
        if papel == 'Admin':
            # Admin: vincula a todas as matrizes ativas
            todas_matrizes = Obra.query.filter(Obra.id_matriz.is_(None), Obra.status == 1).all()
            user.obras_permitidas = todas_matrizes
        else:
            # Outros papéis: vincula apenas as matrizes selecionadas (não filiais específicas)
            # Extrai apenas as matrizes das IDs selecionadas
            matrizes_selecionadas = []
            for oid in obras_ids:
                obra = Obra.query.get(int(oid))
                if obra:
                    # Se for uma matriz (id_matriz é None ou 0), adiciona
                    if obra.id_matriz is None or obra.id_matriz == 0:
                        matrizes_selecionadas.append(obra)
                    # Se for uma filial, adiciona sua matriz (se não estiver duplicada)
                    elif obra.id_matriz and obra.id_matriz > 0:
                        matriz = Obra.query.get(obra.id_matriz)
                        if matriz and matriz not in matrizes_selecionadas:
                            matrizes_selecionadas.append(matriz)
            
            # Vincula apenas as matrizes (filiais serão acessadas dinamicamente)
            user.obras_permitidas = matrizes_selecionadas

        # Se id_supervisor está vazio/None, define primeiro Admin como supervisor padrão
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
            # 4. CORRIGIDO: Passa obra_hierarchy em caso de sucesso
            return render_template("form_usuario.html", item=user, todas_obras=todas_obras, view_mode=True, obra_hierarchy=obra_hierarchy)
        except Exception as e:
            db.session.rollback()
            flash(f"Erro: {str(e)}", "danger")
            # 5. CORRIGIDO: Passa obra_hierarchy em caso de erro de DB
            return render_template("form_usuario.html", item=item_form, todas_obras=todas_obras, obra_hierarchy=obra_hierarchy)

# Mudar Status do Usuário (POST)

@auth_bp.post("/mudar-status-usuario/<int:userId>")
@login_required
def toggle_user_status(userId):
    from app.models.usuario import Usuario
    from flask import jsonify
    
    # Busca o usuário no banco
    user = Usuario.query.get_or_404(userId)
    
    # Inverte o status booleano (Se era True vira False, se era 1 vira 0)
    user.status = not user.status 
    
    try:
        db.session.commit()
        return jsonify({"message": "Status atualizado com sucesso", "status": user.status}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Erro ao atualizar: {str(e)}"}), 500
    
    
# Rota de Reset de Senha corrigida

@auth_bp.post("/usuario-reset/<int:id>")
@login_required
def reset_senha_usuario(id):
    from app.models.usuario import Usuario
    user = Usuario.query.get_or_404(id)
    user.set_senha("EnfilSA@") # Senha padrão solicitada
    db.session.commit()
    return {"message": "Sucesso"}, 200

# Editar Usuário
        
@auth_bp.route("/editar-usuario/<int:id>", methods=['GET', 'POST'])
@login_required
def editar_usuario(id):
    # CORREÇÃO 1: Importar a CLASSE Usuario diretamente (se necessário no escopo)
    from app.models.usuario import Usuario 
    from app.models.obra import Obra
    
    # CORREÇÃO 2: Acessar a classe Usuario e não o módulo 'usuario'
    # user = usuario.Usuario.query.get_or_404(id) # <-- Linha anterior, que causava problemas
    user = Usuario.query.get_or_404(id)
    # todas_obras = Obra.query.all() # Não é mais necessário buscar todas as obras aqui
    
    # CORREÇÃO 3: REMOVER A LÓGICA DE HIERARQUIA MANUAL E CHAMAR O HELPER CORRETO
    # Todo o bloco de código que criava 'obra_hierarchy' manualmente deve ser removido.
    obra_hierarchy = get_obra_hierarchy_for_user_form() # <-- CHAMA A FUNÇÃO CORRETA

    return render_template(
        "form_usuario.html", 
        item=user, 
        categoria="usuario", 
        # todas_obras=todas_obras, # Não é mais estritamente necessário, mas pode ser mantido
        obra_hierarchy=obra_hierarchy # Agora passa a estrutura correta
    )
    
# Visualizar Usuário

@auth_bp.get("/visualizar-usuario/<int:id>")
def visualizar_usuario(id):
    from app.models.usuario import Usuario
    from app.models.obra import Obra
    
    user = Usuario.query.get_or_404(id)
    todas_obras = Obra.query.all()
    
    obra_hierarchy = get_obra_hierarchy_for_user_form()
    # Se a rota é '/usuario/visualizar/<id>', view_mode é True.
    # Verifica a rota da requisição para determinar o modo.
    view_mode = True
    # O item de usuário já deve ter a lista de obras, 
    # mas se o relacionamento não estiver carregado, você pode forçar aqui:
    # item.obras_permitidas # Garante que o relacionamento Many-to-Many está carregado

    # Monta a cadeia de supervisores para exibição
    supervisor_chain = get_supervisor_chain_for_user(user)

    # Se o usuário tiver id_supervisor e ainda não tiver nome_supervisor injetado,
    # tenta popular nome do supervisor imediato
    nome_supervisor = None
    if getattr(user, 'id_supervisor', None):
        try:
            sup = Usuario.query.get(int(user.id_supervisor))
            nome_supervisor = sup.nome if sup else None
        except Exception:
            nome_supervisor = None

    setattr(user, 'nome_supervisor', nome_supervisor)

    # Default supervisor (Admin) caso não exista
    default_supervisor = None
    try:
        admin = Usuario.query.filter_by(papel='Admin').first()
        if admin:
            default_supervisor = {'id': admin.id, 'nome': admin.nome}
    except Exception:
        default_supervisor = None

    return render_template("form_usuario.html", item=user, categoria="usuario", todas_obras=todas_obras, view_mode=view_mode, obra_hierarchy=obra_hierarchy, supervisor_chain=supervisor_chain, default_supervisor=default_supervisor)

# Endpoint que retorna lista de usuários para selecionar como supervisor

@auth_bp.get('/supervisores')
@login_required
def lista_supervisores():
    from app.models.usuario import Usuario
    # Retorna todos os usuários (id + nome) ordenados por nome
    users = Usuario.query.order_by(Usuario.nome.asc()).all()
    result = [{'id': u.id, 'nome': u.nome, 'papel': u.papel} for u in users]
    from flask import jsonify
    return jsonify(result)

#######################################################################################################
####################################################################################################### CLIMAS
#######################################################################################################

@auth_bp.get("/lista-climas")
@login_required
def lista_climas():
    from app.models.lista_opcoes import Clima
    # Busca todos os climas
    climas = Clima.query.order_by(Clima.nome.asc()).all()
    return render_template("list_climas.html", opcoes=climas, categoria="clima")


@auth_bp.get('/criar-clima')
@login_required
def criar_clima():
    # Mostra formulário para criação
    return render_template('form_clima.html', item=None, view_mode=False)


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


@auth_bp.get('/visualizar-clima/<int:id>')
@login_required
def visualizar_clima(id):
    from app.models.lista_opcoes import Clima
    clima = Clima.query.get_or_404(id)
    return render_template('form_clima.html', item=clima, view_mode=True)


@auth_bp.get('/editar-clima/<int:id>')
@login_required
def editar_clima(id):
    from app.models.lista_opcoes import Clima
    clima = Clima.query.get_or_404(id)
    return render_template('form_clima.html', item=clima, view_mode=False)


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

@auth_bp.get("/lista-equipamentos")
@login_required
def lista_equipamentos():
    from app.models.lista_opcoes import Equipamento
    # Busca todos os equipamentos
    equipamentos = Equipamento.query.order_by(Equipamento.nome.asc()).all()
    return render_template("list_equipamentos.html", opcoes=equipamentos, categoria="equipamento")


@auth_bp.get('/criar-equipamento')
@login_required
def criar_equipamento():
    # Mostra formulário para criação
    return render_template('form_equipamento.html', item=None, view_mode=False)


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

@auth_bp.get('/visualizar-equipamento/<int:id>')
@login_required
def visualizar_equipamento(id):
    from app.models.lista_opcoes import Equipamento
    equipamento = Equipamento.query.get_or_404(id)
    return render_template('form_equipamento.html', item=equipamento, view_mode=True)

@auth_bp.get('/editar-equipamento/<int:id>')
@login_required
def editar_equipamento(id):
    from app.models.lista_opcoes import Equipamento
    equipamento = Equipamento.query.get_or_404(id)
    return render_template('form_equipamento.html', item=equipamento, view_mode=False)

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

@auth_bp.get("/lista-tags-ocorrencias")
@login_required
def lista_tags_ocorrencias():
    from app.models.lista_opcoes import TagOcorrencia
    # Busca todos os tagsOcorrencias
    tagsOcorrencias = TagOcorrencia.query.order_by(TagOcorrencia.nome.asc()).all()
    return render_template("list_tags_ocorrencias.html", opcoes=tagsOcorrencias, categoria="tagsOcorrencias")


@auth_bp.get('/criar-tags-ocorrencias')
@login_required
def criar_tags_ocorrencias():
    # Mostra formulário para criação
    return render_template('form_tags_ocorrencias.html', item=None, view_mode=False)


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

@auth_bp.get('/visualizar-tags-ocorrencias/<int:id>')
@login_required
def visualizar_tags_ocorrencias(id):
    from app.models.lista_opcoes import TagOcorrencia
    tag_ocorrencia = TagOcorrencia.query.get_or_404(id)
    return render_template('form_tags_ocorrencias.html', item=tag_ocorrencia, view_mode=True)

@auth_bp.get('/editar-tags-ocorrencias/<int:id>')
@login_required
def editar_tags_ocorrencias(id):
    from app.models.lista_opcoes import TagOcorrencia
    tag_ocorrencia = TagOcorrencia.query.get_or_404(id)
    return render_template('form_tags_ocorrencias.html', item=tag_ocorrencia, view_mode=False)

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


@auth_bp.get('/criar-mao-obra')
@login_required
def criar_mao_obra():
    # Mostra formulário para criação
    return render_template(
        'form_mao_obra.html',
        item=None,
        view_mode=False
    )


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
    
    # 1. Cria um alias (t2) para a tabela Obra. Este alias representará a Matriz/Pai.
    Matriz = aliased(Obra)
    
    # 2. Constrói a consulta com o Self-Join (LEFT OUTER JOIN)
    # Selecionamos a Obra (t1) e o nome da Matriz (t2) com o alias 'nome_matriz'
    # db.session.query é o método padrão para consultas complexas no SQLAlchemy
    consulta = db.session.query(
        Obra,
        # Seleciona o nome da Matriz, atribuindo o nome de coluna 'nome_matriz'
        Matriz.nome.label('nome_matriz')
    ).outerjoin(
        # Condição de Junção: Obra.id_matriz (da Obra Filha) = Matriz.id (da Obra Pai)
        Matriz,
        Obra.id_matriz == Matriz.id
    ).order_by(Obra.id.asc())
    
    resultados = consulta.all()
    
    # 3. Formata os resultados para o Template Jinja
    obras_formatadas = []
    for obra_obj, nome_matriz in resultados:
        # Cria um dicionário com os atributos necessários para o template
        # Isso é mais seguro do que usar obra_obj.__dict__.copy()
        obra_dict = {
            'id': obra_obj.id,
            'nome': obra_obj.nome,
            'cnpj': obra_obj.cnpj,
            'cliente': obra_obj.contratante,
            'id_matriz': obra_obj.id_matriz,
            'cidade': obra_obj.cidade,
            'estado': obra_obj.estado,
            'endereco': obra_obj.endereco,
            'numero': obra_obj.numero,
            'complemento': obra_obj.complemento, # Importante: Certifique-se que este campo existe no modelo Obra
            'bairro': obra_obj.bairro,
            'cep': obra_obj.cep,
            'status': obra_obj.status,
            # 'nome_matriz' é o resultado do JOIN, adicionado ao dicionário
            'nome_matriz': nome_matriz,
        }
        
        obras_formatadas.append(obra_dict)
    
    # ... o restante da função fica igual
    return render_template("list_obras.html", opcoes=obras_formatadas, categoria="obra")
def get_matrix_options():
    """Busca todas as Obras que são Matrizes (id_matriz é NULL ou 0)"""
    # Adiciona a importação, caso Obra ainda não esteja no escopo
    from app.models.obra import Obra
    
    # Filtra por id_matriz NULL ou 0 para ser robusto com a lógica do HTML
    return Obra.query.filter(or_(Obra.id_matriz.is_(None), Obra.id_matriz == 0)).all()
def fetch_single_obra_with_matriz_name(id_obra):
    """Busca uma única Obra por ID e injeta o nome da Matriz (se for filial)"""
    from app.models.obra import Obra # Adiciona a importação
    
    Matriz = aliased(Obra)
    query = Obra.query.outerjoin(Matriz, Obra.id_matriz == Matriz.id)
    
    # Busca a Obra e o nome da Matriz associada
    result = query.with_entities(Obra, Matriz.nome.label('nome_matriz')).filter(Obra.id == id_obra).first()
    
    if result:
        # Se for encontrado, 'result' é uma tupla onde o primeiro elemento é o objeto Obra
        item = result[0]
        # Injeta o atributo 'nome_matriz' no objeto Obra para acesso no template
        setattr(item, 'nome_matriz', result.nome_matriz)
        return item
    
    return None
def get_obra_hierarchy_for_user_form():
    """Busca todas as obras e agrupa filiais sob suas matrizes."""
    from app.models.obra import Obra
    
    # Busca todas as obras ativas
    todas_obras = Obra.query.filter(Obra.status == 1).all()
    
    hierarchy = {}
    
    # 1. Popula as Matrizes (id_matriz = None ou 0)
    for obra in todas_obras:
        if obra.id_matriz is None or obra.id_matriz == 0:
            hierarchy[obra.id] = {
                'matriz': obra,
                'filiais': []
            }

    # 2. Popula as Filiais
    for obra in todas_obras:
        if obra.id_matriz and obra.id_matriz in hierarchy:
            hierarchy[obra.id_matriz]['filiais'].append(obra)
        elif obra.id_matriz and obra.id_matriz not in hierarchy:
            # Caso raro: Filial sem Matriz ativa. Pode ser ignorado ou logado.
            pass

    return hierarchy
def get_supervisor_chain_for_user(user):
    """Retorna lista de supervisores ascendentes a partir do usuário.
    Exemplo: [ {id, nome}, {id, nome}, ... ] onde o primeiro é o supervisor imediato.
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
        chain.append({'id': sup.id, 'nome': sup.nome})
        visited.add(sup.id)
        current = sup

    return chain

# Rota para criar nova obra

@auth_bp.get("/criar-obra")
@login_required
def criar_obra():
    from app.models.obra import Obra
    from app.models.usuario import Usuario
    
    # Busca apenas as obras que são Matrizes para o dropdown
    opcoes_matriz = get_matrix_options()
    usuarios = Usuario.query.filter_by(status=1).all()
    
    # Passa opcoes_matriz para o template
    return render_template("form_obra.html", item=None, opcoes_matriz=opcoes_matriz, usuarios=usuarios)

# Rota para mudar status da obra (POST)

@auth_bp.post("/mudar-status-obras/<int:obraid>")
@login_required
def toggle_user_obras(obraid):
    from app.models.usuario import Obra
    
    # Busca o usuário no banco
    obra = Obra.query.get_or_404(obraid)
    
    # Inverte o status booleano (Se era True vira False, se era 1 vira 0)
    obra.status = not obra.status 
    
    try:
        db.session.commit()
        return {"message": "Status atualizado com sucesso"}, 200
    except Exception as e:
        db.session.rollback()
        return {"message": f"Erro ao atualizar: {str(e)}"}, 500
    
# Rota para salvar obra

@auth_bp.route('/gerar-obra', methods=['POST'])
@login_required
def gerar_obra():
    from app.models.obra import Obra, Frente_Trabalho
    
    # 1. Obter Dados do Formulário
    id_obra = request.form.get("id")
    # Se id_obra vier vazio, garante que seja None para facilitar checagens
    if not id_obra: id_obra = None

    cnpj = request.form.get('cnpj')

    # --- VALIDAÇÃO DE DUPLICIDADE DE CNPJ ---
    # Verifica se já existe alguma obra com este CNPJ no banco
    obra_existente = Obra.query.filter_by(cnpj=cnpj).first()

    if obra_existente:
        # Se estamos criando uma obra nova (id_obra é None) E já achamos um CNPJ igual: ERRO
        # OU se estamos editando (id_obra existe), mas o ID da obra achada é DIFERENTE do ID que estamos editando: ERRO
        if not id_obra or str(obra_existente.id) != str(id_obra):
            flash(f"Erro: O CNPJ {cnpj} já está cadastrado para a obra '{obra_existente.nome}'.", "danger")
            return redirect(url_for('auth.lista_obras'))
            # Nota: Idealmente redirecionaríamos de volta para o form com os dados preenchidos,
            # mas para simplificar e garantir segurança, voltamos para a lista.

    # 2. Coleta dos demais dados
    nome = request.form.get('nome')
    contratante = request.form.get('contratante')
    contrato = request.form.get('contrato')
    id_responsavel = request.form.get('id_responsavel')
    id_matriz = request.form.get('id_matriz')
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
            obra.id_matriz = int(id_matriz) if id_matriz else None
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
                id_matriz=int(id_matriz) if id_matriz else None,
                inicio=inicio, termino=termino,
                cep=cep, endereco=endereco, numero=numero, complemento=complemento,
                bairro=bairro, cidade=cidade, estado=estado, status=status
            )
            db.session.add(obra)
            
            # CRUCIAL: flush() envia o INSERT para o banco e popula obra.id
            # sem fechar a transação. Isso permite vincular as frentes logo abaixo.
            db.session.flush() 
            
            flash("Obra cadastrada com sucesso!", "success")

        # --- PROCESSAMENTO DAS FRENTES (Comum a Criação e Edição) ---
        if frentes_payload:
            data = json.loads(frentes_payload)
            
            # 1. Remover frentes marcadas para exclusão
            for f_id in data.get('removidas', []):
                Frente_Trabalho.query.filter_by(id_frente_trabalho=f_id, id_obra=obra.id).delete()
            
            # 2. Adicionar novas frentes
            for f_nova in data.get('novas', []):
                nova_frente = Frente_Trabalho(
                    id_obra=obra.id, # AQUI O ID JÁ EXISTE (graças ao flush ou query.get)
                    nome_frente=f_nova['nome_frente'],
                    id_responsavel=f_nova['id_responsavel'] if f_nova['id_responsavel'] else None
                )
                db.session.add(nova_frente)

        db.session.commit()
        return redirect(url_for('auth.lista_obras'))

    except Exception as e:
        db.session.rollback()
        print(f"Erro ao salvar obra: {e}")
        # Se for erro de integridade que passou pela nossa validação manual
        if "Duplicate entry" in str(e):
             flash(f"Erro: CNPJ já existente no sistema.", "danger")
        else:
             flash(f"Erro ao processar a solicitação: {str(e)}", "danger")
        
        return redirect(url_for('auth.lista_obras'))
    
# Rota pra editar obra

@auth_bp.get("/editar-obra/<int:id>")
@login_required
def editar_obra(id):
    from app.models.usuario import Usuario
    # Usa o helper para buscar a Obra com o nome da Matriz
    item = fetch_single_obra_with_matriz_name(id)
    
    obra = Obra.query.get_or_404(id)
    # Busca todas as frentes vinculadas a essa obra
    frentes = Frente_Trabalho.query.filter_by(id_obra=id).all()
    
    usuarios = Usuario.query.filter_by(status=1).all() # Apenas usuários ativos
    
    # Busca outras obras para o select de Matriz
    opcoes_matriz = Obra.query.all()
    
    if not item:
        abort(404) # Not Found
    
    # Busca as opções de Matriz
    opcoes_matriz = get_matrix_options()
    
    # Passa as opções de matrizes e o item com nome_matriz para o template
    return render_template("form_obra.html", item=item, opcoes_matriz=opcoes_matriz, frentes=frentes, usuarios=usuarios)

# Rota para visualizar obra
@auth_bp.get("/visualizar-obra/<int:id>")
@login_required
def visualizar_obra(id):
    from app.models.obra import Obra
    from app.models.usuario import Usuario
    
    # Busca o item de Obra
    item = Obra.query.get_or_404(id) 
    item = fetch_single_obra_with_matriz_name(id)

    # Define view_mode como True para bloquear os campos no template
    view_mode = True
    if not item:
        abort(404)
        
    opcoes_matriz = get_matrix_options()
    usuarios = Usuario.query.filter_by(status=1).all() # Apenas usuários ativos
    
    frentes = Frente_Trabalho.query.filter_by(id_obra=id).all()

    usuario = Usuario.query.order_by(Usuario.nome).all()
    
    # Renderiza o template passando o item e o view_mode
    return render_template(
        "form_obra.html", 
        item=item, 
        view_mode=view_mode, 
        categoria="obra",
        opcoes_matriz=opcoes_matriz, # Importante passar isso para o <select> funcionar
        frentes=frentes,
        usuario=usuario,
        usuarios=usuarios
    )

# Rota para toggle de status da obra (usado em list_obras.html)

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
        return '', 200 # Retorna 200 OK para o JavaScript
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao alternar status da obra: {e}")
        return '', 500 # Retorna erro 500