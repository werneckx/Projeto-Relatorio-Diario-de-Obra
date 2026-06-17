import secrets
import string

from app.routes.auth_common import *

from app.models.cliente import Cliente
from app.models.obra import ObraUsuario


def _usuario_acesso_colaborador(colaborador, empresa_id):
    if not colaborador:
        return None
    return next(
        (
            usuario for usuario in getattr(colaborador, "usuarios", [])
            if usuario and usuario.empresa_id == empresa_id
        ),
        None,
    )


def _obras_ativas_para_acesso(empresa_id):
    user = get_current_user()
    if user and user.is_admin:
        return Obra.query.filter_by(empresa_id=empresa_id, status=1).order_by(Obra.nome).all()
    if user:
        return [obra for obra in user.obras_permitidas if obra.status == 1 and obra.empresa_id == empresa_id]
    return []


def _can_manage_access():
    user = get_current_user()
    return bool(user and (getattr(user, "is_admin", False) or user.tem_permissao('usuario.manage')))


def _gerar_senha_forte(tamanho=14):
    alfabeto = string.ascii_letters + string.digits + "!@#$%&*?"
    while True:
        senha = "".join(secrets.choice(alfabeto) for _ in range(tamanho))
        if (
            any(c.islower() for c in senha)
            and any(c.isupper() for c in senha)
            and any(c.isdigit() for c in senha)
            and any(c in "!@#$%&*?" for c in senha)
        ):
            return senha


def _resolver_papel_acesso(nome_papel, empresa_id):
    papel_norm = (nome_papel or ROLE_LEITOR).strip().upper()
    papeis = (
        Papel.query
        .filter(
            Papel.ativo.is_(True),
            func.upper(func.trim(Papel.nome)) == papel_norm,
            or_(Papel.empresa_id == empresa_id, Papel.empresa_id.is_(None)),
        )
        .all()
    )
    if not papeis:
        return None
    return next((papel for papel in papeis if papel.empresa_id == empresa_id), papeis[0])


def _sincronizar_papel_acesso(usuario, nome_papel, empresa_id):
    papel = _resolver_papel_acesso(nome_papel, empresa_id)
    if not papel:
        raise ValueError(f"Papel {nome_papel or ROLE_LEITOR} nao encontrado.")

    db.session.query(UsuarioPapel).filter(
        UsuarioPapel.usuario_id == usuario.id,
        UsuarioPapel.empresa_id == empresa_id,
    ).delete(synchronize_session=False)
    db.session.add(UsuarioPapel(
        empresa_id=empresa_id,
        usuario_id=usuario.id,
        papel_id=papel.id,
        ativo=True,
    ))
    return papel


def _papeis_disponiveis(empresa_id):
    return (
        Papel.query
        .filter(
            Papel.ativo.is_(True),
            or_(Papel.empresa_id == empresa_id, Papel.empresa_id.is_(None)),
        )
        .order_by(Papel.nome.asc())
        .all()
    )


def _preparar_usuario_acesso(colaborador, empresa_id):
    usuario = _usuario_acesso_colaborador(colaborador, empresa_id)
    return hydrate_audit_metadata(usuario) if usuario else None


def _obra_usuario_rows(usuario, empresa_id):
    if not usuario or not getattr(usuario, "id", None):
        return []

    rows = (
        ObraUsuario.query
        .filter_by(empresa_id=empresa_id, usuario_id=usuario.id)
        .order_by(ObraUsuario.id.asc())
        .all()
    )
    return hydrate_audit_metadata(rows)


def _obras_para_acesso_form(empresa_id, usuario=None):
    current_user_obj = get_current_user()
    if current_user_obj and current_user_obj.is_admin:
        base_obras = Obra.query.filter_by(empresa_id=empresa_id).order_by(Obra.nome.asc()).all()
    else:
        base_obras = _obras_ativas_para_acesso(empresa_id)
    obras_por_id = {obra.id: obra for obra in base_obras}
    if usuario and getattr(usuario, "id", None):
        vinculadas = (
            Obra.query
            .join(ObraUsuario, ObraUsuario.obra_id == Obra.id)
            .filter(
                ObraUsuario.empresa_id == empresa_id,
                ObraUsuario.usuario_id == usuario.id,
                Obra.empresa_id == empresa_id,
            )
            .all()
        )
        for obra in vinculadas:
            obras_por_id[obra.id] = obra

    return sorted(obras_por_id.values(), key=lambda obra: (obra.nome or "").lower())


