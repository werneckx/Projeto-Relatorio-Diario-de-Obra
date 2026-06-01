from app.routes.auth_common import *
from app.models.cliente import Cliente
from app.utils.export_service import make_csv_response, make_xlsx_response, make_pdf_response
from app.models.usuario import Colaborador
from sqlalchemy import func

OBRA_EXPORT_COLUMNS = [
    ("id", "ID"),
    ("nome", "Projeto"),
    ("cnpj", "CNPJ"),
    ("cliente", "Cliente"),
    ("cidade", "Cidade"),
    ("estado", "Estado"),
    ("endereco", "Endereço"),
    ("tipo", "Tipo"),
    ("progresso", "Progresso"),
    ("status", "Status"),
]


def _parse_export_columns(default_columns):
    requested = request.args.get("columns", "")
    if not requested:
        return [key for key, _ in default_columns]

    requested_keys = [key.strip() for key in requested.split(",") if key.strip()]
    selected = [key for key, _ in default_columns if key in requested_keys]
    return selected or [key for key, _ in default_columns]


def _parse_export_ids():
    raw_ids = request.args.get("ids", "")
    if not raw_ids:
        return []

    ids = []
    for part in raw_ids.split(","):
        try:
            ids.append(int(part))
        except ValueError:
            continue
    return ids


def _calculate_progress(obra):
    total = 0
    count = 0
    for frente in obra.frentes_trabalho or []:
        plan = frente.qtd_planejada or 0
        real = frente.qtd_realizada or 0
        if plan > 0:
            total += min(100, (real / plan) * 100)
            count += 1
    return int(total / count) if count else 0


def _build_obra_export_cell(obra, key):
    if key == "id":
        return obra.id
    if key == "nome":
        return obra.nome
    if key == "cnpj":
        return obra.cnpj or ""
    if key == "cliente":
        return obra.contratante or ""
    if key == "cidade":
        return obra.cidade or ""
    if key == "estado":
        return obra.estado or ""
    if key == "endereco":
        return obra.endereco or ""
    if key == "tipo":
        return obra.tipo_obra.nome if getattr(obra, "tipo_obra", None) else ""
    if key == "progresso":
        return f"{_calculate_progress(obra)}%"
    if key == "status":
        return "Ativa" if obra.status == 1 else "Inativa"
    return ""


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

    user_ids = set()
    for obra_obj in resultados:
        if obra_obj.criado_por:
            user_ids.add(obra_obj.criado_por)
        if obra_obj.modificado_por:
            user_ids.add(obra_obj.modificado_por)

    user_name_by_id = {}
    if user_ids:
        for u in Usuario.query.filter(Usuario.id.in_(list(user_ids))).all():
            user_name_by_id[u.id] = u.nome

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
            'tipo': obra_obj.tipo_obra.nome if obra_obj.tipo_obra else None,
            'status': obra_obj.status,
            'frentes_trabalho': obra_obj.frentes_trabalho,
            'criado_em': obra_obj.criado_em,
            'modificado_em': obra_obj.modificado_em,
            'criado_por': obra_obj.criado_por,
            'modificado_por': obra_obj.modificado_por,
            'criado_por_nome': user_name_by_id.get(obra_obj.criado_por) if obra_obj.criado_por else None,
            'modificado_por_nome': user_name_by_id.get(obra_obj.modificado_por) if obra_obj.modificado_por else None,
        }
        obras_formatadas.append(obra_dict)
    
    return render_template("cadastros/obras/list_obras.html", opcoes=obras_formatadas, categoria="obra")


@auth_bp.get('/lista-obras/export/<string:export_format>')
@login_required
def export_lista_obras(export_format):
    empresa_id = session.get("empresa_id")
    user = Usuario.query.get(session.get("user_id"))
    ids = _parse_export_ids()
    requested_columns = _parse_export_columns(OBRA_EXPORT_COLUMNS)

    query = Obra.query.filter_by(empresa_id=empresa_id).order_by(Obra.nome.asc())
    if user.papel != ROLE_ADMIN:
        meus_ids = [o.id for o in Obra.query.filter_by(empresa_id=empresa_id).all()]
        query = query.filter(Obra.id.in_(meus_ids))

    if ids:
        query = query.filter(Obra.id.in_(ids))

    obras = query.all()
    headers = [label for key, label in OBRA_EXPORT_COLUMNS if key in requested_columns]
    rows = [[_build_obra_export_cell(obra, key) for key in requested_columns] for obra in obras]

    if export_format == 'csv':
        return make_csv_response(headers, rows, prefix='obras')
    if export_format == 'xlsx':
        return make_xlsx_response(headers, rows, prefix='obras')
    if export_format == 'pdf':
        return make_pdf_response(
            'exports/export_generic_table.html',
            {'title': 'Cadastro de Obras', 'headers': headers, 'rows': rows},
            prefix='obras',
        )

    abort(404)


@auth_bp.get("/criar-obra")
@login_required
@permission_required('obra.manage')
def criar_obra():
    usuarios = Usuario.query.filter_by(status=1).all()
    clientes = Cliente.query.filter_by(empresa_id=session.get('empresa_id'), ativo=True).order_by(Cliente.razao_social.asc()).all()
    mao_de_obra_options = AuxFuncoes.query.filter_by(ativo=True).order_by(AuxFuncoes.nome.asc()).all()
    return render_template("cadastros/obras/form_obra.html", item=None, usuarios=usuarios, clientes=clientes, mao_de_obra_options=mao_de_obra_options, equipe_obra=[])

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
    return render_template("cadastros/obras/form_obra.html", item=obra, frentes=frentes, usuarios=usuarios, clientes=clientes, mao_de_obra_options=mao_de_obra_options, equipe_obra=equipe_obra)

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
    usuario = (
        Usuario.query.filter_by(status=1)
        .outerjoin(Colaborador, Usuario.colaborador_id == Colaborador.id)
        .order_by(func.coalesce(Colaborador.nome, Usuario.email).asc())
        .all()
    )
    mao_de_obra_options = AuxFuncoes.query.filter_by(ativo=True).order_by(AuxFuncoes.nome.asc()).all()
    equipe_obra = _get_equipe_obra_payload(id)
    
    return render_template(
        "cadastros/obras/form_obra.html", 
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
