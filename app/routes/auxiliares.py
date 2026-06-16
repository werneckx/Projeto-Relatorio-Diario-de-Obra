from app.routes.auth_common import *


def _is_system_option(record):
    return bool(record and getattr(record, "is_system", False))


def _redirect_system_option(view_endpoint, record_id):
    flash("Registros do sistema são protegidos e não podem ser alterados.", "warning")
    return redirect(url_for(view_endpoint, id=record_id))


def _current_option_empresa_id():
    return session.get("empresa_id") or get_current_empresa_id()


def _find_duplicate_tipo_equipamento(nome, exclude_id=None):
    nome_norm = _normalize_option_text(nome)
    query = TipoEquipamento.query
    if exclude_id:
        query = query.filter(TipoEquipamento.id != exclude_id)
    for tipo in query.all():
        if _normalize_option_text(tipo.nome) == nome_norm:
            return tipo
    return None


def _current_user_has_permission(chave):
    user = get_current_user()
    if user and getattr(user, "is_admin", False):
        return True
    return chave in (session.get("permissions", []) or [])

@auth_bp.get("/lista-climas")
@login_required
def lista_climas():
    climas = AuxClima.query.order_by(AuxClima.ativo.desc(), AuxClima.nome.asc()).all()
    return render_template("auxiliares/list_climas.html", opcoes=climas, categoria="clima")

@auth_bp.get('/criar-clima')
@login_required
@role_required(PERM_WRITE_BASIC)
def criar_clima():
    return render_template('auxiliares/form_clima.html', item=None, view_mode=False)

@auth_bp.post('/gerar-clima')
@login_required
@role_required(PERM_WRITE_BASIC)
def gerar_clima():
    clima_id = request.form.get('id')
    user_id = get_current_user_id()
    tipo_lista = "Climas"
    nome = _normalize_option_input(request.form.get('nome', ''))
    ativo = request.form.get('ativo') == '1'
    if not nome:
        flash('Nome do clima é obrigatório.', 'danger')
        if clima_id: return redirect(url_for('auth.editar_clima', id=clima_id))
        return redirect(url_for('auth.criar_clima'))

    clima_existente = _find_duplicate_option(AuxClima, nome, tipo_lista, exclude_id=clima_id)

    if clima_existente:
        flash('Já existe um clima cadastrado com esse nome.', 'danger')
        if clima_id: return redirect(url_for('auth.editar_clima', id=clima_id))
        return redirect(url_for('auth.criar_clima'))

    if clima_id:
        clima = AuxClima.query.get(clima_id)
        if not clima: return redirect(url_for('auth.lista_climas'))
        if _is_system_option(clima):
            return _redirect_system_option('auth.visualizar_clima', clima.id)
        clima.nome = nome
        clima.ativo = ativo
        set_audit_on_update(clima, user_id=user_id)
        db.session.add(clima)
        db.session.commit()
        return redirect(url_for('auth.lista_climas'))

    novo = AuxClima(nome=nome, tipo_lista=tipo_lista, ativo=ativo, empresa_id=_current_option_empresa_id())
    set_audit_on_create(novo, user_id=user_id)
    db.session.add(novo)
    db.session.commit()
    return redirect(url_for('auth.lista_climas'))

@auth_bp.get('/visualizar-clima/<int:id>')
@login_required
def visualizar_clima(id):
    clima = hydrate_audit_metadata(AuxClima.query.get_or_404(id))
    return render_template('auxiliares/form_clima.html', item=clima, view_mode=True)

@auth_bp.get('/editar-clima/<int:id>')
@login_required
@role_required(PERM_WRITE_BASIC)
def editar_clima(id):
    clima = hydrate_audit_metadata(AuxClima.query.get_or_404(id))
    if _is_system_option(clima):
        return _redirect_system_option('auth.visualizar_clima', clima.id)
    return render_template('auxiliares/form_clima.html', item=clima, view_mode=False)