def _as_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _salvar_obras_usuario(usuario, empresa_id, user_id):
    if not usuario or not getattr(usuario, "id", None):
        return

    row_ids = request.form.getlist('obra_usuario_id[]')
    obra_ids = request.form.getlist('obra_usuario_obra_id[]')
    papel_ids = request.form.getlist('obra_usuario_papel_id[]')
    ativos = request.form.getlist('obra_usuario_ativo[]')
    total = max(len(row_ids), len(obra_ids), len(papel_ids), len(ativos), 0)
    current_user_obj = get_current_user()
    allowed_obra_ids = {obra.id for obra in _obras_ativas_para_acesso(empresa_id)}
    allowed_papel_ids = {
        papel.id
        for papel in _papeis_disponiveis(empresa_id)
        if papel and getattr(papel, "id", None)
    }
    seen_obra_ids = set()

    for idx in range(total):
        row_id = _as_int(row_ids[idx] if idx < len(row_ids) else None)
        obra_id = _as_int(obra_ids[idx] if idx < len(obra_ids) else None)
        papel_id = _as_int(papel_ids[idx] if idx < len(papel_ids) else None)
        ativo_raw = ativos[idx] if idx < len(ativos) else '1'
        ativo = str(ativo_raw).strip().lower() in {'1', 'true', 'on', 'ativo'}

        if not obra_id:
            continue
        if not (current_user_obj and current_user_obj.is_admin) and obra_id not in allowed_obra_ids:
            continue
        if papel_id and papel_id not in allowed_papel_ids:
            papel_id = None
        if obra_id in seen_obra_ids:
            continue
        seen_obra_ids.add(obra_id)

        obra = Obra.query.filter_by(id=obra_id, empresa_id=empresa_id).first()
        if not obra:
            continue

        vinculo = None
        if row_id:
            vinculo = ObraUsuario.query.filter_by(
                id=row_id,
                empresa_id=empresa_id,
                usuario_id=usuario.id,
            ).first()
        if not vinculo:
            vinculo = ObraUsuario.query.filter_by(
                empresa_id=empresa_id,
                usuario_id=usuario.id,
                obra_id=obra_id,
            ).first()

        if vinculo:
            vinculo.obra_id = obra_id
            vinculo.papel_id = papel_id
            vinculo.ativo = ativo
            set_audit_on_update(vinculo, user_id=user_id)
        else:
            vinculo = ObraUsuario(
                empresa_id=empresa_id,
                usuario_id=usuario.id,
                obra_id=obra_id,
                papel_id=papel_id,
                ativo=ativo,
            )
            set_audit_on_create(vinculo, user_id=user_id)
            db.session.add(vinculo)


def _associar_todas_obras_usuario(usuario, empresa_id, papel_id, user_id):
    if not usuario or not getattr(usuario, "id", None):
        return

    vinculos = {
        vinculo.obra_id: vinculo
        for vinculo in ObraUsuario.query.filter_by(
            empresa_id=empresa_id,
            usuario_id=usuario.id,
        ).all()
    }
    obras = Obra.query.filter_by(empresa_id=empresa_id).all()
    for obra in obras:
        vinculo = vinculos.get(obra.id)
        if vinculo:
            vinculo.papel_id = papel_id
            vinculo.ativo = True
            set_audit_on_update(vinculo, user_id=user_id)
        else:
            vinculo = ObraUsuario(
                empresa_id=empresa_id,
                usuario_id=usuario.id,
                obra_id=obra.id,
                papel_id=papel_id,
                ativo=True,
            )
            set_audit_on_create(vinculo, user_id=user_id)
            db.session.add(vinculo)


