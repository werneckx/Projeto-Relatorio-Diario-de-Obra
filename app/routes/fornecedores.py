from app.routes.auth_common import *


# --- FORNECEDORES ---
@auth_bp.get("/lista-fornecedores")
@login_required
def lista_fornecedores():
    empresa_id = get_current_empresa_id()
    fornecedores = (
        Fornecedor.query
        .filter(Fornecedor.empresa_id == empresa_id)
        .order_by(Fornecedor.ativo.desc(), Fornecedor.id.asc())
        .all()
    )
    return render_template("cadastros/fornecedores/list_fornecedores.html", opcoes=fornecedores, categoria="fornecedor")


@auth_bp.get('/criar-fornecedor')
@login_required
@role_required(PERM_WRITE_BASIC)
def criar_fornecedor():
    return render_template('cadastros/fornecedores/form_fornecedor.html', item=None, view_mode=False)


@auth_bp.get('/editar-fornecedor/<int:id>')
@login_required
@role_required(PERM_WRITE_BASIC)
def editar_fornecedor(id):
    empresa_id = get_current_empresa_id()
    item = hydrate_audit_metadata(Fornecedor.query.filter_by(id=id, empresa_id=empresa_id).first_or_404())
    return render_template('cadastros/fornecedores/form_fornecedor.html', item=item, view_mode=False)


@auth_bp.get('/visualizar-fornecedor/<int:id>')
@login_required
def visualizar_fornecedor(id):
    empresa_id = get_current_empresa_id()
    item = hydrate_audit_metadata(Fornecedor.query.filter_by(id=id, empresa_id=empresa_id).first_or_404())
    return render_template('cadastros/fornecedores/form_fornecedor.html', item=item, view_mode=True)


@auth_bp.post('/gerar-fornecedor')
@login_required
@role_required(PERM_WRITE_BASIC)
def gerar_fornecedor():
    empresa_id = get_current_empresa_id()
    user_id = get_current_user_id()

    fornecedor_id = request.form.get('id')
    nome = _normalize_option_input(request.form.get('nome', ''))
    cnpj = ''.join(ch for ch in request.form.get('cnpj', '') if ch.isdigit())
    cep = ''.join(ch for ch in request.form.get('cep', '') if ch.isdigit())
    logradouro = _normalize_option_input(request.form.get('logradouro', ''))
    numero = _normalize_option_input(request.form.get('numero', ''))
    complemento = _normalize_option_input(request.form.get('complemento', ''))
    bairro = _normalize_option_input(request.form.get('bairro', ''))
    cidade = _normalize_option_input(request.form.get('cidade', ''))
    estado = _normalize_option_input(request.form.get('estado', '')).upper()
    ativo = request.form.get('ativo') == '1'

    if not nome:
        flash('Nome do fornecedor é obrigatório.', 'danger')
        if fornecedor_id:
            return redirect(url_for('auth.editar_fornecedor', id=fornecedor_id))
        return redirect(url_for('auth.criar_fornecedor'))

    if fornecedor_id:
        fornecedor = Fornecedor.query.filter_by(id=fornecedor_id, empresa_id=empresa_id).first_or_404()
        fornecedor.nome = nome
        fornecedor.cnpj = cnpj or None
        fornecedor.cep = cep or None
        fornecedor.logradouro = logradouro or None
        fornecedor.numero = numero or None
        fornecedor.complemento = complemento or None
        fornecedor.bairro = bairro or None
        fornecedor.cidade = cidade or None
        fornecedor.estado = estado or None
        fornecedor.ativo = ativo
        set_audit_on_update(fornecedor, user_id=user_id)
    else:
        novo = Fornecedor(
            empresa_id=empresa_id,
            nome=nome,
            cnpj=cnpj or None,
            cep=cep or None,
            logradouro=logradouro or None,
            numero=numero or None,
            complemento=complemento or None,
            bairro=bairro or None,
            cidade=cidade or None,
            estado=estado or None,
            ativo=ativo,
        )
        set_audit_on_create(novo, user_id=user_id)
        db.session.add(novo)

    db.session.commit()
    return redirect(url_for('auth.lista_fornecedores'))


@auth_bp.post('/excluir-fornecedor/<int:id>')
@auth_bp.post('/toggle-fornecedor/<int:id>')
@login_required
@permission_required('fornecedor.manage')
def excluir_fornecedor(id):
    empresa_id = get_current_empresa_id()
    user_id = get_current_user_id()
    fornecedor = Fornecedor.query.filter_by(id=id, empresa_id=empresa_id).first()
    if fornecedor:
        if fornecedor.ativo:
            set_audit_on_inactivate(fornecedor, user_id=user_id)
        else:
            fornecedor.ativo = True
            set_audit_on_update(fornecedor, user_id=user_id)
        db.session.commit()
    return redirect(url_for('auth.lista_fornecedores'))
