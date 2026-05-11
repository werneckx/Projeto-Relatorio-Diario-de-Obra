from app.routes.auth_common import *

@auth_bp.get("/lista-climas")
@login_required
def lista_climas():
    climas = AuxClima.query.filter_by(ativo=True).order_by(AuxClima.nome.asc()).all()
    return render_template("list_climas.html", opcoes=climas, categoria="clima")

@auth_bp.get('/criar-clima')
@login_required
@role_required(PERM_WRITE_BASIC)
def criar_clima():
    return render_template('form_clima.html', item=None, view_mode=False)

@auth_bp.post('/gerar-clima')
@login_required
@role_required(PERM_WRITE_BASIC)
def gerar_clima():
    clima_id = request.form.get('id')
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
        clima.nome = nome
        clima.ativo = ativo
        db.session.add(clima)
        db.session.commit()
        return redirect(url_for('auth.lista_climas'))

    novo = AuxClima(nome=nome, tipo_lista=tipo_lista, ativo=ativo)
    db.session.add(novo)
    db.session.commit()
    return redirect(url_for('auth.lista_climas'))

@auth_bp.get('/visualizar-clima/<int:id>')
@login_required
def visualizar_clima(id):
    clima = AuxClima.query.get_or_404(id)
    return render_template('form_clima.html', item=clima, view_mode=True)

@auth_bp.get('/editar-clima/<int:id>')
@login_required
@role_required(PERM_WRITE_BASIC)
def editar_clima(id):
    clima = AuxClima.query.get_or_404(id)
    return render_template('form_clima.html', item=clima, view_mode=False)

@auth_bp.post('/excluir-clima/<int:id>')
@login_required
@role_required(PERM_MANAGEMENT)
def excluir_clima(id):
    clima = AuxClima.query.get(id)
    if clima:
        db.session.delete(clima)
        db.session.commit()
    return redirect(url_for('auth.lista_climas'))

# --- EQUIPAMENTOS ---
@auth_bp.get("/lista-equipamentos")
@login_required
def lista_equipamentos():
    equipamentos = AuxEquipamentos.query.filter_by(ativo=True).order_by(AuxEquipamentos.nome.asc()).all()
    return render_template("list_equipamentos.html", opcoes=equipamentos, categoria="equipamento")

@auth_bp.get('/criar-equipamento')
@login_required
@role_required(PERM_WRITE_BASIC)
def criar_equipamento():
    return render_template('form_equipamento.html', item=None, view_mode=False)

@auth_bp.post('/gerar-equipamento')
@login_required
@role_required(PERM_WRITE_BASIC)
def gerar_equipamento():
    equipamento_id = request.form.get('id')
    tipo_lista = "Equipamentos"
    nome = _normalize_option_input(request.form.get('nome', ''))
    ativo = request.form.get('ativo') == '1'
    if not nome:
        flash('Nome do equipamento é obrigatório.', 'danger')
        return redirect(url_for('auth.lista_equipamentos'))

    equipamento_existente = _find_duplicate_option(AuxEquipamentos, nome, tipo_lista, exclude_id=equipamento_id)

    if equipamento_existente:
        flash('Já existe um equipamento cadastrado com esse nome.', 'danger')
        if equipamento_id: return redirect(url_for('auth.editar_equipamento', id=equipamento_id))
        return redirect(url_for('auth.criar_equipamento'))

    if equipamento_id:
        equipamento = AuxEquipamentos.query.get(equipamento_id)
        equipamento.nome = nome
        equipamento.ativo = ativo
        db.session.add(equipamento)
    else:
        novo = AuxEquipamentos(nome=nome, tipo_lista=tipo_lista, ativo=ativo)
        db.session.add(novo)
    db.session.commit()
    return redirect(url_for('auth.lista_equipamentos'))

@auth_bp.get('/visualizar-equipamento/<int:id>')
@login_required
def visualizar_equipamento(id):
    equipamento = AuxEquipamentos.query.get_or_404(id)
    return render_template('form_equipamento.html', item=equipamento, view_mode=True)

@auth_bp.get('/editar-equipamento/<int:id>')
@login_required
@role_required(PERM_WRITE_BASIC)
def editar_equipamento(id):
    equipamento = AuxEquipamentos.query.get_or_404(id)
    return render_template('form_equipamento.html', item=equipamento, view_mode=False)

@auth_bp.post('/excluir-equipamento/<int:id>')
@login_required
@role_required(PERM_MANAGEMENT)
def excluir_equipamento(id):
    equipamento = AuxEquipamentos.query.get(id)
    if equipamento:
        db.session.delete(equipamento)
        db.session.commit()
    return redirect(url_for('auth.lista_equipamentos'))