@auth_bp.post('/excluir-clima/<int:id>')
@auth_bp.post('/toggle-clima/<int:id>')
@login_required
@role_required(PERM_MANAGEMENT)
def excluir_clima(id):
    user_id = get_current_user_id()
    clima = AuxClima.query.get(id)
    if clima:
        if _is_system_option(clima):
            flash("Registros do sistema não podem ser ativados ou inativados.", "warning")
            return redirect(url_for('auth.lista_climas'))
        if clima.ativo:
            set_audit_on_inactivate(clima, user_id=user_id)
        else:
            clima.ativo = True
            set_audit_on_update(clima, user_id=user_id)
        db.session.add(clima)
        db.session.commit()
    return redirect(url_for('auth.lista_climas'))


# --- EQUIPAMENTOS ---
@auth_bp.get("/lista-equipamentos")
@login_required
def lista_equipamentos():
    equipamentos = (
        AuxEquipamentos.query
        .options(joinedload(AuxEquipamentos.tipo))
        .order_by(AuxEquipamentos.ativo.desc(), AuxEquipamentos.nome.asc())
        .all()
    )
    return render_template("auxiliares/list_equipamentos.html", opcoes=equipamentos, categoria="equipamento")

@auth_bp.get('/criar-equipamento')
@login_required
@role_required(PERM_WRITE_BASIC)
def criar_equipamento():
    tipos_equipamento = TipoEquipamento.query.filter_by(ativo=True).order_by(TipoEquipamento.nome.asc()).all()
    return render_template('auxiliares/form_equipamento.html', item=None, view_mode=False, tipos_equipamento=tipos_equipamento)

@auth_bp.post('/gerar-equipamento')
@login_required
@role_required(PERM_WRITE_BASIC)
def gerar_equipamento():
    equipamento_id = request.form.get('id')
    user_id = get_current_user_id()
    tipo_lista = "Equipamentos"
    nome = _normalize_option_input(request.form.get('nome', ''))
    tipo_id = request.form.get('tipo_id')
    ativo = request.form.get('ativo') == '1'
    if not nome:
        flash('Nome do equipamento é obrigatório.', 'danger')
        return redirect(url_for('auth.lista_equipamentos'))
    if not tipo_id:
        flash('Tipo de equipamento é obrigatório.', 'danger')
        if equipamento_id: return redirect(url_for('auth.editar_equipamento', id=equipamento_id))
        return redirect(url_for('auth.criar_equipamento'))

    equipamento = None
    if equipamento_id:
        equipamento = AuxEquipamentos.query.get(equipamento_id)
        if not equipamento:
            return redirect(url_for('auth.lista_equipamentos'))
        if _is_system_option(equipamento):
            return _redirect_system_option('auth.visualizar_equipamento', equipamento.id)

    tipo_query = TipoEquipamento.query.filter(TipoEquipamento.id == tipo_id)
    if equipamento:
        tipo_query = tipo_query.filter(
            db.or_(TipoEquipamento.ativo.is_(True), TipoEquipamento.id == equipamento.tipo_id)
        )
    else:
        tipo_query = tipo_query.filter(TipoEquipamento.ativo.is_(True))

    aux_tipo_equipamento = tipo_query.first()
    if not aux_tipo_equipamento:
        flash('Tipo de equipamento inválido ou inativo.', 'danger')
        if equipamento_id: return redirect(url_for('auth.editar_equipamento', id=equipamento_id))
        return redirect(url_for('auth.criar_equipamento'))

    equipamento_existente = _find_duplicate_option(AuxEquipamentos, nome, tipo_lista, exclude_id=equipamento_id)

    if equipamento_existente:
        flash('Já existe um equipamento cadastrado com esse nome.', 'danger')
        if equipamento_id: return redirect(url_for('auth.editar_equipamento', id=equipamento_id))
        return redirect(url_for('auth.criar_equipamento'))

    if equipamento_id:
        equipamento.nome = nome
        equipamento.tipo_id = aux_tipo_equipamento.id
        equipamento.ativo = ativo
        set_audit_on_update(equipamento, user_id=user_id)
        db.session.add(equipamento)
    else:
        novo = AuxEquipamentos(nome=nome, tipo_lista=tipo_lista, tipo_id=aux_tipo_equipamento.id, ativo=ativo, empresa_id=_current_option_empresa_id())
        set_audit_on_create(novo, user_id=user_id)
        db.session.add(novo)
    db.session.commit()
    return redirect(url_for('auth.lista_equipamentos'))

