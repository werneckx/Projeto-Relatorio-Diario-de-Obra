from app.routes.auth_common import *
from app.models.cliente import Cliente
from app.models.obra import FrenteTrabalho, FrenteColaborador, ObraUsuario
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


def _get_centros_custo_options(empresa_id):
    if not empresa_id:
        return []

    rows = (
        db.session.query(FrenteTrabalho.centro_custo)
        .filter(FrenteTrabalho.empresa_id == empresa_id)
        .filter(FrenteTrabalho.centro_custo.isnot(None))
        .all()
    )
    values = sorted({(v or "").strip() for (v,) in rows if (v or "").strip()})
    return values


def _current_empresa_id(user=None):
    return session.get("empresa_id") or getattr(user, "empresa_id", None)


def _get_obras_permitidas_ids(user, empresa_id):
    if not user or not empresa_id:
        return []

    if getattr(user, "is_admin", False):
        return [
            obra_id
            for (obra_id,) in (
                db.session.query(Obra.id)
                .filter(Obra.empresa_id == empresa_id)
                .all()
            )
        ]

    return [
        obra_id
        for (obra_id,) in (
            db.session.query(ObraUsuario.obra_id)
            .filter(
                ObraUsuario.usuario_id == user.id,
                ObraUsuario.empresa_id == empresa_id,
                ObraUsuario.ativo.is_(True),
            )
            .all()
        )
    ]


def _apply_obras_usuario_scope(query, user, empresa_id):
    if not user or not empresa_id:
        return query.filter(False)

    if getattr(user, "is_admin", False):
        return query.filter(Obra.empresa_id == empresa_id)

    return (
        query
        .join(
            ObraUsuario,
            db.and_(
                ObraUsuario.obra_id == Obra.id,
                ObraUsuario.empresa_id == Obra.empresa_id,
            ),
        )
        .filter(
            Obra.empresa_id == empresa_id,
            ObraUsuario.usuario_id == user.id,
            ObraUsuario.ativo.is_(True),
        )
        .distinct()
    )


def _get_admin_users_empresa(empresa_id):
    if not empresa_id:
        return []

    admin_names = {ROLE_ADMIN, "ADMINISTRADOR"}
    admins = (
        Usuario.query
        .join(UsuarioPapel, UsuarioPapel.usuario_id == Usuario.id)
        .join(Papel, Papel.id == UsuarioPapel.papel_id)
        .filter(
            Usuario.empresa_id == empresa_id,
            db.or_(UsuarioPapel.empresa_id.is_(None), UsuarioPapel.empresa_id == empresa_id),
            Usuario.ativo.is_(True),
            UsuarioPapel.ativo.is_(True),
            Papel.ativo.is_(True),
            func.upper(func.trim(Papel.nome)).in_(admin_names),
            db.or_(Papel.empresa_id.is_(None), Papel.empresa_id == empresa_id),
        )
        .distinct()
        .all()
    )
    admin_ids = {admin.id for admin in admins}

    for usuario in Usuario.query.filter_by(empresa_id=empresa_id, ativo=True).all():
        if usuario.id not in admin_ids and getattr(usuario, "is_admin", False):
            admins.append(usuario)
            admin_ids.add(usuario.id)

    return admins


def _ensure_obra_usuario_access(obra, usuario_id, criado_por=None):
    if not obra or not usuario_id:
        return

    obra_usuario = ObraUsuario.query.filter_by(
        empresa_id=obra.empresa_id,
        obra_id=obra.id,
        usuario_id=usuario_id,
    ).first()
    if obra_usuario:
        obra_usuario.ativo = True
        set_audit_on_update(obra_usuario, user_id=criado_por)
        return

    novo_vinculo = ObraUsuario(
        empresa_id=obra.empresa_id,
        obra_id=obra.id,
        usuario_id=usuario_id,
        ativo=True,
        criado_por=criado_por,
    )
    set_audit_on_create(novo_vinculo, user_id=criado_por)
    db.session.add(novo_vinculo)