# --- COLABORADORES ---
@auth_bp.get("/lista-colaboradores")
@auth_bp.get("/colaboradores")
@login_required
def lista_colaboradores():
    empresa_id = get_current_empresa_id()
    colaboradores = (
        Colaborador.query
        .filter(Colaborador.empresa_id == empresa_id)
        .order_by(Colaborador.ativo.desc(), Colaborador.nome.asc())
        .all()
    )
    for colaborador in colaboradores:
        usuario_acesso = next(
            (
                usuario for usuario in getattr(colaborador, "usuarios", [])
                if usuario and usuario.empresa_id == empresa_id
            ),
            None,
        )
        setattr(colaborador, "usuario_acesso", usuario_acesso)
    return render_template("cadastros/colaboradores/list_colaboradores.html", opcoes=colaboradores, categoria="colaborador")


@auth_bp.get('/criar-colaborador')
@auth_bp.get('/colaboradores/novo')
@login_required
@role_required(PERM_WRITE_BASIC)
def criar_colaborador():
    empresa_id = get_current_empresa_id()
    fornecedores = Fornecedor.query.filter_by(empresa_id=empresa_id, ativo=True).order_by(Fornecedor.nome.asc()).all()
    clientes = Cliente.query.filter_by(empresa_id=empresa_id, ativo=True).order_by(Cliente.razao_social.asc()).all()
    return render_template(
        'cadastros/colaboradores/form_colaborador.html',
        item=None,
        view_mode=False,
        fornecedores=fornecedores,
        clientes=clientes,
        usuario_acesso=None,
        obra_usuario_rows=[],
        obras=_obras_para_acesso_form(empresa_id),
        can_manage_access=_can_manage_access(),
        papeis=_papeis_disponiveis(empresa_id),
        is_admin_current=bool(get_current_user() and get_current_user().is_admin),
    )


@auth_bp.get('/editar-colaborador/<int:id>')
@auth_bp.get('/colaboradores/<int:id>/editar')
@login_required
@role_required(PERM_WRITE_BASIC)
def editar_colaborador(id):
    empresa_id = get_current_empresa_id()
    item = hydrate_audit_metadata(Colaborador.query.filter_by(id=id, empresa_id=empresa_id).first_or_404())
    item.usuario_acesso = _preparar_usuario_acesso(item, empresa_id)
    fornecedores = Fornecedor.query.filter_by(empresa_id=empresa_id, ativo=True).order_by(Fornecedor.nome.asc()).all()
    clientes = Cliente.query.filter_by(empresa_id=empresa_id, ativo=True).order_by(Cliente.razao_social.asc()).all()
    return render_template(
        'cadastros/colaboradores/form_colaborador.html',
        item=item,
        view_mode=False,
        fornecedores=fornecedores,
        clientes=clientes,
        usuario_acesso=item.usuario_acesso,
        obra_usuario_rows=_obra_usuario_rows(item.usuario_acesso, empresa_id),
        obras=_obras_para_acesso_form(empresa_id, item.usuario_acesso),
        can_manage_access=_can_manage_access(),
        papeis=_papeis_disponiveis(empresa_id),
        is_admin_current=bool(get_current_user() and get_current_user().is_admin),
    )


@auth_bp.get('/visualizar-colaborador/<int:id>')
@auth_bp.get('/colaboradores/<int:id>')
@login_required
def visualizar_colaborador(id):
    empresa_id = get_current_empresa_id()
    item = hydrate_audit_metadata(Colaborador.query.filter_by(id=id, empresa_id=empresa_id).first_or_404())
    item.usuario_acesso = _preparar_usuario_acesso(item, empresa_id)
    fornecedores = Fornecedor.query.filter_by(empresa_id=empresa_id, ativo=True).order_by(Fornecedor.nome.asc()).all()
    clientes = Cliente.query.filter_by(empresa_id=empresa_id, ativo=True).order_by(Cliente.razao_social.asc()).all()
    return render_template(
        'cadastros/colaboradores/form_colaborador.html',
        item=item,
        view_mode=True,
        fornecedores=fornecedores,
        clientes=clientes,
        usuario_acesso=item.usuario_acesso,
        obra_usuario_rows=_obra_usuario_rows(item.usuario_acesso, empresa_id),
        obras=_obras_para_acesso_form(empresa_id, item.usuario_acesso),
        can_manage_access=_can_manage_access(),
        papeis=_papeis_disponiveis(empresa_id),
        is_admin_current=bool(get_current_user() and get_current_user().is_admin),
    )