@auth_bp.get('/visualizar-equipamento/<int:id>')
@login_required
def visualizar_equipamento(id):
    equipamento = hydrate_audit_metadata(
        AuxEquipamentos.query.options(joinedload(AuxEquipamentos.tipo)).filter_by(id=id).first_or_404()
    )
    tipos_equipamento = TipoEquipamento.query.filter_by(ativo=True).order_by(TipoEquipamento.nome.asc()).all()
    return render_template('auxiliares/form_equipamento.html', item=equipamento, view_mode=True, tipos_equipamento=tipos_equipamento)

@auth_bp.get('/editar-equipamento/<int:id>')
@login_required
@role_required(PERM_WRITE_BASIC)
def editar_equipamento(id):
    equipamento = hydrate_audit_metadata(
        AuxEquipamentos.query.options(joinedload(AuxEquipamentos.tipo)).filter_by(id=id).first_or_404()
    )
    if _is_system_option(equipamento):
        return _redirect_system_option('auth.visualizar_equipamento', equipamento.id)
    tipos_equipamento = (
        TipoEquipamento.query
        .filter(db.or_(TipoEquipamento.ativo.is_(True), TipoEquipamento.id == equipamento.tipo_id))
        .order_by(TipoEquipamento.nome.asc())
        .all()
    )
    return render_template('auxiliares/form_equipamento.html', item=equipamento, view_mode=False, tipos_equipamento=tipos_equipamento)

@auth_bp.post('/excluir-equipamento/<int:id>')
@auth_bp.post('/toggle-equipamento/<int:id>')
@login_required
@role_required(PERM_MANAGEMENT)
def excluir_equipamento(id):
    user_id = get_current_user_id()
    equipamento = AuxEquipamentos.query.get(id)
    if equipamento:
        if _is_system_option(equipamento):
            flash("Registros do sistema não podem ser ativados ou inativados.", "warning")
            return redirect(url_for('auth.lista_equipamentos'))
        if equipamento.ativo:
            set_audit_on_inactivate(equipamento, user_id=user_id)
        else:
            equipamento.ativo = True
            set_audit_on_update(equipamento, user_id=user_id)
        db.session.add(equipamento)
        db.session.commit()
    return redirect(url_for('auth.lista_equipamentos'))


# --- TIPOS DE EQUIPAMENTO ---
@auth_bp.get("/tipos-equipamento")
@login_required
@permission_required('aux_tipo_equipamento.view')
def lista_tipos_equipamento():
    tipos = TipoEquipamento.query.order_by(TipoEquipamento.ativo.desc(), TipoEquipamento.nome.asc()).all()
    return render_template("cadastros/tipos_equipamento/list_tipos_equipamento.html", opcoes=tipos)


@auth_bp.get("/tipos-equipamento/novo")
@login_required
@permission_required('aux_tipo_equipamento.create')
def criar_tipo_equipamento():
    return render_template("cadastros/tipos_equipamento/form_tipo_equipamento.html", item=None, view_mode=False)


