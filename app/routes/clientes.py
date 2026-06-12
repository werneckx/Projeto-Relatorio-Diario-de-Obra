from app.routes.auth_common import *


# --- CLIENTES ---
@auth_bp.get("/lista-clientes")
@login_required
def lista_clientes():
    empresa_id = get_current_empresa_id()
    clientes = (
        Cliente.query
        .filter(Cliente.empresa_id == empresa_id)
        .order_by(Cliente.ativo.desc(), Cliente.id.asc())
        .all()
    )
    return render_template("cadastros/clientes/list_clientes.html", opcoes=clientes, categoria="cliente")


@auth_bp.get('/criar-cliente')
@login_required
@role_required(PERM_WRITE_BASIC)
def criar_cliente():
    return render_template('cadastros/clientes/form_cliente.html', item=None, view_mode=False)


@auth_bp.get('/editar-cliente/<int:id>')
@login_required
@role_required(PERM_WRITE_BASIC)
def editar_cliente(id):
    empresa_id = get_current_empresa_id()
    item = hydrate_audit_metadata(Cliente.query.filter_by(id=id, empresa_id=empresa_id).first_or_404())
    return render_template('cadastros/clientes/form_cliente.html', item=item, view_mode=False)


@auth_bp.get('/visualizar-cliente/<int:id>')
@login_required
def visualizar_cliente(id):
    empresa_id = get_current_empresa_id()
    item = hydrate_audit_metadata(Cliente.query.filter_by(id=id, empresa_id=empresa_id).first_or_404())
    return render_template('cadastros/clientes/form_cliente.html', item=item, view_mode=True)


@auth_bp.post('/gerar-cliente')
@login_required
@role_required(PERM_WRITE_BASIC)
def gerar_cliente():
    empresa_id = get_current_empresa_id()
    user_id = get_current_user_id()

    cliente_id = request.form.get('id')
    razao_social = _normalize_option_input(request.form.get('razao_social', ''))
    nome_fantasia = _normalize_option_input(request.form.get('nome_fantasia', ''))
    cnpj = _normalize_option_input(request.form.get('cnpj', ''))
    contato_nome = _normalize_option_input(request.form.get('contato_nome', ''))
    contato_email = _normalize_option_input(request.form.get('contato_email', ''))
    contato_telefone = _normalize_option_input(request.form.get('contato_telefone', ''))
    ativo = request.form.get('ativo') == '1'

    if not razao_social:
        flash('Razão social é obrigatória.', 'danger')
        return redirect(url_for('auth.criar_cliente'))

    if not cnpj:
        flash('CNPJ é obrigatório.', 'danger')
        return redirect(url_for('auth.criar_cliente'))

    if cliente_id:
        cliente = Cliente.query.filter_by(id=cliente_id, empresa_id=empresa_id).first_or_404()
        cliente.razao_social = razao_social
        cliente.nome_fantasia = nome_fantasia or None
        cliente.cnpj = cnpj
        cliente.contato_nome = contato_nome or None
        cliente.contato_email = contato_email or None
        cliente.contato_telefone = contato_telefone or None
        cliente.ativo = ativo
        set_audit_on_update(cliente, user_id=user_id)
    else:
        novo = Cliente(
            empresa_id=empresa_id,
            razao_social=razao_social,
            nome_fantasia=nome_fantasia or None,
            cnpj=cnpj,
            contato_nome=contato_nome or None,
            contato_email=contato_email or None,
            contato_telefone=contato_telefone or None,
            ativo=ativo,
        )
        set_audit_on_create(novo, user_id=user_id)
        db.session.add(novo)

    db.session.commit()
    return redirect(url_for('auth.lista_clientes'))


@auth_bp.post('/excluir-cliente/<int:id>')
@login_required
@role_required(PERM_MANAGEMENT)
def excluir_cliente(id):
    empresa_id = get_current_empresa_id()
    cliente = Cliente.query.filter_by(id=id, empresa_id=empresa_id).first()
    if cliente:
        set_audit_on_inactivate(cliente)
        db.session.commit()
    return redirect(url_for('auth.lista_clientes'))