@auth_bp.post('/gerar-colaborador')
@auth_bp.post('/colaboradores/salvar')
@login_required
@role_required(PERM_WRITE_BASIC)
def gerar_colaborador():
    empresa_id = get_current_empresa_id()
    user_id = get_current_user_id()

    colaborador_id = request.form.get('id')
    nome = _normalize_option_input(request.form.get('nome', ''))
    cadastro_pessoa_fisica = _normalize_option_input(request.form.get('cadastro_pessoa_fisica', ''))
    tipo = (request.form.get('tipo') or 'PROPRIO').strip().upper()
    fornecedor_id_raw = (request.form.get('fornecedor_id') or '').strip() or None
    cliente_id_raw = (request.form.get('cliente_id') or '').strip() or None
    ativo = request.form.get('ativo') == '1'

    if not nome:
        flash('Nome do colaborador é obrigatório.', 'danger')
        return redirect(url_for('auth.criar_colaborador'))

    # Normalização/Coerência de vínculos por tipo
    if tipo == 'PROPRIO':
        fornecedor_id_raw = None
        cliente_id_raw = None
    elif tipo == 'TERCEIRO':
        if not fornecedor_id_raw:
            flash('Colaborador TERCEIRO deve ter um fornecedor vinculado.', 'danger')
            return redirect(url_for('auth.criar_colaborador'))
        cliente_id_raw = None
    elif tipo == 'CLIENTE':
        if not cliente_id_raw:
            flash('Colaborador CLIENTE deve ter um cliente vinculado.', 'danger')
            return redirect(url_for('auth.criar_colaborador'))
        fornecedor_id_raw = None

    fornecedor_id = int(fornecedor_id_raw) if fornecedor_id_raw else None
    cliente_id = int(cliente_id_raw) if cliente_id_raw else None

    if colaborador_id:
        colaborador = Colaborador.query.filter_by(id=colaborador_id, empresa_id=empresa_id).first_or_404()
        colaborador.nome = nome
        colaborador.cadastro_pessoa_fisica = cadastro_pessoa_fisica or None
        colaborador.fornecedor_id = fornecedor_id
        colaborador.cliente_id = cliente_id
        colaborador.tipo = tipo
        colaborador.ativo = ativo
        set_audit_on_update(colaborador, user_id=user_id)
    else:
        colaborador = Colaborador(
            empresa_id=empresa_id,
            nome=nome,
            cadastro_pessoa_fisica=cadastro_pessoa_fisica or None,
            fornecedor_id=fornecedor_id,
            cliente_id=cliente_id,
            tipo=tipo,
            ativo=ativo,
        )
        set_audit_on_create(colaborador, user_id=user_id)
        db.session.add(colaborador)
        db.session.flush()

    usuario_acesso = _usuario_acesso_colaborador(colaborador, empresa_id)
    if not colaborador.ativo and usuario_acesso and usuario_acesso.ativo:
        usuario_acesso.ativo = False
        set_audit_on_update(usuario_acesso, user_id=user_id)

    possui_acesso = request.form.get('possui_acesso') == '1'
    acesso_email = _normalize_option_input(request.form.get('acesso_email', ''))
    if _can_manage_access() and usuario_acesso and not possui_acesso:
        usuario_acesso.ativo = False
        set_audit_on_update(usuario_acesso, user_id=user_id)

    if _can_manage_access() and possui_acesso:
        if not acesso_email:
            flash('E-mail do acesso Ã© obrigatÃ³rio para usuÃ¡rio vinculado.', 'danger')
            return redirect(url_for('auth.editar_colaborador', id=colaborador.id))

        usuario_id = usuario_acesso.id if usuario_acesso else 0
        email_duplicado = Usuario.query.filter(
            Usuario.empresa_id == empresa_id,
            Usuario.email == acesso_email,
            Usuario.id != usuario_id,
        ).first()
        if email_duplicado:
            flash('Este e-mail jÃ¡ estÃ¡ cadastrado.', 'danger')
            return redirect(url_for('auth.editar_colaborador', id=colaborador.id))

        acesso_status_raw = (request.form.get('acesso_status') or '').strip().lower()
        acesso_status = acesso_status_raw in {'1', 'true', 'on', 'ativo'}
        if not colaborador.ativo and acesso_status:
            flash('Nao e permitido manter usuario ativo para colaborador inativo.', 'danger')
            return redirect(url_for('auth.editar_colaborador', id=colaborador.id))

        if not usuario_acesso:
            senha_plana = _gerar_senha_forte() if request.form.get('gerar_senha_aleatoria') == '1' else (request.form.get('senha') or '')
            if not senha_plana:
                flash('Informe uma senha ou use a opcao de gerar senha aleatoria.', 'danger')
                return redirect(url_for('auth.editar_colaborador', id=colaborador.id))
            usuario_acesso = Usuario(
                empresa_id=empresa_id,
                colaborador_id=colaborador.id,
                email=acesso_email,
                ativo=acesso_status,
                troca_senha_obrigatoria=True,
            )
            usuario_acesso.set_senha(senha_plana)
            set_audit_on_create(usuario_acesso, user_id=user_id)
            db.session.add(usuario_acesso)
            db.session.flush()
            if request.form.get('gerar_senha_aleatoria') == '1':
                flash(f'Senha temporaria gerada: {senha_plana}', 'warning')
        else:
            usuario_acesso.email = acesso_email
            usuario_acesso.ativo = acesso_status
            set_audit_on_update(usuario_acesso, user_id=user_id)

        papel = request.form.get('acesso_papel') or ROLE_LEITOR
        papel_acesso = _sincronizar_papel_acesso(usuario_acesso, papel, empresa_id)
        if (papel or '').strip().upper() == ROLE_ADMIN:
            _associar_todas_obras_usuario(usuario_acesso, empresa_id, papel_acesso.id, user_id)
        else:
            _salvar_obras_usuario(usuario_acesso, empresa_id, user_id)

    db.session.commit()
    return redirect(url_for('auth.lista_colaboradores'))


