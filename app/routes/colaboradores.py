from app.routes.auth_common import *

from app.models.cliente import Cliente


# --- COLABORADORES ---
@auth_bp.get("/lista-colaboradores")
@login_required
def lista_colaboradores():
    empresa_id = get_current_empresa_id()
    colaboradores = (
        Colaborador.query
        .filter(Colaborador.empresa_id == empresa_id, Colaborador.ativo.is_(True))
        .order_by(Colaborador.nome.asc())
        .all()
    )
    return render_template("list_colaboradores.html", opcoes=colaboradores, categoria="colaborador")


@auth_bp.get('/criar-colaborador')
@login_required
@role_required(PERM_WRITE_BASIC)
def criar_colaborador():
    empresa_id = get_current_empresa_id()
    fornecedores = Fornecedor.query.filter_by(empresa_id=empresa_id, ativo=True).order_by(Fornecedor.nome.asc()).all()
    clientes = Cliente.query.filter_by(empresa_id=empresa_id, ativo=True).order_by(Cliente.razao_social.asc()).all()
    return render_template('form_colaborador.html', item=None, view_mode=False, fornecedores=fornecedores, clientes=clientes)


@auth_bp.get('/editar-colaborador/<int:id>')
@login_required
@role_required(PERM_WRITE_BASIC)
def editar_colaborador(id):
    empresa_id = get_current_empresa_id()
    item = Colaborador.query.filter_by(id=id, empresa_id=empresa_id).first_or_404()
    fornecedores = Fornecedor.query.filter_by(empresa_id=empresa_id, ativo=True).order_by(Fornecedor.nome.asc()).all()
    clientes = Cliente.query.filter_by(empresa_id=empresa_id, ativo=True).order_by(Cliente.razao_social.asc()).all()
    return render_template('form_colaborador.html', item=item, view_mode=False, fornecedores=fornecedores, clientes=clientes)


@auth_bp.get('/visualizar-colaborador/<int:id>')
@login_required
def visualizar_colaborador(id):
    empresa_id = get_current_empresa_id()
    item = Colaborador.query.filter_by(id=id, empresa_id=empresa_id).first_or_404()
    fornecedores = Fornecedor.query.filter_by(empresa_id=empresa_id, ativo=True).order_by(Fornecedor.nome.asc()).all()
    clientes = Cliente.query.filter_by(empresa_id=empresa_id, ativo=True).order_by(Cliente.razao_social.asc()).all()
    return render_template('form_colaborador.html', item=item, view_mode=True, fornecedores=fornecedores, clientes=clientes)


@auth_bp.post('/gerar-colaborador')
@login_required
@role_required(PERM_WRITE_BASIC)
def gerar_colaborador():
    empresa_id = get_current_empresa_id()

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
        colaborador.tipo = tipo
        colaborador.fornecedor_id = fornecedor_id
        colaborador.cliente_id = cliente_id
        colaborador.ativo = ativo
    else:
        novo = Colaborador(
            empresa_id=empresa_id,
            nome=nome,
            cadastro_pessoa_fisica=cadastro_pessoa_fisica or None,
            tipo=tipo,
            fornecedor_id=fornecedor_id,
            cliente_id=cliente_id,
            ativo=ativo,
        )
        db.session.add(novo)

    db.session.commit()
    return redirect(url_for('auth.lista_colaboradores'))


@auth_bp.post('/excluir-colaborador/<int:id>')
@login_required
@role_required(PERM_MANAGEMENT)
def excluir_colaborador(id):
    empresa_id = get_current_empresa_id()
    colaborador = Colaborador.query.filter_by(id=id, empresa_id=empresa_id).first()
    if colaborador:
        colaborador.ativo = False
        db.session.commit()
    return redirect(url_for('auth.lista_colaboradores'))