@auth_bp.post("/tipos-equipamento/salvar")
@login_required
def gerar_tipo_equipamento():
    tipo_id = request.form.get("id")
    user_id = get_current_user_id()
    nome = _normalize_option_input(request.form.get("nome", ""))
    ativo = request.form.get("ativo") == "1"

    if tipo_id:
        tipo = TipoEquipamento.query.get_or_404(tipo_id)
        if _is_system_option(tipo):
            return _redirect_system_option('auth.visualizar_tipo_equipamento', tipo.id)
        required_permission = 'aux_tipo_equipamento.edit'
    else:
        tipo = None
        required_permission = 'aux_tipo_equipamento.create'

    # Revalida a permissão específica para criação/edição sem duplicar a rota.
    if not _current_user_has_permission(required_permission):
        flash("Você não tem permissão para executar esta ação.", "danger")
        return redirect(url_for("auth.lista_tipos_equipamento"))

    if not nome:
        flash("Nome do tipo de equipamento é obrigatório.", "danger")
        if tipo_id:
            return redirect(url_for("auth.editar_tipo_equipamento", id=tipo_id))
        return redirect(url_for("auth.criar_tipo_equipamento"))

    if _find_duplicate_tipo_equipamento(nome, exclude_id=tipo_id):
        flash("Já existe um tipo de equipamento cadastrado com esse nome.", "danger")
        if tipo_id:
            return redirect(url_for("auth.editar_tipo_equipamento", id=tipo_id))
        return redirect(url_for("auth.criar_tipo_equipamento"))

    if tipo:
        tipo.nome = nome
        tipo.ativo = ativo
        set_audit_on_update(tipo, user_id=user_id)
        db.session.add(tipo)
        flash("Tipo de equipamento atualizado com sucesso.", "success")
    else:
        tipo = TipoEquipamento(nome=nome, ativo=ativo)
        set_audit_on_create(tipo, user_id=user_id)
        db.session.add(tipo)
        flash("Tipo de equipamento cadastrado com sucesso.", "success")

    db.session.commit()
    return redirect(url_for("auth.lista_tipos_equipamento"))


@auth_bp.get("/tipos-equipamento/<int:id>")
@login_required
@permission_required('aux_tipo_equipamento.view')
def visualizar_tipo_equipamento(id):
    tipo = hydrate_audit_metadata(TipoEquipamento.query.get_or_404(id))
    return render_template("cadastros/tipos_equipamento/view_tipo_equipamento.html", item=tipo, view_mode=True)


@auth_bp.get("/tipos-equipamento/<int:id>/editar")
@login_required
@permission_required('aux_tipo_equipamento.edit')
def editar_tipo_equipamento(id):
    tipo = hydrate_audit_metadata(TipoEquipamento.query.get_or_404(id))
    if _is_system_option(tipo):
        return _redirect_system_option('auth.visualizar_tipo_equipamento', tipo.id)
    return render_template("cadastros/tipos_equipamento/form_tipo_equipamento.html", item=tipo, view_mode=False)


@auth_bp.post("/tipos-equipamento/<int:id>/toggle-status")
@login_required
@permission_required('aux_tipo_equipamento.manage')
def toggle_tipo_equipamento_status(id):
    tipo = TipoEquipamento.query.get_or_404(id)
    if _is_system_option(tipo):
        flash("Registros de sistema não podem ser alterados.", "warning")
        return redirect(url_for("auth.lista_tipos_equipamento"))
    if tipo.ativo:
        equipamentos_ativos = AuxEquipamentos.query.filter_by(tipo_id=tipo.id, ativo=True).count()
        if equipamentos_ativos:
            flash("Não é possível inativar um tipo vinculado a equipamentos ativos.", "warning")
            return redirect(url_for("auth.lista_tipos_equipamento"))
    tipo.ativo = not bool(tipo.ativo)
    set_audit_on_update(tipo)
    db.session.add(tipo)
    db.session.commit()
    return redirect(url_for("auth.lista_tipos_equipamento"))


# --- TAGS ---
@auth_bp.get("/lista-tags-ocorrencias")
@login_required
def lista_tags_ocorrencias():
    tagsOcorrencias = AuxTagOcorrencia.query.order_by(AuxTagOcorrencia.ativo.desc(), AuxTagOcorrencia.nome.asc()).all()
    return render_template("auxiliares/list_tags_ocorrencias.html", opcoes=tagsOcorrencias, categoria="tagsOcorrencias")

@auth_bp.get('/criar-tags-ocorrencias')
@login_required
@role_required(PERM_WRITE_BASIC)
def criar_tags_ocorrencias():
    return render_template('auxiliares/form_tags_ocorrencias.html', item=None, view_mode=False)