def _sync_admin_obras_empresa(empresa_id, criado_por=None):
    if not empresa_id:
        return 0

    admins = _get_admin_users_empresa(empresa_id)
    obras = Obra.query.filter_by(empresa_id=empresa_id).all()
    if not admins or not obras:
        return 0

    existentes = {
        (obra_id, usuario_id): ativo
        for obra_id, usuario_id, ativo in (
            db.session.query(ObraUsuario.obra_id, ObraUsuario.usuario_id, ObraUsuario.ativo)
            .filter(ObraUsuario.empresa_id == empresa_id)
            .all()
        )
    }

    alterados = 0
    for admin in admins:
        for obra in obras:
            chave = (obra.id, admin.id)
            if chave not in existentes or existentes[chave] is not True:
                _ensure_obra_usuario_access(obra, admin.id, criado_por=criado_por or admin.id)
                existentes[chave] = True
                alterados += 1

    return alterados


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
    user = Usuario.query.get(session.get("user_id"))
    empresa_id = _current_empresa_id(user)
    if user and getattr(user, "is_admin", False):
        try:
            if _sync_admin_obras_empresa(empresa_id, criado_por=user.id):
                db.session.commit()
        except Exception:
            db.session.rollback()

    query = Obra.query.order_by(Obra.id.asc())
    query = _apply_obras_usuario_scope(query, user, empresa_id)
        
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
    user = Usuario.query.get(session.get("user_id"))
    empresa_id = _current_empresa_id(user)
    if user and getattr(user, "is_admin", False):
        try:
            if _sync_admin_obras_empresa(empresa_id, criado_por=user.id):
                db.session.commit()
        except Exception:
            db.session.rollback()

    ids = _parse_export_ids()
    requested_columns = _parse_export_columns(OBRA_EXPORT_COLUMNS)

    query = Obra.query.filter_by(empresa_id=empresa_id).order_by(Obra.nome.asc())
    query = _apply_obras_usuario_scope(query, user, empresa_id)

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
    tipos_obra = AuxTipoObra.query.filter_by(ativo=True).order_by(AuxTipoObra.nome.asc()).all()
    mao_de_obra_options = AuxFuncoes.query.filter_by(ativo=True).order_by(AuxFuncoes.nome.asc()).all()
    centros_custo = _get_centros_custo_options(session.get('empresa_id'))
    return render_template(
        "cadastros/obras/form_obra.html",
        item=None,
        usuarios=usuarios,
        clientes=clientes,
        tipos_obra=tipos_obra,
        mao_de_obra_options=mao_de_obra_options,
        equipe_obra=[],
        centros_custo=centros_custo,
    )

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
    set_audit_on_update(obra)
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
    def _parse_date(value):
        value = (value or "").strip()
        if not value:
            return None
        return datetime.strptime(value, "%Y-%m-%d").date()

    def _parse_time(value):
        value = (value or "").strip()
        if not value:
            return None
        return datetime.strptime(value, "%H:%M").time()

    def _parse_bool(value, default=False):
        if value is None:
            return default
        value = str(value).strip().lower()
        if value in ("1", "true", "t", "yes", "y", "on"):
            return True
        if value in ("0", "false", "f", "no", "n", "off"):
            return False
        return default

    def _validation_error(message):
        flash(message, "danger")
        return redirect(url_for("auth.lista_obras"))

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

    nome = (request.form.get("nome") or "").strip()
    if not nome:
        flash("Erro: o nome da obra é obrigatório.", "danger")
        return redirect(url_for("auth.lista_obras"))

    criado_por = session.get('user_id')
    audit_user_id = get_current_user_id()

    # Campos do schema (com fallback para nomes legados)
    data_inicio_str = request.form.get("data_inicio") or request.form.get("inicio")
    data_fim_planejada_str = request.form.get("data_fim_planejada")
    data_fim_str = request.form.get("data_fim") or request.form.get("termino")

    hora_entrada_padrao_str = request.form.get("hora_entrada_padrao") or request.form.get("horario_entrada")
    intervalo_entrada_padrao_str = request.form.get("intervalo_entrada_padrao")
    intervalo_saida_padrao_str = request.form.get("intervalo_saida_padrao")
    hora_saida_padrao_str = request.form.get("hora_saida_padrao") or request.form.get("horario_saida")

    cep = request.form.get('cep')
    ibge_municipio = request.form.get('ibge_municipio')
    logradouro = request.form.get("logradouro") or request.form.get("endereco")
    numero = request.form.get('numero')
    complemento = request.form.get('complemento')
    bairro = request.form.get('bairro')
    cidade = request.form.get('cidade')
    estado = request.form.get('estado')

    tipo_obra_id_raw = (request.form.get("tipo_obra_id") or "").strip() or None
    usuario_responsavel_id_raw = (request.form.get("usuario_responsavel_id") or request.form.get("id_responsavel") or "").strip() or None
    ativo = _parse_bool(request.form.get("ativo"), default=_parse_bool(request.form.get("status"), default=True))
    frentes_payload = request.form.get('frentes_json')
    equipe_payload = request.form.get('equipe_obra_json')

    try:
        data_inicio = _parse_date(data_inicio_str)
        data_fim_planejada = _parse_date(data_fim_planejada_str)
        data_fim = _parse_date(data_fim_str)
        frentes_data = json.loads(frentes_payload) if frentes_payload else {}

        if data_inicio and data_fim_planejada and data_fim_planejada < data_inicio:
            return _validation_error("Erro: a data de fim planejada não pode anteceder a data de início da obra.")

        if data_inicio and data_fim and data_fim < data_inicio:
            return _validation_error("Erro: a data de fim real não pode anteceder a data de início da obra.")

        limite_obra = min([d for d in (data_fim_planejada, data_fim) if d], default=None)
        frentes_para_validar = list(frentes_data.get("novas", [])) + list(frentes_data.get("editadas", []))
        for indice, frente_data in enumerate(frentes_para_validar, start=1):
            frente_nome = (frente_data.get("nome_frente") or f"Frente {indice}").strip()
            frente_inicio = _parse_date(frente_data.get("data_inicio"))
            frente_fim_planejada = _parse_date(frente_data.get("data_planejada") or frente_data.get("data_fim_planejada"))
            frente_fim = _parse_date(frente_data.get("data_fim"))

            if data_inicio and frente_inicio and frente_inicio < data_inicio:
                return _validation_error(f"Erro: a data de início da frente '{frente_nome}' não pode anteceder a data de início da obra.")

            if frente_inicio and frente_fim_planejada and frente_fim_planejada < frente_inicio:
                return _validation_error(f"Erro: a data de fim planejada da frente '{frente_nome}' não pode anteceder sua data de início.")

            if frente_inicio and frente_fim and frente_fim < frente_inicio:
                return _validation_error(f"Erro: a data de fim real da frente '{frente_nome}' não pode anteceder sua data de início.")

            if limite_obra and frente_fim_planejada and frente_fim_planejada > limite_obra:
                return _validation_error(f"Erro: a data de fim planejada da frente '{frente_nome}' não pode ultrapassar o prazo da obra.")

            if limite_obra and frente_fim and frente_fim > limite_obra:
                return _validation_error(f"Erro: a data de fim real da frente '{frente_nome}' não pode ultrapassar o prazo da obra.")

        cep_limpo = ''.join(ch for ch in (cep or "") if ch.isdigit())
        if not obra_id and cep_limpo and (len(cep_limpo) != 8 or not cidade or not estado or not ibge_municipio):
            return _validation_error("Erro: informe um CEP válido para carregar Cidade, Estado e IBGE.")

        hora_entrada_padrao = _parse_time(hora_entrada_padrao_str)
        intervalo_entrada_padrao = _parse_time(intervalo_entrada_padrao_str)
        intervalo_saida_padrao = _parse_time(intervalo_saida_padrao_str)
        hora_saida_padrao = _parse_time(hora_saida_padrao_str)

        tipo_obra_id = int(tipo_obra_id_raw) if tipo_obra_id_raw else None
        usuario_responsavel_id = int(usuario_responsavel_id_raw) if usuario_responsavel_id_raw else None

        if usuario_responsavel_id:
            usuario_resp = Usuario.query.filter_by(id=usuario_responsavel_id, status=1).first()
            if not usuario_resp:
                flash("Erro: o responsável da obra deve ser um usuário ativo.", "danger")
                return redirect(url_for("auth.lista_obras"))

        if tipo_obra_id:
            tipo_obra = AuxTipoObra.query.filter_by(id=tipo_obra_id, ativo=True).first()
            if not tipo_obra:
                flash("Erro: tipo de obra inválido.", "danger")
                return redirect(url_for("auth.lista_obras"))

        if obra_id:
            empresa_id = session.get('empresa_id')
            obra = Obra.query.filter_by(id=obra_id, empresa_id=empresa_id).first()
            obra.nome = nome
            obra.cnpj_obra = cnpj_obra
            obra.cliente_id = cliente.id
            obra.tipo_obra_id = tipo_obra_id
            obra.usuario_responsavel_id = usuario_responsavel_id
            obra.data_inicio = data_inicio
            obra.data_fim_planejada = data_fim_planejada
            obra.data_fim = data_fim
            obra.hora_entrada_padrao = hora_entrada_padrao
            obra.intervalo_entrada_padrao = intervalo_entrada_padrao
            obra.intervalo_saida_padrao = intervalo_saida_padrao
            obra.hora_saida_padrao = hora_saida_padrao
            obra.cep = cep
            obra.logradouro = logradouro
            obra.numero = numero
            obra.complemento = complemento
            obra.bairro = bairro
            obra.cidade = cidade
            obra.estado = estado
            obra.ativo = ativo
            set_audit_on_update(obra, user_id=audit_user_id)
            flash("Obra atualizada com sucesso!", "success")
        else:
            obra = Obra(
                empresa_id=session.get('empresa_id'),
                nome=nome,
                cliente_id=cliente.id,
                cnpj_obra=cnpj_obra,
                criado_por=criado_por if criado_por else None,
                tipo_obra_id=tipo_obra_id,
                usuario_responsavel_id=usuario_responsavel_id,
                data_inicio=data_inicio,
                data_fim_planejada=data_fim_planejada,
                data_fim=data_fim,
                hora_entrada_padrao=hora_entrada_padrao,
                intervalo_entrada_padrao=intervalo_entrada_padrao,
                intervalo_saida_padrao=intervalo_saida_padrao,
                hora_saida_padrao=hora_saida_padrao,
                cep=cep,
                logradouro=logradouro,
                numero=numero,
                complemento=complemento,
                bairro=bairro,
                cidade=cidade,
                estado=estado,
                ativo=ativo
            )
            set_audit_on_create(obra, user_id=audit_user_id)
            db.session.add(obra)
            db.session.flush() 
            flash("Obra cadastrada com sucesso!", "success")

            usuarios_com_acesso = {criado_por} if criado_por else set()
            usuarios_com_acesso.update(admin.id for admin in _get_admin_users_empresa(obra.empresa_id))
            for usuario_id in usuarios_com_acesso:
                _ensure_obra_usuario_access(obra, usuario_id, criado_por=criado_por)

        if frentes_payload:
            data = frentes_data
            for f_id in data.get('removidas', []):
                if not f_id:
                    continue
                frente = FrenteTrabalho.query.filter_by(frente_trabalho_id=f_id, obra_id=obra.id, empresa_id=obra.empresa_id).first()
                if frente:
                    set_audit_on_inactivate(frente, user_id=audit_user_id)
            
            for f_nova in data.get('novas', []):
                nova_frente = FrenteTrabalho(
                    empresa_id=session.get('empresa_id'),
                    obra_id=obra.id,
                    nome_frente=(f_nova.get('nome_frente') or '').strip() or None,
                    centro_custo=f_nova.get('centro_custo'),
                    data_inicio=datetime.strptime(f_nova.get('data_inicio'), '%Y-%m-%d').date() if f_nova.get('data_inicio') else None,
                    data_planejada=datetime.strptime(f_nova.get('data_planejada'), '%Y-%m-%d').date() if f_nova.get('data_planejada') else None,
                    data_fim=datetime.strptime(f_nova.get('data_fim'), '%Y-%m-%d').date() if f_nova.get('data_fim') else None,
                    ativo=_parse_bool(f_nova.get('ativo'), default=True),
                )
                set_audit_on_create(nova_frente, user_id=audit_user_id)
                db.session.add(nova_frente)

            for f_edit in data.get('editadas', []):
                frente_id = f_edit.get('frente_trabalho_id') or f_edit.get('id_frente_trabalho')
                frente_existente = FrenteTrabalho.query.get(frente_id)
                if frente_existente and frente_existente.obra_id == obra.id:
                    frente_existente.nome_frente = (f_edit.get('nome_frente') or '').strip() or None
                    frente_existente.centro_custo = f_edit.get('centro_custo')
                    frente_existente.data_inicio = datetime.strptime(f_edit.get('data_inicio'), '%Y-%m-%d').date() if f_edit.get('data_inicio') else None
                    frente_existente.data_planejada = datetime.strptime(f_edit.get('data_planejada'), '%Y-%m-%d').date() if f_edit.get('data_planejada') else None
                    frente_existente.data_fim = datetime.strptime(f_edit.get('data_fim'), '%Y-%m-%d').date() if f_edit.get('data_fim') else None
                    frente_existente.ativo = _parse_bool(f_edit.get('ativo'), default=True)
                    set_audit_on_update(frente_existente, user_id=audit_user_id)

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
    obra = hydrate_audit_metadata(Obra.query.filter_by(id=id, empresa_id=empresa_id).first_or_404())
    frentes = (
        FrenteTrabalho.query
        .filter_by(obra_id=id, empresa_id=empresa_id)
        # MySQL não suporta "NULLS LAST" no ORDER BY. Usamos expressão booleana para empurrar NULLs pro fim.
        .order_by(FrenteTrabalho.data_inicio.is_(None), FrenteTrabalho.data_inicio.asc(), FrenteTrabalho.id.asc())
        .all()
    )
    usuarios = Usuario.query.filter_by(status=1).all()
    clientes = Cliente.query.filter_by(empresa_id=session.get('empresa_id'), ativo=True).order_by(Cliente.razao_social.asc()).all()
    tipos_obra = AuxTipoObra.query.filter_by(ativo=True).order_by(AuxTipoObra.nome.asc()).all()
    mao_de_obra_options = AuxFuncoes.query.filter_by(ativo=True).order_by(AuxFuncoes.nome.asc()).all()
    equipe_obra = _get_equipe_obra_payload(id)
    centros_custo = _get_centros_custo_options(session.get('empresa_id'))
    return render_template(
        "cadastros/obras/form_obra.html",
        item=obra,
        frentes=frentes,
        usuarios=usuarios,
        clientes=clientes,
        tipos_obra=tipos_obra,
        mao_de_obra_options=mao_de_obra_options,
        equipe_obra=equipe_obra,
        centros_custo=centros_custo,
    )

