from app.routes.auth_common import *


# --- FORNECEDORES ---
@auth_bp.get("/lista-fornecedores")
@login_required
def lista_fornecedores():
    empresa_id = get_current_empresa_id()
    fornecedores = (
        Fornecedor.query
        .filter(Fornecedor.empresa_id == empresa_id, Fornecedor.ativo.is_(True))
        .order_by(Fornecedor.id.asc())
        .all()
    )
    return render_template("list_fornecedores.html", opcoes=fornecedores, categoria="fornecedor")


@auth_bp.get('/criar-fornecedor')
@login_required
@role_required(PERM_WRITE_BASIC)
def criar_fornecedor():
    return render_template('form_fornecedor.html', item=None, view_mode=False)


@auth_bp.get('/editar-fornecedor/<int:id>')
@login_required
@role_required(PERM_WRITE_BASIC)
def editar_fornecedor(id):
    empresa_id = get_current_empresa_id()
    item = Fornecedor.query.filter_by(id=id, empresa_id=empresa_id).first_or_404()
    return render_template('form_fornecedor.html', item=item, view_mode=False)


@auth_bp.get('/visualizar-fornecedor/<int:id>')
@login_required
def visualizar_fornecedor(id):
    empresa_id = get_current_empresa_id()
    item = Fornecedor.query.filter_by(id=id, empresa_id=empresa_id).first_or_404()
    return render_template('form_fornecedor.html', item=item, view_mode=True)


@auth_bp.post('/gerar-fornecedor')
@login_required
@role_required(PERM_WRITE_BASIC)
def gerar_fornecedor():
    empresa_id = get_current_empresa_id()

    fornecedor_id = request.form.get('id')
    nome = _normalize_option_input(request.form.get('nome', ''))
    cnpj = _normalize_option_input(request.form.get('cnpj', ''))
    endereco = _normalize_option_input(request.form.get('endereco', ''))
    ativo = request.form.get('ativo') == '1'

    if not nome:
        flash('Nome do fornecedor é obrigatório.', 'danger')
        return redirect(url_for('auth.criar_fornecedor'))

    if fornecedor_id:
        fornecedor = Fornecedor.query.filter_by(id=fornecedor_id, empresa_id=empresa_id).first_or_404()
        fornecedor.nome = nome
        fornecedor.cnpj = cnpj or None
        fornecedor.endereco = endereco or None
        fornecedor.ativo = ativo
    else:
        novo = Fornecedor(
            empresa_id=empresa_id,
            nome=nome,
            cnpj=cnpj or None,
            endereco=endereco or None,
            ativo=ativo,
        )
        db.session.add(novo)

    db.session.commit()
    return redirect(url_for('auth.lista_fornecedores'))


@auth_bp.post('/excluir-fornecedor/<int:id>')
@login_required
@role_required(PERM_MANAGEMENT)
def excluir_fornecedor(id):
    empresa_id = get_current_empresa_id()
    fornecedor = Fornecedor.query.filter_by(id=id, empresa_id=empresa_id).first()
    if fornecedor:
        fornecedor.ativo = False
        db.session.commit()
    return redirect(url_for('auth.lista_fornecedores'))

