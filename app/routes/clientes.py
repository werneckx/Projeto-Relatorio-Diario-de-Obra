from app.routes.auth_common import *
from app.models.cliente import Cliente


@auth_bp.get("/lista-clientes")
@login_required
def lista_clientes():
    empresa_id = get_current_empresa_id()
    clientes = Cliente.query.filter_by(empresa_id=empresa_id, ativo=True).order_by(Cliente.razao_social.asc()).all()
    return render_template("list_clientes.html", opcoes=clientes, categoria="cliente")


@auth_bp.get("/criar-cliente")
@login_required
@role_required(PERM_WRITE_BASIC)
def criar_cliente():
    return render_template("form_cliente.html", item=None, view_mode=False)


@auth_bp.get("/visualizar-cliente/<int:id>")
@login_required
def visualizar_cliente(id):
    empresa_id = get_current_empresa_id()
    cliente = Cliente.query.filter_by(id=id, empresa_id=empresa_id).first_or_404()
    return render_template("form_cliente.html", item=cliente, view_mode=True)


@auth_bp.get("/editar-cliente/<int:id>")
@login_required
@role_required(PERM_WRITE_BASIC)
def editar_cliente(id):
    empresa_id = get_current_empresa_id()
    cliente = Cliente.query.filter_by(id=id, empresa_id=empresa_id).first_or_404()
    return render_template("form_cliente.html", item=cliente, view_mode=False)


@auth_bp.post("/gerar-cliente")
@login_required
@role_required(PERM_WRITE_BASIC)
def gerar_cliente():
    empresa_id = get_current_empresa_id()
    user_id = session.get("user_id")

    cliente_id = request.form.get("id")
    razao_social = (request.form.get("razao_social") or "").strip()
    nome_fantasia = (request.form.get("nome_fantasia") or "").strip() or None
    cnpj = (request.form.get("cnpj") or "").strip()
    contato_nome = (request.form.get("contato_nome") or "").strip() or None
    contato_email = (request.form.get("contato_email") or "").strip() or None
    contato_telefone = (request.form.get("contato_telefone") or "").strip() or None
    ativo = request.form.get("ativo") == "1"

    if not razao_social:
        flash("Razao social obrigatoria.", "danger")
        return redirect(url_for("auth.lista_clientes"))
    if not cnpj:
        flash("CNPJ obrigatorio.", "danger")
        return redirect(url_for("auth.lista_clientes"))

    if cliente_id:
        cliente = Cliente.query.filter_by(id=cliente_id, empresa_id=empresa_id).first_or_404()
        cliente.razao_social = razao_social
        cliente.nome_fantasia = nome_fantasia
        cliente.cnpj = cnpj
        cliente.contato_nome = contato_nome
        cliente.contato_email = contato_email
        cliente.contato_telefone = contato_telefone
        cliente.ativo = ativo
        cliente.modificado_por = user_id
    else:
        cliente = Cliente(
            empresa_id=empresa_id,
            razao_social=razao_social,
            nome_fantasia=nome_fantasia,
            cnpj=cnpj,
            contato_nome=contato_nome,
            contato_email=contato_email,
            contato_telefone=contato_telefone,
            ativo=ativo,
            criado_por=user_id,
            modificado_por=user_id,
        )
        db.session.add(cliente)

    db.session.commit()
    return redirect(url_for("auth.lista_clientes"))


@auth_bp.post("/excluir-cliente/<int:id>")
@login_required
@role_required(PERM_MANAGEMENT)
def excluir_cliente(id):
    empresa_id = get_current_empresa_id()
    user_id = session.get("user_id")

    cliente = Cliente.query.filter_by(id=id, empresa_id=empresa_id).first_or_404()
    cliente.ativo = False
    cliente.modificado_por = user_id
    db.session.commit()
    return redirect(url_for("auth.lista_clientes"))