@auth_bp.post('/gerar-tags-ocorrencias')
@login_required
@role_required(PERM_WRITE_BASIC)
def gerar_tags_ocorrencias():
    tag_id = request.form.get('id')
    user_id = get_current_user_id()
    nome = _normalize_option_input(request.form.get('nome', ''))
    ativo = request.form.get('ativo') == '1'
    if not nome:
        flash('Nome da tag é obrigatório.', 'danger')
        return redirect(url_for('auth.lista_tags_ocorrencias'))

    tag_existente = _find_duplicate_option(AuxTagOcorrencia, nome, "Tags Ocorrencias", exclude_id=tag_id)

    if tag_existente:
        flash('Já existe uma tag de ocorrência cadastrada com esse nome.', 'danger')
        if tag_id: return redirect(url_for('auth.editar_tags_ocorrencias', id=tag_id))
        return redirect(url_for('auth.criar_tags_ocorrencias'))

    if tag_id:
        tag = AuxTagOcorrencia.query.get(tag_id)
        if not tag:
            return redirect(url_for('auth.lista_tags_ocorrencias'))
        if _is_system_option(tag):
            return _redirect_system_option('auth.visualizar_tags_ocorrencias', tag.id)
        tag.nome = nome
        tag.ativo = ativo
        set_audit_on_update(tag, user_id=user_id)
        db.session.add(tag)
    else:
        nova_tag = AuxTagOcorrencia(nome=nome, tipo_lista="Tags Ocorrencias", ativo=ativo, empresa_id=_current_option_empresa_id())
        set_audit_on_create(nova_tag, user_id=user_id)
        db.session.add(nova_tag)
    db.session.commit()
    return redirect(url_for('auth.lista_tags_ocorrencias'))

@auth_bp.get('/visualizar-tags-ocorrencias/<int:id>')
@login_required
def visualizar_tags_ocorrencias(id):
    tag = hydrate_audit_metadata(AuxTagOcorrencia.query.get_or_404(id))
    return render_template('auxiliares/form_tags_ocorrencias.html', item=tag, view_mode=True)

@auth_bp.get('/editar-tags-ocorrencias/<int:id>')
@login_required
@role_required(PERM_WRITE_BASIC)
def editar_tags_ocorrencias(id):
    tag = hydrate_audit_metadata(AuxTagOcorrencia.query.get_or_404(id))
    if _is_system_option(tag):
        return _redirect_system_option('auth.visualizar_tags_ocorrencias', tag.id)
    return render_template('auxiliares/form_tags_ocorrencias.html', item=tag, view_mode=False)

@auth_bp.post('/excluir-tags-ocorrencias/<int:id>')
@auth_bp.post('/toggle-tags-ocorrencias/<int:id>')
@login_required
@role_required(PERM_MANAGEMENT)
def excluir_tags_ocorrencias(id):
    user_id = get_current_user_id()
    tag = AuxTagOcorrencia.query.get(id)
    if tag:
        if _is_system_option(tag):
            flash("Registros do sistema não podem ser ativados ou inativados.", "warning")
            return redirect(url_for('auth.lista_tags_ocorrencias'))
        if tag.ativo:
            set_audit_on_inactivate(tag, user_id=user_id)
        else:
            tag.ativo = True
            set_audit_on_update(tag, user_id=user_id)
        db.session.add(tag)
        db.session.commit()
    return redirect(url_for('auth.lista_tags_ocorrencias'))


# --- MAO DE OBRA ---
# O mÃ³dulo "mao_obra" foi renomeado para "funcoes".
# Mantemos rotas antigas como aliases para preservar compatibilidade.

@auth_bp.get("/lista-funcoes")
@login_required
def lista_funcoes():
    funcoes = AuxFuncoes.query.order_by(AuxFuncoes.ativo.desc(), AuxFuncoes.nome.asc()).all()
    return render_template("auxiliares/list_funcoes.html", opcoes=funcoes, categoria="funcoes")

@auth_bp.get("/lista-mao-obra")
@login_required
def lista_mao_obra():
    return redirect(url_for("auth.lista_funcoes"))


@auth_bp.get("/criar-funcao")
@login_required
@role_required(PERM_WRITE_BASIC)
def criar_funcao():
    return render_template("auxiliares/form_funcoes.html", item=None, view_mode=False)

@auth_bp.get("/criar-mao-obra")
@login_required
@role_required(PERM_WRITE_BASIC)
def criar_mao_obra():
    return redirect(url_for("auth.criar_funcao"))