# --- TAGS ---
@auth_bp.get("/lista-tags-ocorrencias")
@login_required
def lista_tags_ocorrencias():
    tagsOcorrencias = AuxTagOcorrencia.query.filter_by(ativo=True).order_by(AuxTagOcorrencia.nome.asc()).all()
    return render_template("list_tags_ocorrencias.html", opcoes=tagsOcorrencias, categoria="tagsOcorrencias")

@auth_bp.get('/criar-tags-ocorrencias')
@login_required
@role_required(PERM_WRITE_BASIC)
def criar_tags_ocorrencias():
    return render_template('form_tags_ocorrencias.html', item=None, view_mode=False)

@auth_bp.post('/gerar-tags-ocorrencias')
@login_required
@role_required(PERM_WRITE_BASIC)
def gerar_tags_ocorrencias():
    tag_id = request.form.get('id')
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
        tag.nome = nome
        tag.ativo = ativo
        db.session.add(tag)
    else:
        db.session.add(AuxTagOcorrencia(nome=nome, tipo_lista="Tags Ocorrencias", ativo=ativo))
    db.session.commit()
    return redirect(url_for('auth.lista_tags_ocorrencias'))

@auth_bp.get('/visualizar-tags-ocorrencias/<int:id>')
@login_required
def visualizar_tags_ocorrencias(id):
    tag = AuxTagOcorrencia.query.get_or_404(id)
    return render_template('form_tags_ocorrencias.html', item=tag, view_mode=True)

@auth_bp.get('/editar-tags-ocorrencias/<int:id>')
@login_required
@role_required(PERM_WRITE_BASIC)
def editar_tags_ocorrencias(id):
    tag = AuxTagOcorrencia.query.get_or_404(id)
    return render_template('form_tags_ocorrencias.html', item=tag, view_mode=False)

@auth_bp.post('/excluir-tags-ocorrencias/<int:id>')
@login_required
@role_required(PERM_MANAGEMENT)
def excluir_tags_ocorrencias(id):
    tag = AuxTagOcorrencia.query.get(id)
    if tag:
        db.session.delete(tag)
        db.session.commit()
    return redirect(url_for('auth.lista_tags_ocorrencias'))

# --- MAO DE OBRA ---
@auth_bp.get("/lista-mao-obra")
@login_required
def lista_mao_obra():
    mao_obra = AuxFuncoes.query.filter_by(ativo=True).order_by(AuxFuncoes.nome.asc()).all()
    return render_template("list_mao_obra.html", opcoes=mao_obra, categoria="mao_obra")

@auth_bp.get('/criar-mao-obra')
@login_required
@role_required(PERM_WRITE_BASIC)
def criar_mao_obra():
    return render_template('form_mao_obra.html', item=None, view_mode=False)

@auth_bp.post('/gerar-mao-obra')
@login_required
@role_required(PERM_WRITE_BASIC)
def gerar_mao_obra():
    mo_id = request.form.get('id')
    nome = _normalize_option_input(request.form.get('nome', ''))
    tipo = _normalize_option_input(request.form.get('tipo', '')) or None
    ativo = request.form.get('ativo') == '1'
    if not nome:
        flash('Nome da mão de obra é obrigatório.', 'danger')
        return redirect(url_for('auth.lista_mao_obra'))

    mo_existente = _find_duplicate_option(AuxFuncoes, nome, "Mao de Obra", exclude_id=mo_id, tipo=tipo)

    if mo_existente:
        flash('Já existe uma mão de obra cadastrada com esse nome e tipo.', 'danger')
        if mo_id: return redirect(url_for('auth.editar_mao_obra', id=mo_id))
        return redirect(url_for('auth.criar_mao_obra'))

    if mo_id:
        mo = AuxFuncoes.query.get(mo_id)
        mo.nome = nome
        mo.tipo = tipo
        mo.ativo = ativo
        db.session.add(mo)
    else:
        db.session.add(AuxFuncoes(nome=nome, tipo_lista="Mao de Obra", tipo=tipo, ativo=ativo))
    db.session.commit()
    return redirect(url_for('auth.lista_mao_obra'))

@auth_bp.get('/visualizar-mao-obra/<int:id>')
@login_required
def visualizar_mao_obra(id):
    mo = AuxFuncoes.query.get_or_404(id)
    return render_template('form_mao_obra.html', item=mo, view_mode=True)

@auth_bp.get('/editar-mao-obra/<int:id>')
@login_required
@role_required(PERM_WRITE_BASIC)
def editar_mao_obra(id):
    mo = AuxFuncoes.query.get_or_404(id)
    return render_template('form_mao_obra.html', item=mo, view_mode=False)

@auth_bp.post('/excluir-mao-obra/<int:id>')
@login_required
@role_required(PERM_MANAGEMENT)
def excluir_mao_obra(id):
    mo = AuxFuncoes.query.get(id)
    if mo:
        db.session.delete(mo)
        db.session.commit()
    return redirect(url_for('auth.lista_mao_obra'))

#######################################################################################################
####################################################################################################### OBRAS
#######################################################################################################
