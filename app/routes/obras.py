from app.routes.auth_common import *
from app.models.cliente import Cliente

@auth_bp.get("/lista-obras")
@login_required
def lista_obras():
    # SCOPING:
    user = Usuario.query.get(session.get("user_id"))
    query = Obra.query.order_by(Obra.id.asc())
    
    if user.papel != ROLE_ADMIN:
        meus_ids = [o.id for o in Obra.query.filter_by(empresa_id=session.get('empresa_id')).all()]
        query = query.filter(Obra.id.in_(meus_ids))
        
    resultados = query.all()
    obras_formatadas = []
    for obra_obj in resultados:
        obra_dict = {
            'id': obra_obj.id,
            'nome': obra_obj.nome,
            'cnpj': obra_obj.cnpj,
            'cliente': obra_obj.contratante,
            'cidade': obra_obj.cidade,
            'estado': obra_obj.estado,
            'endereco': obra_obj.endereco,
            'numero': obra_obj.numero,
            'complemento': obra_obj.complemento,
            'bairro': obra_obj.bairro,
            'cep': obra_obj.cep,
            'status': obra_obj.status,
            'frentes_trabalho': obra_obj.frentes_trabalho
        }
        obras_formatadas.append(obra_dict)
    
    return render_template("list_obras.html", opcoes=obras_formatadas, categoria="obra")

@auth_bp.get("/criar-obra")
@login_required
@permission_required('obra.manage')
def criar_obra():
    usuarios = Usuario.query.filter_by(status=1).all()
    clientes = Cliente.query.filter_by(empresa_id=session.get('empresa_id'), ativo=True).order_by(Cliente.razao_social.asc()).all()
    mao_de_obra_options = AuxFuncoes.query.filter_by(ativo=True).order_by(AuxFuncoes.nome.asc()).all()
    return render_template("form_obra.html", item=None, usuarios=usuarios, clientes=clientes, mao_de_obra_options=mao_de_obra_options, equipe_obra=[])

@auth_bp.post("/mudar-status-obras/<int:obraid>")
@login_required
@permission_required('obra.manage')
def toggle_user_obras(obraid):
    # Security scope check
    scope_ids = get_user_scope_ids()
    if scope_ids is not None and obraid not in scope_ids:
        return {"message": "Forbidden"}, 403

    empresa_id = session.get('empresa_id')
    obra = Obra.query.filter_by(id=obraid, empresa_id=empresa_id).first_or_404()
    obra.status = not obra.status 
    try:
        db.session.commit()
        return {"message": "Status atualizado com sucesso"}, 200
    except Exception as e:
        db.session.rollback()
        return {"message": f"Erro ao atualizar: {str(e)}"}, 500
    
