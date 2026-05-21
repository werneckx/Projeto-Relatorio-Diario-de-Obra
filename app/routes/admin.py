import os
from functools import wraps
from datetime import datetime

from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, session, current_app, jsonify
)
from werkzeug.utils import secure_filename
from PIL import Image

from app import db
from app.models.empresa import Empresa
from app.models.usuario import Usuario, Papel, Permissao, PapelPermissao, Colaborador, UsuarioPapel
from app.models.fornecedor import Fornecedor
from app.models.configuracao import ConfigDefinicao, EmpresaConfig, ObraConfig
from app.models.obra import Obra
from app.services.config_service import ConfigService

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# ---------------------------------------------------------------------------
# Roles padrão do sistema (espelha o seed do SQL)
# ---------------------------------------------------------------------------
SYSTEM_ROLES = [
    {'nome': 'ADMIN',        'descricao': 'Controle total sobre a empresa'},
    {'nome': 'GESTOR',       'descricao': 'Gestão operacional: RDO, equipes, aprovações'},
    {'nome': 'OPERADOR',     'descricao': 'Input operacional: lançamentos de RDO'},
    {'nome': 'LEITOR',       'descricao': 'Somente leitura de dados da empresa'},
    {'nome': 'CLIENTE_OBRA', 'descricao': 'Acesso externo restrito: visualização e assinatura'},
]

SYSTEM_PERMISSIONS = [
    {'chave': 'empresa.create',    'descricao': 'Criar novas empresas no sistema'},
    {'chave': 'empresa.view',      'descricao': 'Visualizar dados da empresa'},
    {'chave': 'empresa.manage',    'descricao': 'Gerenciar configurações da empresa'},
    {'chave': 'usuario.manage',    'descricao': 'Gerenciar usuários da empresa'},
    {'chave': 'rdo.create',        'descricao': 'Criar novos RDOs'},
    {'chave': 'rdo.update',        'descricao': 'Editar RDOs existentes'},
    {'chave': 'rdo.approve',       'descricao': 'Aprovar ou rejeitar RDOs'},
    {'chave': 'rdo.view',          'descricao': 'Visualizar RDOs'},
    {'chave': 'fornecedor.manage', 'descricao': 'Gerenciar fornecedores da empresa'},
    {'chave': 'obra.manage',       'descricao': 'Gerenciar obras e frentes de trabalho'},
    {'chave': 'colaborador.manage','descricao': 'Gerenciar colaboradores e equipes'},
]

ROLE_PERMISSION_MAP = {
    'ADMIN':        None,  # None = todas as permissões
    'GESTOR':       ['empresa.view','usuario.manage','rdo.create','rdo.update',
                     'rdo.approve','rdo.view','fornecedor.manage','obra.manage','colaborador.manage'],
    'OPERADOR':     ['rdo.create','rdo.update','rdo.view','empresa.view','colaborador.manage'],
    'LEITOR':       ['rdo.view','empresa.view'],
    'CLIENTE_OBRA': ['rdo.view','rdo.approve'],
}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ---------------------------------------------------------------------------
# Decorators
# ---------------------------------------------------------------------------

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash("Você precisa estar logado.", "warning")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated


def permission_required(chave):
    """Exige que o usuário autenticado possua a permissão especificada."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                return redirect(url_for('auth.login'))
            user = Usuario.query.get(session['user_id'])
            if not user or not user.tem_permissao(chave):
                flash("Você não tem permissão para executar esta ação.", "danger")
                return redirect(url_for('auth.inicio'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# ---------------------------------------------------------------------------
# Utilitário: garantir roles e permissões globais no banco
# ---------------------------------------------------------------------------

def seed_system_roles_and_permissions():
    """
    Garante que os papéis e permissões globais do sistema existam no banco.
    Chamado no setup inicial e pode ser chamado manualmente.
    """
    all_perms = {}
    for pdef in SYSTEM_PERMISSIONS:
        perm = Permissao.query.filter_by(chave=pdef['chave'], empresa_id=None).first()
        if not perm:
            perm = Permissao(
                empresa_id=None,
                chave=pdef['chave'],
                descricao=pdef['descricao'],
                is_system=True,
                ativo=True
            )
            db.session.add(perm)
            db.session.flush()
        all_perms[pdef['chave']] = perm

    for rdef in SYSTEM_ROLES:
        papel = Papel.query.filter_by(nome=rdef['nome'], empresa_id=None).first()
        if not papel:
            papel = Papel(
                empresa_id=None,
                nome=rdef['nome'],
                descricao=rdef['descricao'],
                is_system=True,
                ativo=True
            )
            db.session.add(papel)
            db.session.flush()

        # Mapeia permissões
        chaves_permitidas = ROLE_PERMISSION_MAP.get(rdef['nome'])
        perms_para_vincular = list(all_perms.values()) if chaves_permitidas is None else [
            all_perms[c] for c in chaves_permitidas if c in all_perms
        ]

        for perm in perms_para_vincular:
            existente = PapelPermissao.query.filter_by(
                papel_id=papel.id, permissao_id=perm.id, empresa_id=None
            ).first()
            if not existente:
                db.session.add(PapelPermissao(
                    empresa_id=None,
                    papel_id=papel.id,
                    permissao_id=perm.id,
                    ativo=True
                ))

    db.session.commit()


# ---------------------------------------------------------------------------
# EMPRESAS
# ---------------------------------------------------------------------------

@admin_bp.get("/empresas")
@login_required
@permission_required('empresa.create')
def listar_empresas():
    empresas = Empresa.query.order_by(Empresa.nome).all()
    return render_template("admin/empresas_lista.html", empresas=empresas)


@admin_bp.route("/empresas/nova", methods=["GET", "POST"])
@login_required
@permission_required('empresa.create')
def nova_empresa():
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        logo_file = request.files.get("logo_empresa")
        icone_file = request.files.get("icone_empresa")

        if not nome:
            flash("Nome da empresa é obrigatório.", "danger")
            return render_template("admin/empresa_form.html", empresa=None)

        try:
            nova = Empresa(
                nome=nome,
                ativo=True,
                criado_por=session.get('user_id')
            )
            db.session.add(nova)
            db.session.flush()

            upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'empresas', str(nova.id))
            os.makedirs(upload_folder, exist_ok=True)

            if logo_file and logo_file.filename and allowed_file(logo_file.filename):
                logo_path = _save_image(logo_file, upload_folder, "logo.png")
                nova.logo_empresa = f"uploads/empresas/{nova.id}/logo.png"

            if icone_file and icone_file.filename and allowed_file(icone_file.filename):
                icone_path = _save_image(icone_file, upload_folder, "icone.png", thumb=(128, 128))
                nova.icone_empresa = f"uploads/empresas/{nova.id}/icone.png"

            db.session.commit()
            flash(f'Empresa "{nova.nome}" criada com sucesso!', "success")
            return redirect(url_for("admin.listar_empresas"))

        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao criar empresa: {str(e)}", "danger")

    return render_template("admin/empresa_form.html", empresa=None)


@admin_bp.route("/empresas/<int:empresa_id>/editar", methods=["GET", "POST"])
@login_required
@permission_required('empresa.manage')
def editar_empresa(empresa_id):
    empresa = Empresa.query.get_or_404(empresa_id)

    if request.method == "POST":
        empresa.nome = request.form.get("nome", empresa.nome).strip()
        empresa.modificado_por = session.get('user_id')

        logo_file = request.files.get("logo_empresa")
        icone_file = request.files.get("icone_empresa")

        upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'empresas', str(empresa.id))
        os.makedirs(upload_folder, exist_ok=True)

        if logo_file and logo_file.filename and allowed_file(logo_file.filename):
            _save_image(logo_file, upload_folder, "logo.png")
            empresa.logo_empresa = f"uploads/empresas/{empresa.id}/logo.png"

        if icone_file and icone_file.filename and allowed_file(icone_file.filename):
            _save_image(icone_file, upload_folder, "icone.png", thumb=(128, 128))
            empresa.icone_empresa = f"uploads/empresas/{empresa.id}/icone.png"

        try:
            db.session.commit()
            flash("Empresa atualizada com sucesso!", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao salvar: {str(e)}", "danger")

        return redirect(url_for("admin.listar_empresas"))

    return render_template("admin/empresa_form.html", empresa=empresa)


# ---------------------------------------------------------------------------
# FORNECEDORES (por empresa)
# ---------------------------------------------------------------------------

@admin_bp.get("/fornecedores")
@login_required
@permission_required('fornecedor.manage')
def listar_fornecedores():
    empresa_id = session.get('empresa_id')
    fornecedores = Fornecedor.query.filter_by(empresa_id=empresa_id).order_by(Fornecedor.nome).all()
    return render_template("admin/fornecedores_lista.html", fornecedores=fornecedores)


@admin_bp.route("/fornecedores/novo", methods=["GET", "POST"])
@login_required
@permission_required('fornecedor.manage')
def novo_fornecedor():
    empresa_id = session.get('empresa_id')

    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        cnpj = request.form.get("cnpj", "").strip() or None
        endereco = request.form.get("endereco", "").strip() or None

        if not nome:
            flash("Nome do fornecedor é obrigatório.", "danger")
            return render_template("admin/fornecedor_form.html", fornecedor=None)

        # Verifica duplicidade de CNPJ na empresa
        if cnpj:
            existente = Fornecedor.query.filter_by(empresa_id=empresa_id, cnpj=cnpj).first()
            if existente:
                flash(f"Já existe um fornecedor com CNPJ {cnpj} nesta empresa.", "warning")
                return render_template("admin/fornecedor_form.html", fornecedor=None)

        try:
            forn = Fornecedor(
                empresa_id=empresa_id,
                nome=nome,
                cnpj=cnpj,
                endereco=endereco,
                ativo=True,
                criado_por=session.get('user_id')
            )
            db.session.add(forn)
            db.session.commit()
            flash(f'Fornecedor "{forn.nome}" cadastrado com sucesso!', "success")
            return redirect(url_for("admin.listar_fornecedores"))
        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao cadastrar fornecedor: {str(e)}", "danger")

    return render_template("admin/fornecedor_form.html", fornecedor=None)


@admin_bp.route("/fornecedores/<int:forn_id>/editar", methods=["GET", "POST"])
@login_required
@permission_required('fornecedor.manage')
def editar_fornecedor(forn_id):
    empresa_id = session.get('empresa_id')
    forn = Fornecedor.query.filter_by(id=forn_id, empresa_id=empresa_id).first_or_404()

    if request.method == "POST":
        forn.nome = request.form.get("nome", forn.nome).strip()
        forn.cnpj = request.form.get("cnpj", "").strip() or None
        forn.endereco = request.form.get("endereco", "").strip() or None
        forn.modificado_por = session.get('user_id')

        try:
            db.session.commit()
            flash("Fornecedor atualizado com sucesso!", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao salvar: {str(e)}", "danger")

        return redirect(url_for("admin.listar_fornecedores"))

    return render_template("admin/fornecedor_form.html", fornecedor=forn)


@admin_bp.post("/fornecedores/<int:forn_id>/desativar")
@login_required
@permission_required('fornecedor.manage')
def desativar_fornecedor(forn_id):
    empresa_id = session.get('empresa_id')
    forn = Fornecedor.query.filter_by(id=forn_id, empresa_id=empresa_id).first_or_404()
    forn.ativo = False
    forn.modificado_por = session.get('user_id')
    db.session.commit()
    flash(f'Fornecedor "{forn.nome}" desativado.', "info")
    return redirect(url_for("admin.listar_fornecedores"))


# API JSON para uso em selects dinâmicos
@admin_bp.get("/api/fornecedores")
@login_required
def api_fornecedores():
    empresa_id = session.get('empresa_id')
    fornecedores = Fornecedor.query.filter_by(empresa_id=empresa_id, ativo=True).order_by(Fornecedor.nome).all()
    return jsonify([f.to_dict() for f in fornecedores])


# ---------------------------------------------------------------------------
# Helper: salvar imagem com redimensionamento
# ---------------------------------------------------------------------------

def _save_image(file_obj, folder, filename, thumb=None):
    path = os.path.join(folder, filename)
    try:
        img = Image.open(file_obj)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        if thumb:
            img.thumbnail(thumb, Image.LANCZOS)
        img.save(path, optimize=True, quality=85)
    except Exception:
        file_obj.stream.seek(0)
        file_obj.save(path)
    return path


# ---------------------------------------------------------------------------
# CONFIGURAÇÕES POR EMPRESA / OBRA
# ---------------------------------------------------------------------------


@admin_bp.get('/configuracoes')
@login_required
@permission_required('config.manage')
def listar_configuracoes():
    empresa_id = session.get('empresa_id')
    definicoes = ConfigDefinicao.query.order_by(ConfigDefinicao.chave).all()
    # Carrega valores atuais para exibição
    valores = {}
    for d in definicoes:
        emp_cfg = EmpresaConfig.query.filter_by(empresa_id=empresa_id, chave=d.chave).first()
        valores[d.chave] = emp_cfg.valor if emp_cfg and emp_cfg.valor is not None else d.valor_padrao
    return render_template('admin/configuracoes_empresa.html', definicoes=definicoes, valores=valores)


@admin_bp.route('/configuracoes/<chave>/editar', methods=['GET', 'POST'])
@login_required
@permission_required('config.manage')
def editar_configuracao(chave):
    empresa_id = session.get('empresa_id')
    definicao = ConfigDefinicao.query.filter_by(chave=chave).first_or_404()
    emp_cfg = EmpresaConfig.query.filter_by(empresa_id=empresa_id, chave=chave).first()

    if request.method == 'POST':
        valor = request.form.get('valor')
        # Validação básica pelo tipo
        valid = True
        if definicao.tipo == 'INT':
            try:
                int(valor)
            except Exception:
                valid = False
        elif definicao.tipo == 'JSON':
            try:
                import json as _json
                _json.loads(valor)
            except Exception:
                valid = False

        if not valid:
            flash('Valor inválido para o tipo definido.', 'danger')
            return render_template('admin/configuracao_form.html', definicao=definicao, valor=valor)

        try:
            if not emp_cfg:
                emp_cfg = EmpresaConfig(empresa_id=empresa_id, chave=chave, valor=valor)
                db.session.add(emp_cfg)
            else:
                emp_cfg.valor = valor
                emp_cfg.modificado_por = session.get('user_id')
            db.session.commit()
            # Invalidate cache for this company
            try:
                ConfigService.clear_cache(empresa_id)
            except Exception:
                pass
            flash('Configuração salva com sucesso.', 'success')
            return redirect(url_for('admin.listar_configuracoes'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao salvar: {e}', 'danger')

    return render_template('admin/configuracao_form.html', definicao=definicao, valor=(emp_cfg.valor if emp_cfg else definicao.valor_padrao))


@admin_bp.get('/obras/<int:obra_id>/configuracoes')
@login_required
@permission_required('config.manage')
def listar_configuracoes_obra(obra_id):
    empresa_id = session.get('empresa_id')
    obra = Obra.query.filter_by(id=obra_id, empresa_id=empresa_id).first_or_404()
    definicoes = ConfigDefinicao.query.order_by(ConfigDefinicao.chave).all()
    valores = {}
    for d in definicoes:
        valores[d.chave] = ConfigService.obter_valor(empresa_id=empresa_id, obra_id=obra_id, chave=d.chave)
    return render_template('admin/configuracoes_obra.html', definicoes=definicoes, valores=valores, obra=obra)


@admin_bp.route('/obras/<int:obra_id>/configuracoes/<chave>/editar', methods=['GET', 'POST'])
@login_required
@permission_required('config.manage')
def editar_configuracao_obra(obra_id, chave):
    empresa_id = session.get('empresa_id')
    obra = Obra.query.filter_by(id=obra_id, empresa_id=empresa_id).first_or_404()
    definicao = ConfigDefinicao.query.filter_by(chave=chave).first_or_404()
    ocfg = ObraConfig.query.filter_by(empresa_id=empresa_id, obra_id=obra_id, chave=chave).first()

    if request.method == 'POST':
        valor = request.form.get('valor')
        # Validação básica
        valid = True
        if definicao.tipo == 'INT':
            try:
                int(valor)
            except Exception:
                valid = False
        elif definicao.tipo == 'JSON':
            try:
                import json as _json
                _json.loads(valor)
            except Exception:
                valid = False

        if not valid:
            flash('Valor inválido para o tipo definido.', 'danger')
            return render_template('admin/configuracao_form.html', definicao=definicao, valor=valor, obra=obra)

        try:
            if not ocfg:
                ocfg = ObraConfig(empresa_id=empresa_id, obra_id=obra_id, chave=chave, valor=valor)
                db.session.add(ocfg)
            else:
                ocfg.valor = valor
            db.session.commit()
            try:
                ConfigService.clear_cache(empresa_id, obra_id=obra_id)
            except Exception:
                pass
            flash('Configuração da obra salva com sucesso.', 'success')
            return redirect(url_for('admin.listar_configuracoes_obra', obra_id=obra_id))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao salvar: {e}', 'danger')

    return render_template('admin/configuracao_form.html', definicao=definicao, valor=(ocfg.valor if ocfg else definicao.valor_padrao), obra=obra)


# ---------------------------------------------------------------------------
# RBAC: exibir papéis globais e personalizados
# ---------------------------------------------------------------------------


@admin_bp.get('/papeis')
@login_required
@permission_required('usuario.manage')
def listar_papeis():
    empresa_id = session.get('empresa_id')
    papeis_globais = Papel.query.filter_by(empresa_id=None).order_by(Papel.nome).all()
    papeis_empresa = Papel.query.filter_by(empresa_id=empresa_id).order_by(Papel.nome).all()
    return render_template('admin/papeis_lista.html', papeis_globais=papeis_globais, papeis_empresa=papeis_empresa)