@auth_bp.get("/visualizar-obra/<int:id>")
@login_required
def visualizar_obra(id):
    # Security scope
    scope_ids = get_user_scope_ids()
    if scope_ids is not None and id not in scope_ids:
        flash("Acesso restrito.", "danger")
        return redirect(url_for('auth.lista_obras'))

    empresa_id = session.get('empresa_id')
    item = hydrate_audit_metadata(Obra.query.filter_by(id=id, empresa_id=empresa_id).first_or_404())
    usuarios = Usuario.query.filter_by(status=1).all()
    clientes = Cliente.query.filter_by(empresa_id=session.get('empresa_id'), ativo=True).order_by(Cliente.razao_social.asc()).all()
    tipos_obra = AuxTipoObra.query.filter_by(ativo=True).order_by(AuxTipoObra.nome.asc()).all()
    frentes = (
        FrenteTrabalho.query
        .filter_by(obra_id=id, empresa_id=empresa_id)
        .order_by(FrenteTrabalho.data_inicio.is_(None), FrenteTrabalho.data_inicio.asc(), FrenteTrabalho.id.asc())
        .all()
    )
    usuario = (
        Usuario.query.filter_by(status=1)
        .outerjoin(Colaborador, Usuario.colaborador_id == Colaborador.id)
        .order_by(func.coalesce(Colaborador.nome, Usuario.email).asc())
        .all()
    )
    mao_de_obra_options = AuxFuncoes.query.filter_by(ativo=True).order_by(AuxFuncoes.nome.asc()).all()
    equipe_obra = _get_equipe_obra_payload(id)
    centros_custo = _get_centros_custo_options(session.get('empresa_id'))
    
    return render_template(
        "cadastros/obras/form_obra.html", 
        item=item, 
        view_mode=True, 
        categoria="obra",
        frentes=frentes,
        usuario=usuario,
        usuarios=usuarios,
        clientes=clientes,
        tipos_obra=tipos_obra,
        mao_de_obra_options=mao_de_obra_options,
        equipe_obra=equipe_obra,
        centros_custo=centros_custo,
    )