@auth_bp.post("/gerar-funcao")
@login_required
@role_required(PERM_WRITE_BASIC)
def gerar_funcao():
    funcao_id = request.form.get("id")
    user_id = get_current_user_id()
    nome = _normalize_option_input(request.form.get("nome", ""))
    tipo = _normalize_option_input(request.form.get("tipo", "")) or None
    if tipo:
        tipo = tipo.upper()
    tipo = {"DIRETA": "DIRETO", "INDIRETA": "INDIRETO"}.get(tipo, tipo)
    ativo = request.form.get("ativo") == "1"

    if not nome:
        flash("Nome da função é obrigatório.", "danger")
        return redirect(url_for("auth.lista_funcoes"))

    funcao_existente = _find_duplicate_option(AuxFuncoes, nome, "Função", exclude_id=funcao_id, tipo=tipo)
    if funcao_existente:
        flash("Já existe uma função cadastrada com esse nome e tipo.", "danger")
        if funcao_id:
            return redirect(url_for("auth.editar_funcao", id=funcao_id))
        return redirect(url_for("auth.criar_funcao"))

    if funcao_id:
        funcao = AuxFuncoes.query.get(funcao_id)
        if not funcao:
            return redirect(url_for("auth.lista_funcoes"))
        if _is_system_option(funcao):
            return _redirect_system_option('auth.visualizar_funcao', funcao.id)
        funcao.nome = nome
        funcao.tipo = tipo
        funcao.ativo = ativo
        set_audit_on_update(funcao, user_id=user_id)
        db.session.add(funcao)
    else:
        nova_funcao = AuxFuncoes(nome=nome, tipo_lista="Mao de Obra", tipo=tipo, ativo=ativo, empresa_id=_current_option_empresa_id())
        set_audit_on_create(nova_funcao, user_id=user_id)
        db.session.add(nova_funcao)

    db.session.commit()
    return redirect(url_for("auth.lista_funcoes"))

@auth_bp.post("/gerar-mao-obra")
@login_required
@role_required(PERM_WRITE_BASIC)
def gerar_mao_obra():
    return gerar_funcao()


@auth_bp.get("/visualizar-funcao/<int:id>")
@login_required
def visualizar_funcao(id):
    funcao = hydrate_audit_metadata(AuxFuncoes.query.get_or_404(id))
    return render_template("auxiliares/form_funcoes.html", item=funcao, view_mode=True)

@auth_bp.get("/visualizar-mao-obra/<int:id>")
@login_required
def visualizar_mao_obra(id):
    return redirect(url_for("auth.visualizar_funcao", id=id))


@auth_bp.get("/editar-funcao/<int:id>")
@login_required
@role_required(PERM_WRITE_BASIC)
def editar_funcao(id):
    funcao = hydrate_audit_metadata(AuxFuncoes.query.get_or_404(id))
    if _is_system_option(funcao):
        return _redirect_system_option('auth.visualizar_funcao', funcao.id)
    return render_template("auxiliares/form_funcoes.html", item=funcao, view_mode=False)

@auth_bp.get("/editar-mao-obra/<int:id>")
@login_required
@role_required(PERM_WRITE_BASIC)
def editar_mao_obra(id):
    return redirect(url_for("auth.editar_funcao", id=id))


@auth_bp.post("/excluir-funcao/<int:id>")
@auth_bp.post("/toggle-funcao/<int:id>")
@login_required
@role_required(PERM_MANAGEMENT)
def excluir_funcao(id):
    user_id = get_current_user_id()
    funcao = AuxFuncoes.query.get(id)
    if funcao:
        if _is_system_option(funcao):
            flash("Registros do sistema não podem ser ativados ou inativados.", "warning")
            return redirect(url_for("auth.lista_funcoes"))
        if funcao.ativo:
            set_audit_on_inactivate(funcao, user_id=user_id)
        else:
            funcao.ativo = True
            set_audit_on_update(funcao, user_id=user_id)
        db.session.add(funcao)
        db.session.commit()
    return redirect(url_for("auth.lista_funcoes"))

@auth_bp.post("/excluir-mao-obra/<int:id>")
@login_required
@role_required(PERM_MANAGEMENT)
def excluir_mao_obra(id):
    return excluir_funcao(id)