@auth_bp.route('/gerar-obra', methods=['POST'])
@login_required
@permission_required('obra.manage')
def gerar_obra():
    obra_id = request.form.get("id")
    if obra_id:
        # Security scope
        scope_ids = get_user_scope_ids()
        if scope_ids is not None and int(obra_id) not in scope_ids:
             flash("Sem permissão para editar esta obra", "danger")
             return redirect(url_for('auth.lista_obras'))

    cnpj_obra = request.form.get('cnpj_obra')
    cliente_id = request.form.get('cliente_id')

    if not cliente_id:
        flash("Erro: selecione um cliente válido para esta obra.", "danger")
        return redirect(url_for('auth.lista_obras'))

    cliente = Cliente.query.filter_by(id=cliente_id, empresa_id=session.get('empresa_id')).first()
    if not cliente:
        flash("Erro: cliente inválido.", "danger")
        return redirect(url_for('auth.lista_obras'))

    obra_existente = Obra.query.filter_by(cnpj_obra=cnpj_obra).first() if cnpj_obra else None
    if obra_existente:
        if not obra_id or str(obra_existente.id) != str(obra_id):
            flash(f"Erro: O CNPJ {cnpj_obra} já está cadastrado.", "danger")
            return redirect(url_for('auth.lista_obras'))

    nome = request.form.get('nome')
    criado_por = session.get('user_id')
    inicio_str = request.form.get('inicio')
    termino_str = request.form.get('termino')
    horario_entrada_str = request.form.get('horario_entrada')
    horario_saida_str = request.form.get('horario_saida')
    cep = request.form.get('cep')
    endereco = request.form.get('endereco')
    numero = request.form.get('numero')
    complemento = request.form.get('complemento')
    bairro = request.form.get('bairro')
    cidade = request.form.get('cidade')
    estado = request.form.get('estado')
    status = 1 if request.form.get('status') == 'on' else 0
    frentes_payload = request.form.get('frentes_json')
    equipe_payload = request.form.get('equipe_obra_json')

    try:
        inicio = datetime.strptime(inicio_str, '%Y-%m-%d').date() if inicio_str else None
        termino = datetime.strptime(termino_str, '%Y-%m-%d').date() if termino_str else None
        horario_entrada = datetime.strptime(horario_entrada_str, '%H:%M').time() if horario_entrada_str else None
        horario_saida = datetime.strptime(horario_saida_str, '%H:%M').time() if horario_saida_str else None

        if obra_id:
            empresa_id = session.get('empresa_id')
            obra = Obra.query.filter_by(id=obra_id, empresa_id=empresa_id).first()
            obra.nome = nome
            obra.cnpj_obra = cnpj_obra
            obra.cliente_id = cliente.id
            obra.data_inicio = inicio
            obra.data_fim = termino
            obra.hora_entrada_padrao = horario_entrada
            obra.hora_saida_padrao = horario_saida
            obra.cep = cep
            obra.logradouro = endereco
            obra.numero = numero
            obra.complemento = complemento
            obra.bairro = bairro
            obra.cidade = cidade
            obra.estado = estado
            obra.status = status
            flash("Obra atualizada com sucesso!", "success")
        else:
            obra = Obra(
                empresa_id=session.get('empresa_id'),
                nome=nome,
                cliente_id=cliente.id,
                cnpj_obra=cnpj_obra,
                criado_por=criado_por if criado_por else None,
                data_inicio=inicio,
                data_fim=termino,
                hora_entrada_padrao=horario_entrada,
                hora_saida_padrao=horario_saida,
                cep=cep,
                logradouro=endereco,
                numero=numero,
                complemento=complemento,
                bairro=bairro,
                cidade=cidade,
                estado=estado,
                ativo=status
            )
            db.session.add(obra)
            db.session.flush() 
            flash("Obra cadastrada com sucesso!", "success")

            # Se quem criou foi um Gestor, adiciona automaticamente permissão pra ele
            current_user_obj = Usuario.query.get(session.get("user_id"))
            if current_user_obj.papel == ROLE_GESTOR:
                current_user_obj.obras_permitidas.append(obra)

        if frentes_payload:
            data = json.loads(frentes_payload)
            for f_id in data.get('removidas', []):
                if f_id: FrenteTrabalho.query.filter_by(frente_trabalho_id=f_id, obra_id=obra.id).delete()
            
            for f_nova in data.get('novas', []):
                nova_frente = FrenteTrabalho(
                    obra_id=obra.id,
                    nome_frente=f_nova['nome_frente'],
                    criado_por=f_nova['criado_por'] if f_nova['criado_por'] else None,
                    unidade=f_nova.get('unidade'),
                    qtd_planejada=float(f_nova.get('qtd_planejada')) if f_nova.get('qtd_planejada') else 0,
                    data_inicio=datetime.strptime(f_nova.get('data_inicio'), '%Y-%m-%d').date() if f_nova.get('data_inicio') else None,
                    data_planejada=datetime.strptime(f_nova.get('data_planejada'), '%Y-%m-%d').date() if f_nova.get('data_planejada') else None
                )
                db.session.add(nova_frente)

            for f_edit in data.get('editadas', []):
                frente_existente = FrenteTrabalho.query.get(f_edit['frente_trabalho_id'])
                if frente_existente and frente_existente.obra_id == obra.id:
                    frente_existente.nome_frente = f_edit['nome_frente']
                    frente_existente.criado_por = f_edit['criado_por'] if f_edit['criado_por'] else None
                    frente_existente.unidade = f_edit.get('unidade')
                    frente_existente.qtd_planejada = float(f_edit.get('qtd_planejada')) if f_edit.get('qtd_planejada') else 0
                    frente_existente.data_inicio = datetime.strptime(f_edit.get('data_inicio'), '%Y-%m-%d').date() if f_edit.get('data_inicio') else None
                    frente_existente.data_planejada = datetime.strptime(f_edit.get('data_planejada'), '%Y-%m-%d').date() if f_edit.get('data_planejada') else None

        # Legacy equipe de obra não possui modelo compatível com o schema atual.
        # O payload é preservado no formulário, mas não é gravado enquanto a tabela de suporte não estiver disponível.
        db.session.commit()
        return redirect(url_for('auth.lista_obras'))

    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao processar a solicitação: {str(e)}", "danger")
        return redirect(url_for('auth.lista_obras'))
    