def _get_frente_or_404(frente_id: int):
    empresa_id = session.get("empresa_id")
    frente = FrenteTrabalho.query.filter_by(id=frente_id, empresa_id=empresa_id).first_or_404()

    scope_ids = get_user_scope_ids()
    if scope_ids is not None and frente.obra_id not in scope_ids:
        abort(403)

    return frente


def _serialize_frente_colaborador(vinculo: FrenteColaborador):
    colaborador = vinculo.colaborador
    return {
        "id": vinculo.id,
        "vinculo_id": vinculo.id,
        "colaborador_id": vinculo.colaborador_id,
        "colaborador_nome": colaborador.nome if colaborador else "",
        "cpf": (colaborador.cadastro_pessoa_fisica if colaborador else None),
        "colaborador_cpf": (colaborador.cadastro_pessoa_fisica if colaborador else None),
        "funcao_id": vinculo.funcao_id,
        "funcao_nome": vinculo.funcao.nome if vinculo.funcao else "",
        "data_inicio": vinculo.data_inicio.isoformat() if vinculo.data_inicio else None,
        "data_fim": vinculo.data_fim.isoformat() if vinculo.data_fim else None,
        "ativo": bool(vinculo.ativo),
        "observacao": getattr(vinculo, "observacao", None),
    }