# --- TIPOS DE OBRA ---
@auth_bp.get("/lista-tipos-obra")
@login_required
def lista_tipos_obra():
    tipos = AuxTipoObra.query.order_by(AuxTipoObra.ativo.desc(), AuxTipoObra.nome.asc()).all()
    return render_template("cadastros/obras/list_tipos_obra.html", opcoes=tipos, categoria="tipo_obra")


@auth_bp.get("/criar-tipo-obra")
@login_required
@role_required(PERM_MANAGEMENT)
def criar_tipo_obra():
    return render_template("cadastros/obras/form_tipo_obra.html", item=None, view_mode=False)

@auth_bp.post('/gerar-tipo-obra')
@login_required
@role_required(PERM_WRITE_BASIC)
def gerar_tipo_obra():
    tipo_id = request.form.get('id')
    user_id = get_current_user_id()
    nome = _normalize_option_input(request.form.get('nome', ''))
    ativo = request.form.get('ativo') == '1'
    if not nome:
        flash('Nome do tipo de obra é obrigatório.', 'danger')
        if tipo_id: return redirect(url_for('auth.editar_tipo_obra', id=tipo_id))
        return redirect(url_for('auth.criar_tipo_obra'))

    tipo_existente = _find_duplicate_option(AuxTipoObra, nome, "Tipo de Obra", exclude_id=tipo_id)

    if tipo_existente:
        flash('Já existe um tipo de obra cadastrado com esse nome.', 'danger')
        if tipo_id: return redirect(url_for('auth.editar_tipo_obra', id=tipo_id))
        return redirect(url_for('auth.criar_tipo_obra'))

    if tipo_id:
        tipo = AuxTipoObra.query.get(tipo_id)
        if not tipo: return redirect(url_for('auth.lista_tipos_obra'))
        if _is_system_option(tipo):
            return _redirect_system_option('auth.visualizar_tipo_obra', tipo.id)
        tipo.nome = nome
        tipo.descricao = request.form.get('descricao')
        tipo.ativo = ativo
        set_audit_on_update(tipo, user_id=user_id)
        db.session.add(tipo)
        db.session.commit()
        return redirect(url_for('auth.lista_tipos_obra'))

    novo = AuxTipoObra(nome=nome, descricao=request.form.get('descricao'), ativo=ativo, empresa_id=_current_option_empresa_id())
    set_audit_on_create(novo, user_id=user_id)
    db.session.add(novo)
    db.session.commit()
    return redirect(url_for('auth.lista_tipos_obra'))

@auth_bp.get("/editar-tipo-obra/<int:id>")
@login_required
@role_required(PERM_MANAGEMENT)
def editar_tipo_obra(id):
    tipo = hydrate_audit_metadata(AuxTipoObra.query.get_or_404(id))
    if _is_system_option(tipo):
        return _redirect_system_option('auth.visualizar_tipo_obra', tipo.id)
    return render_template("cadastros/obras/form_tipo_obra.html", item=tipo, view_mode=False)

@auth_bp.post('/excluir-tipo-obra/<int:id>')
@auth_bp.post('/toggle-tipo-obra/<int:id>')
@login_required
@role_required(PERM_MANAGEMENT)
def excluir_tipo_obra(id):
    user_id = get_current_user_id()
    tipo = AuxTipoObra.query.get(id)
    if tipo:
        if _is_system_option(tipo):
            flash("Registros do sistema não podem ser ativados ou inativados.", "warning")
            return redirect(url_for('auth.lista_tipos_obra'))
        if tipo.ativo:
            set_audit_on_inactivate(tipo, user_id=user_id)
        else:
            tipo.ativo = True
            set_audit_on_update(tipo, user_id=user_id)
        db.session.add(tipo)
        db.session.commit()
    return redirect(url_for('auth.lista_tipos_obra'))

@auth_bp.get('/visualizar-tipo-obra/<int:id>')
@login_required
def visualizar_tipo_obra(id):
    tipo = hydrate_audit_metadata(AuxTipoObra.query.get_or_404(id))
    return render_template('cadastros/obras/form_tipo_obra.html', item=tipo, view_mode=True)
