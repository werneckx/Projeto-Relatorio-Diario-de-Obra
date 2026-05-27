from app.routes.auth_common import *


@auth_bp.get("/lista-fornecedores")
@login_required
def lista_fornecedores():
    empresa_id = get_current_empresa_id()
    fornecedores = Fornecedor.query.filter_by(empresa_id=empresa_id, ativo=True).order_by(Fornecedor.nome.asc()).all()
    return render_template("list_fornecedores.html", opcoes=fornecedores, categoria="fornecedor")


@auth_bp.get('/criar-fornecedor')
@login_required
@role_required(PERM_WRITE_BASIC)
def criar_fornecedor():
    return render_template('form_fornecedor.html', item=None, view_mode=False)


@auth_bp.get('/visualizar-fornecedor/<int:id>')
@login_required
def visualizar_fornecedor(id):
    empresa_id = get_current_empresa_id()
    fornecedor = Fornecedor.query.filter_by(id=id, empresa_id=empresa_id).first_or_404()
    return render_template('form_fornecedor.html', item=fornecedor, view_mode=True)


@auth_bp.get('/editar-fornecedor/<int:id>')
@login_required
@role_required(PERM_WRITE_BASIC)
def editar_fornecedor(id):
    empresa_id = get_current_empresa_id()
    fornecedor = Fornecedor.query.filter_by(id=id, empresa_id=empresa_id).first_or_404()
    return render_template('form_fornecedor.html', item=fornecedor, view_mode=False)


@auth_bp.post('/gerar-fornecedor')
@login_required
@role_required(PERM_WRITE_BASIC)
def gerar_fornecedor():
    empresa_id = get_current_empresa_id()
    user_id = session.get('user_id')

    fornecedor_id = request.form.get('id')
    nome = (request.form.get('nome') or '').strip()
    cnpj = (request.form.get('cnpj') or '').strip() or None
    endereco = (request.form.get('endereco') or '').strip() or None
    ativo = request.form.get('ativo') == '1'

    if not nome:
        flash('Nome do fornecedor obrigatorio.', 'danger')
        return redirect(url_for('auth.lista_fornecedores'))

    if fornecedor_id:
        fornecedor = Fornecedor.query.filter_by(id=fornecedor_id, empresa_id=empresa_id).first_or_404()
        fornecedor.nome = nome
        fornecedor.cnpj = cnpj
        fornecedor.endereco = endereco
        fornecedor.ativo = ativo
        fornecedor.modificado_por = user_id
    else:
        fornecedor = Fornecedor(
            empresa_id=empresa_id,
            nome=nome,
            cnpj=cnpj,
            endereco=endereco,
            ativo=ativo,
            criado_por=user_id,
            modificado_por=user_id,
        )
        db.session.add(fornecedor)

    db.session.commit()
    return redirect(url_for('auth.lista_fornecedores'))


@auth_bp.post('/excluir-fornecedor/<int:id>')
@login_required
@role_required(PERM_MANAGEMENT)
def excluir_fornecedor(id):
    empresa_id = get_current_empresa_id()
    user_id = session.get('user_id')

    fornecedor = Fornecedor.query.filter_by(id=id, empresa_id=empresa_id).first_or_404()
    fornecedor.ativo = False
    fornecedor.modificado_por = user_id
    db.session.commit()
    return redirect(url_for('auth.lista_fornecedores'))