def _frente_colaboradores_counts(frente_id: int, empresa_id: int):
    rows = (
        FrenteColaborador.query
        .filter(
            FrenteColaborador.frente_id == frente_id,
            FrenteColaborador.empresa_id == empresa_id,
        )
        .all()
    )
    total = len(rows)
    ativos = sum(1 for row in rows if bool(row.ativo))
    inativos = total - ativos
    return {"total": total, "ativos": ativos, "inativos": inativos}


@auth_bp.get("/api/frente/<int:frente_id>/colaboradores")
@login_required
def api_frente_colaboradores_list(frente_id):
    frente = _get_frente_or_404(frente_id)

    rows = (
        FrenteColaborador.query
        .filter(FrenteColaborador.frente_id == frente.id, FrenteColaborador.empresa_id == frente.empresa_id)
        .outerjoin(Colaborador, Colaborador.id == FrenteColaborador.colaborador_id)
        .order_by(func.coalesce(Colaborador.nome, FrenteColaborador.id).asc())
        .all()
    )

    items = [_serialize_frente_colaborador(row) for row in rows]
    counts = _frente_colaboradores_counts(frente.id, frente.empresa_id)

    return jsonify({
        "ok": True,
        "frente": {"id": frente.id, "obra_id": frente.obra_id, "nome": frente.nome},
        "counts": counts,
        "items": items,
    })