@auth_bp.post('/excluir-colaborador/<int:id>')
@auth_bp.post('/toggle-colaborador/<int:id>')
@auth_bp.post('/colaboradores/<int:id>/toggle-status')
@login_required
@role_required(PERM_MANAGEMENT)
def excluir_colaborador(id):
    empresa_id = get_current_empresa_id()
    user_id = get_current_user_id()
    colaborador = Colaborador.query.filter_by(id=id, empresa_id=empresa_id).first()
    if colaborador:
        if colaborador.ativo:
            set_audit_on_inactivate(colaborador, user_id=user_id)
            usuario_acesso = _usuario_acesso_colaborador(colaborador, empresa_id)
            if usuario_acesso and usuario_acesso.ativo:
                usuario_acesso.ativo = False
                set_audit_on_update(usuario_acesso, user_id=user_id)
        else:
            colaborador.ativo = True
            set_audit_on_update(colaborador, user_id=user_id)
        db.session.commit()
    return redirect(url_for('auth.lista_colaboradores'))


@auth_bp.post('/colaboradores/<int:id>/resetar-senha')
@login_required
@permission_required('usuario.manage')
def resetar_senha_colaborador(id):
    empresa_id = get_current_empresa_id()
    colaborador = Colaborador.query.filter_by(id=id, empresa_id=empresa_id).first_or_404()
    usuario_acesso = _usuario_acesso_colaborador(colaborador, empresa_id)
    if not usuario_acesso:
        flash('Colaborador nao possui usuario vinculado.', 'danger')
        return redirect(url_for('auth.editar_colaborador', id=id))

    nova_senha = _gerar_senha_forte()
    usuario_acesso.set_senha(nova_senha)
    usuario_acesso.troca_senha_obrigatoria = True
    set_audit_on_update(usuario_acesso, user_id=get_current_user_id())
    db.session.commit()
    flash(f'Senha temporaria gerada: {nova_senha}', 'warning')
    return redirect(url_for('auth.editar_colaborador', id=id))