@auth_bp.get("/editar-obra/<int:id>")
@login_required
@permission_required('obra.manage')
def editar_obra(id):
    # Security scope
    scope_ids = get_user_scope_ids()
    if scope_ids is not None and id not in scope_ids:
        abort(403)

    empresa_id = session.get('empresa_id')
    obra = Obra.query.filter_by(id=id, empresa_id=empresa_id).first_or_404()
    frentes = FrenteTrabalho.query.filter_by(obra_id=id).all()
    usuarios = Usuario.query.filter_by(status=1).all()
    clientes = Cliente.query.filter_by(empresa_id=session.get('empresa_id'), ativo=True).order_by(Cliente.razao_social.asc()).all()
    mao_de_obra_options = AuxFuncoes.query.filter_by(ativo=True).order_by(AuxFuncoes.nome.asc()).all()
    equipe_obra = _get_equipe_obra_payload(id)
    return render_template("form_obra.html", item=obra, frentes=frentes, usuarios=usuarios, clientes=clientes, mao_de_obra_options=mao_de_obra_options, equipe_obra=equipe_obra)

@auth_bp.get("/visualizar-obra/<int:id>")
@login_required
def visualizar_obra(id):
    # Security scope
    scope_ids = get_user_scope_ids()
    if scope_ids is not None and id not in scope_ids:
        flash("Acesso restrito.", "danger")
        return redirect(url_for('auth.lista_obras'))

    empresa_id = session.get('empresa_id')
    item = Obra.query.filter_by(id=id, empresa_id=empresa_id).first_or_404()
    usuarios = Usuario.query.filter_by(status=1).all()
    clientes = Cliente.query.filter_by(empresa_id=session.get('empresa_id'), ativo=True).order_by(Cliente.razao_social.asc()).all()
    frentes = FrenteTrabalho.query.filter_by(obra_id=id).all()
    usuario = Usuario.query.order_by(Usuario.nome).all()
    mao_de_obra_options = AuxFuncoes.query.filter_by(ativo=True).order_by(AuxFuncoes.nome.asc()).all()
    equipe_obra = _get_equipe_obra_payload(id)
    
    return render_template(
        "form_obra.html", 
        item=item, 
        view_mode=True, 
        categoria="obra",
        frentes=frentes,
        usuario=usuario,
        usuarios=usuarios,
        clientes=clientes,
        mao_de_obra_options=mao_de_obra_options,
        equipe_obra=equipe_obra
    )

@auth_bp.post("/obra/toggle-status/<int:id>")
@login_required
@permission_required('obra.manage')
def toggle_obra_status(id):
    # Security scope
    scope_ids = get_user_scope_ids()
    if scope_ids is not None and id not in scope_ids:
        return '', 403

    empresa_id = session.get('empresa_id')
    obra = Obra.query.filter_by(id=id, empresa_id=empresa_id).first_or_404()
    if obra.status == 1: obra.status = 0
    else: obra.status = 1
    try:
        db.session.commit()
        return '', 200 
    except Exception:
        db.session.rollback()
        return '', 500