@auth_bp.get("/api/colaboradores/search")
@login_required
def api_colaboradores_search():
    empresa_id = session.get("empresa_id")
    q = (request.args.get("q") or "").strip()
    tipo = (request.args.get("tipo") or "").strip().upper()
    cpf = (request.args.get("cpf") or "").strip()

    query = Colaborador.query.filter(Colaborador.empresa_id == empresa_id)

    if q:
        query = query.filter(
            db.or_(
                Colaborador.nome.ilike(f"%{q}%"),
                Colaborador.cadastro_pessoa_fisica.ilike(f"%{q}%"),
            )
        )
    if cpf:
        query = query.filter(Colaborador.cadastro_pessoa_fisica.ilike(f"%{cpf}%"))
    if tipo in ("PROPRIO", "TERCEIRO", "CLIENTE"):
        query = query.filter(Colaborador.tipo == tipo)

    colaboradores = query.order_by(Colaborador.nome.asc()).limit(50).all()

    items = []
    for c in colaboradores:
        vinculo = (
            FrenteColaborador.query
            .filter(
                FrenteColaborador.empresa_id == empresa_id,
                FrenteColaborador.colaborador_id == c.id,
                FrenteColaborador.ativo.is_(True),
                FrenteColaborador.data_fim.is_(None),
            )
            .order_by(
                FrenteColaborador.data_inicio.is_(None),
                FrenteColaborador.data_inicio.desc(),
                FrenteColaborador.id.desc(),
            )
            .first()
        )
        items.append({
            "id": c.id,
            "nome": c.nome,
            "tipo": c.tipo,
            "cpf": c.cadastro_pessoa_fisica,
            "ativo": bool(c.ativo),
            "funcao_atual": vinculo.funcao.nome if (vinculo and vinculo.funcao) else None,
        })

    return jsonify({"ok": True, "items": items})


@auth_bp.post("/api/frente/<int:frente_id>/colaboradores")
@login_required
@permission_required("obra.manage")
def api_frente_colaboradores_create(frente_id):
    def _parse_date(value):
        value = (value or "").strip()
        if not value:
            return None
        return datetime.strptime(value, "%Y-%m-%d").date()

    frente = _get_frente_or_404(frente_id)

    data = request.get_json(silent=True) or {}
    colaborador_id = data.get("colaborador_id")
    funcao_id = data.get("funcao_id")
    data_inicio = data.get("data_inicio")
    data_fim = data.get("data_fim")
    ativo = data.get("ativo", True)

    if not colaborador_id:
        return jsonify({"ok": False, "error": "Colaborador é obrigatório."}), 400

    colaborador = Colaborador.query.filter_by(id=colaborador_id, empresa_id=frente.empresa_id).first()
    if not colaborador:
        return jsonify({"ok": False, "error": "Colaborador inválido."}), 400

    novo = FrenteColaborador(
        empresa_id=frente.empresa_id,
        frente_id=frente.id,
        colaborador_id=int(colaborador_id),
        funcao_id=int(funcao_id) if funcao_id else None,
        data_inicio=_parse_date(data_inicio) if data_inicio else None,
        data_fim=_parse_date(data_fim) if data_fim else None,
        ativo=bool(ativo),
    )
    set_audit_on_create(novo)
    db.session.add(novo)
    db.session.commit()
    novo = (
        FrenteColaborador.query
        .filter_by(id=novo.id, empresa_id=frente.empresa_id)
        .outerjoin(Colaborador, Colaborador.id == FrenteColaborador.colaborador_id)
        .first()
    )
    return jsonify({
        "ok": True,
        "id": novo.id,
        "item": _serialize_frente_colaborador(novo),
        "counts": _frente_colaboradores_counts(frente.id, frente.empresa_id),
    })


@auth_bp.put("/api/frente-colaborador/<int:vinculo_id>")
@login_required
@permission_required("obra.manage")
def api_frente_colaborador_update(vinculo_id):
    def _parse_date(value):
        value = (value or "").strip()
        if not value:
            return None
        return datetime.strptime(value, "%Y-%m-%d").date()

    empresa_id = session.get("empresa_id")
    vinculo = FrenteColaborador.query.filter_by(id=vinculo_id, empresa_id=empresa_id).first_or_404()
    _get_frente_or_404(vinculo.frente_id)

    data = request.get_json(silent=True) or {}
    vinculo.funcao_id = int(data.get("funcao_id")) if data.get("funcao_id") else None
    vinculo.data_inicio = _parse_date(data.get("data_inicio")) if data.get("data_inicio") else None
    vinculo.data_fim = _parse_date(data.get("data_fim")) if data.get("data_fim") else None
    vinculo.ativo = bool(data.get("ativo", vinculo.ativo))
    set_audit_on_update(vinculo)

    db.session.commit()
    return jsonify({
        "ok": True,
        "item": _serialize_frente_colaborador(vinculo),
        "counts": _frente_colaboradores_counts(vinculo.frente_id, vinculo.empresa_id),
    })


@auth_bp.post("/api/frente-colaborador/<int:vinculo_id>/toggle")
@login_required
@permission_required("obra.manage")
def api_frente_colaborador_toggle(vinculo_id):
    empresa_id = session.get("empresa_id")
    vinculo = FrenteColaborador.query.filter_by(id=vinculo_id, empresa_id=empresa_id).first_or_404()
    _get_frente_or_404(vinculo.frente_id)

    vinculo.ativo = not bool(vinculo.ativo)
    if vinculo.ativo and vinculo.data_fim is not None:
        vinculo.data_fim = None
    elif not vinculo.ativo and vinculo.data_fim is None:
        vinculo.data_fim = datetime.utcnow().date()
    set_audit_on_update(vinculo)
    db.session.commit()
    return jsonify({
        "ok": True,
        "ativo": bool(vinculo.ativo),
        "item": _serialize_frente_colaborador(vinculo),
        "counts": _frente_colaboradores_counts(vinculo.frente_id, vinculo.empresa_id),
    })

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
    set_audit_on_update(obra)
    try:
        db.session.commit()
        return '', 200 
    except Exception:
        db.session.rollback()
        return '', 500
