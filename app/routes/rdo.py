from app.routes.auth_common import *

@auth_bp.get("/criar-rdo")
@login_required
@permission_required('rdo.create')
def criar_rdo():
    # Carregar apenas obras ativas da empresa atual
    empresa_id = session.get("empresa_id")
    user = Usuario.query.get(session.get("user_id"))
    if user and user.papel == ROLE_ADMIN:
        obras = Obra.query.filter_by(empresa_id=empresa_id, status=1).all()
    else:
        # Filtra na memória as obras ativas do usuário
        obras = [o for o in Obra.query.filter_by(empresa_id=empresa_id).all() if o.status == 1]
    
    mao_de_obra_options = [{"id": m.id, "nome": m.nome, "tipo": m.tipo} for m in AuxFuncoes.query.filter_by(ativo=True).order_by(AuxFuncoes.nome.asc()).all()]
    equipamentos_options = [{"id": e.id, "nome": e.nome} for e in AuxEquipamentos.query.filter_by(ativo=True).order_by(AuxEquipamentos.nome.asc()).all()]
    tags_options = [{"id": t.id, "nome": t.nome} for t in AuxTagOcorrencia.query.filter_by(ativo=True).order_by(AuxTagOcorrencia.nome.asc()).all()]

    clima = AuxClima.query.filter_by(ativo=True).order_by(AuxClima.nome.asc()).all()
    frente_trabalho = FrenteTrabalho.query.filter_by(empresa_id=empresa_id).all()
    usuarios_obra = Usuario.query.filter_by(empresa_id=empresa_id, ativo=True).all()

    return render_template(
        "form_rdo.html", 
        item=None, 
        obras=obras, 
        clima=clima, 
        frente_trabalho=frente_trabalho, 
        usuarios_obra=usuarios_obra,
        view_mode=False,
        mao_de_obra_options=mao_de_obra_options,
        equipamentos_options=equipamentos_options, 
        tags_options=tags_options 
    )


@auth_bp.get("/api/obra/<int:id>")
@login_required
def get_obra_api(id):
    # SECURITY: Escopo por empresa
    empresa_id = session.get("empresa_id")
    scope_ids = get_user_scope_ids()
    if scope_ids is not None and id not in scope_ids:
        return jsonify({"error": "Acesso não autorizado a esta obra"}), 403

    obra = Obra.query.filter_by(id=id, empresa_id=empresa_id).first_or_404()
    frentes = FrenteTrabalho.query.filter_by(obra_id=id, empresa_id=empresa_id).all()
    
    data_inicio_fmt = obra.data_inicio.strftime('%d/%m/%Y') if obra.data_inicio else "-"
    data_inicio_iso = obra.data_inicio.isoformat() if obra.data_inicio else ""
    data_fim_fmt = obra.data_fim.strftime('%d/%m/%Y') if obra.data_fim else "-"
    data_fim_iso = obra.data_fim.isoformat() if obra.data_fim else ""
    nome_responsavel = obra.responsavel.nome if obra.responsavel else "Não definido"

    lista_frentes = []
    for f in frentes:
        nome_resp_frente = f.responsavel.nome if f.responsavel else "Sem responsável"
        id_resp_frente = f.criado_por if f.criado_por else ""
        lista_frentes.append({
            "id": f.id,
            "nome": f.nome,
            "centro_custo": f.centro_custo or "",
        })

    return jsonify({
        "data_inicio": data_inicio_fmt,
        "data_inicio_iso": data_inicio_iso,
        "data_fim": data_fim_fmt,
        "data_fim_iso": data_fim_iso,
        "horario_entrada": obra.hora_entrada_padrao.strftime('%H:%M') if obra.hora_entrada_padrao else "",
        "horario_saida": obra.hora_saida_padrao.strftime('%H:%M') if obra.hora_saida_padrao else "",
        "responsavel_id": obra.criado_por,
        "frentes": lista_frentes,
    })


@auth_bp.get("/api/obra/<int:id>/clima")
@login_required
def get_obra_clima_api(id):
    empresa_id = session.get("empresa_id")
    scope_ids = get_user_scope_ids()
    if scope_ids is not None and id not in scope_ids:
        return jsonify({"error": "Acesso não autorizado a esta obra"}), 403

    obra = Obra.query.filter_by(id=id, empresa_id=empresa_id).first_or_404()
    data_str = request.args.get("data")
    try:
        data_referencia = datetime.strptime(data_str, "%Y-%m-%d").date() if data_str else date.today()
    except ValueError:
        return jsonify({"error": "Data inválida. Use o formato YYYY-MM-DD."}), 400

    climas_disponiveis = AuxClima.query.filter_by(ativo=True).order_by(AuxClima.nome.asc()).all()

    try:
        payload = _build_clima_automatico_payload(obra, data_referencia, climas_disponiveis)
        payload["obra"] = {"nome": obra.nome}
        payload["data"] = data_referencia.isoformat()
        payload["matched"] = bool(payload["manha"]["id"] or payload["tarde"]["id"])
        return jsonify(payload)
    except (URLError, HTTPError, TimeoutError, ValueError) as exc:
        current_app.logger.warning(f"Falha ao consultar clima automático da obra {id}: {exc}")
        return jsonify({"error": str(exc)}), 502

@auth_bp.get("/api/frente/<int:id>")
@login_required
def get_frente_api(id):
    # SECURITY: Validação básica + escopo por empresa
    empresa_id = session.get("empresa_id")
    frente = FrenteTrabalho.query.filter_by(id=id, empresa_id=empresa_id).first_or_404()
    # Verifica scope da obra pai da frente
    scope_ids = get_user_scope_ids()
    if scope_ids is not None and frente.obra_id not in scope_ids:
        return jsonify({"error": "Forbidden"}), 403

    return jsonify({
        "nome": frente.nome,
        "centro_custo": frente.centro_custo or ""
    })

@auth_bp.post("/gerar-rdo")
@login_required
@permission_required('rdo.update')
def gerar_rdo():
    try:
        sp_tz = timezone(timedelta(hours=-3))
        now_br = datetime.now(sp_tz).replace(tzinfo=None)
        current_user_id = session.get("user_id")

        form = RdoForm()
        if not form.validate_on_submit():
            for field_errors in form.errors.values():
                for error in field_errors:
                    flash(error, "danger")
            return redirect(request.referrer or url_for('auth.criar_rdo'))

        # Helpers
        def _get_int(key):
            v = request.form.get(key)
            return int(v) if v and v.isdigit() else None
        
        def _get_time(key):
            v = request.form.get(key)
            if not v: return None
            try: return datetime.strptime(v, '%H:%M').time()
            except: return None
            
        def _get_float(key):
            v = request.form.get(key)
            if not v: return None
            try: return float(v.replace(',', '.'))
            except: return None

        def _get_float_from_list(values, index):
            if index >= len(values) or not values[index]:
                return None
            try:
                return float(values[index].replace(',', '.'))
            except Exception:
                return None

        rdo_id_original = _get_int("rdo_id")
        obra_id = _get_int("obra_id")

        # SECURITY: Validação de Escopo (Data Scoping)
        # Verifica se o usuário tem permissão na Obra alvo
        scope_ids = get_user_scope_ids()
        if scope_ids is not None:
            if obra_id not in scope_ids:
                flash("Você não tem permissão para criar/editar RDO nesta obra.", "danger")
                abort(403)

        # SECURITY: Se for edição, verifica status e permissões extras
        if rdo_id_original:
            empresa_id = session.get('empresa_id')
            item_rdo = RDO.query.filter_by(id=rdo_id_original, empresa_id=empresa_id).first()
            if not item_rdo:
                abort(404)
            
            # Se já aprovado, apenas Admin/Gestor podem revisar (Operador não revisa aprovado, cria novo geralmente)
            if item_rdo.status == 'APROVADO' and session.get("user_role") == ROLE_OPERADOR:
                 flash("Operadores não podem alterar RDOs já aprovados. Solicite ao Gestor.", "danger")
                 return redirect(url_for('auth.visualizar_rdo', rdo_id=rdo_id_original))

            # UPDATE (EDIÇÃO / NOVA REVISÃO)
            item_rdo.status = 'PENDENTE'

            # Reset workflow
            assinaturas_existentes = RDOAprovacao.query.filter_by(rdo_id=item_rdo.id).all()
            for ass in assinaturas_existentes:
                ass.imagem_assinatura = None
                ass.comentario = None
                ass.status = 'PENDENTE'
                ass.data_aprovacao = None
                ass.endereco_ip = None
                ass.hash = None

        else:
            # INSERT (NOVO RDO)
            item_rdo = RDO(
                empresa_id=session.get('empresa_id'),
                obra_id=obra_id,
            )
            item_rdo.criado_por = current_user_id
            item_rdo.status = 'PENDENTE'

        # Popular campos comuns
        item_rdo.frente_trabalho_id = _get_int("frente_trabalho_id")
        item_rdo.clima_manha_id = _get_int("climas_manha")
        item_rdo.clima_tarde_id = _get_int("climas_tarde")
        data_rdo_str = request.form.get("data_rdo")
        item_rdo.data_rdo = datetime.strptime(data_rdo_str, '%Y-%m-%d').date() if data_rdo_str else date.today()
        item_rdo.modificado_por = current_user_id
        item_rdo.observacoes = request.form.get("comentarios_gerais")
        item_rdo.hora_entrada = _get_time("hora_entrada")
        item_rdo.hora_saida = _get_time("hora_saida")
        item_rdo.intervalo_entrada = _get_time("intervalo_entrada")
        item_rdo.intervalo_saida = _get_time("intervalo_saida")
        
        if not rdo_id_original:
            db.session.add(item_rdo)
        
        db.session.flush()

        # [Criação] Assinatura do criador
        if not rdo_id_original:
            empresa_id = session.get('empresa_id')
            obra_rdo = Obra.query.filter_by(id=obra_id, empresa_id=empresa_id).first() if obra_id else None
            aprovador_padrao_id = obra_rdo.criado_por if obra_rdo and obra_rdo.criado_por else current_user_id
            existe_ass = RDOAprovacao.query.filter_by(rdo_id=item_rdo.id, aprovador_id=aprovador_padrao_id).first()
            if not existe_ass:
                assinatura_criador = RDOAprovacao(
                    empresa_id=session.get('empresa_id'),
                    rdo_id=item_rdo.id,
                    aprovador_id=aprovador_padrao_id,
                    nivel=1,
                    status='PENDENTE',
                    ativo=True
                )
                db.session.add(assinatura_criador)

        # Limpeza de filhos para recriação
        if rdo_id_original:
            # Soft delete dos filhos (não usar delete físico)
            for _a in RDOAtividade.query.filter_by(rdo_id=item_rdo.id, ativo=True).all():
                _a.soft_delete(usuario=current_user, motivo="recriação RDO")
            for _m in RDOMaoObra.query.filter_by(rdo_id=item_rdo.id, ativo=True).all():
                _m.soft_delete(usuario=current_user, motivo="recriação RDO")
            for _e in RDOEquipamento.query.filter_by(rdo_id=item_rdo.id, ativo=True).all():
                _e.soft_delete(usuario=current_user, motivo="recriação RDO")
            for _o in RDOOcorrencia.query.filter_by(rdo_id=item_rdo.id, ativo=True).all():
                _o.soft_delete(usuario=current_user, motivo="recriação RDO")


        # 1. Atividades
        descricoes = request.form.getlist("atividade_descricao[]")
        status_list = request.form.getlist("atividade_status[]")
        for i, desc in enumerate(descricoes):
            if desc and desc.strip():
                st = status_list[i] if i < len(status_list) else "Não iniciada"
                db.session.add(RDOAtividade(
                    empresa_id=session.get('empresa_id'),
                    rdo_id=item_rdo.id,
                    descricao=desc,
                    status=st,
                    ativo=True,
                ))

        mo_colaborador_ids = request.form.getlist("mo_colaborador_id[]")
        mo_funcoes = request.form.getlist("mo_funcao[]")
        mo_horas = request.form.getlist("mo_horas[]")
        mo_tipos = request.form.getlist("mo_tipo[]")
        for i, col_id in enumerate(mo_colaborador_ids):
            if col_id and col_id.isdigit():
                db.session.add(
                    RDOMaoObra(
                        empresa_id=session.get('empresa_id'),
                        rdo_id=item_rdo.id,
                        colaborador_id=int(col_id),
                        funcao=mo_funcoes[i] if i < len(mo_funcoes) else None,
                        quantidade_horas=_get_float_from_list(mo_horas, i),
                        tipo_mao_obra=mo_tipos[i] if i < len(mo_tipos) else 'PROPRIA',
                        ativo=True
                    )
                )

        # 3. Equipamentos
        eq_ids = request.form.getlist("eq_id[]")
        eq_qts = request.form.getlist("eq_qtd[]")
        eq_status_list = request.form.getlist("eq_status[]")
        for i, eid in enumerate(eq_ids):
            if eid and eid.isdigit():
                qtd = int(eq_qts[i]) if i < len(eq_qts) and eq_qts[i] else 0
                eq_status = eq_status_list[i] if i < len(eq_status_list) else 'OPERANDO'
                db.session.add(RDOEquipamento(
                    empresa_id=session.get('empresa_id'),
                    rdo_id=item_rdo.id,
                    equipamento_id=int(eid),
                    quantidade=qtd,
                    status=eq_status,
                    ativo=True
                ))

        # 4. Ocorrências
        oc_tags = request.form.getlist("oc_tag[]")
        oc_descs = request.form.getlist("oc_desc[]")
        oc_impactos = request.form.getlist("oc_impacto[]")
        oc_tempos = request.form.getlist("oc_tempo_parado[]")
        for i, tid in enumerate(oc_tags):
            if not tid: continue
            tempo_par = None
            tempo_str = oc_tempos[i] if i < len(oc_tempos) else None
            if tempo_str and tempo_str.strip():
                try: tempo_par = float(tempo_str.replace(',','.'))
                except ValueError: tempo_par = None
            desc = oc_descs[i] if i < len(oc_descs) else ""
            impacto = oc_impactos[i] if i < len(oc_impactos) else None
            db.session.add(RDOOcorrencia(
                empresa_id=session.get('empresa_id'),
                rdo_id=item_rdo.id,
                tipo_ocorrencia=int(tid) if tid.isdigit() else None,
                descricao=desc,
                impacto=impacto,
                tempo_paralisacao=tempo_par,
                ativo=True
            ))

        # 5. Fotos
        UPLOAD_FOLDER = os.path.join(current_app.root_path, 'static', 'uploads', 'rdo')
        if not os.path.exists(UPLOAD_FOLDER): os.makedirs(UPLOAD_FOLDER)
            
        ids_remover = request.form.getlist("fotos_remover[]")
        if ids_remover:
            for id_rem in ids_remover:
                try:
                    if not id_rem: continue
                    foto_del = RDOFoto.query.get(int(id_rem))
                    if foto_del and foto_del.rdo_id == item_rdo.id:
                        try:
                            caminho_arquivo = os.path.join(UPLOAD_FOLDER, foto_del.arquivo)
                            if os.path.exists(caminho_arquivo): os.remove(caminho_arquivo)
                        except Exception: pass
                        # Soft delete da foto
                        foto_del.soft_delete(usuario=current_user, motivo="remover foto")

                except Exception: pass
            
        ids_existentes = request.form.getlist("fotos_existentes_ids[]")
        comentarios_existentes = request.form.getlist("comentarios_existentes_list[]")
        for foto_id_str, nova_legenda in zip(ids_existentes, comentarios_existentes):
            try:
                if not foto_id_str: continue
                foto_id = int(foto_id_str)
                foto_obj = RDOFoto.query.get(foto_id)
                if foto_obj and foto_obj.rdo_id == item_rdo.id:
                    if foto_obj.comentario != nova_legenda:
                        foto_obj.comentario = nova_legenda
                        db.session.add(foto_obj)
            except Exception: pass

        arquivos = request.files.getlist("fotos[]")
        legendas = request.form.getlist("novas_fotos_comentarios[]")
        idx_file = 0
        for arquivo in arquivos:
            if arquivo and arquivo.filename:
                fname = secure_filename(arquivo.filename)
                ext = os.path.splitext(fname)[1].lower()
                if ext in ['.jpg', '.jpeg', '.png', '.webp']:
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S%f')
                    novo_nome = f"{timestamp}_{idx_file}{ext}"
                    caminho_salvar = os.path.join(UPLOAD_FOLDER, novo_nome)

                    try:
                        img = Image.open(arquivo)
                        if img.mode in ("RGBA", "P"):
                            img = img.convert("RGB")
                        img.thumbnail((1920, 1080), Image.LANCZOS)
                        img.save(caminho_salvar, optimize=True, quality=75)
                    except Exception:
                        arquivo.stream.seek(0)
                        arquivo.save(caminho_salvar)

                    comentario = legendas[idx_file] if idx_file < len(legendas) else ""
                    db.session.add(RDOFoto(
                        empresa_id=session.get('empresa_id'),
                        rdo_id=item_rdo.id,
                        arquivo=novo_nome,
                        comentario=comentario,
                        ativo=True,
                    ))
                    idx_file += 1

        db.session.commit()
        msg_acao = "revisado" if rdo_id_original else "salvo"
        flash(f"RDO #{item_rdo.id} {msg_acao} com sucesso!", "success")
        return redirect(url_for('auth.visualizar_rdo', rdo_id=item_rdo.id))

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erro ao gerar RDO: {e}")
        import traceback
        traceback.print_exc()
        flash(f"Erro ao salvar RDO: {str(e)}", "danger")
        return redirect(request.referrer)
    
@auth_bp.get("/visualizar-rdo/<int:rdo_id>")
@login_required
def visualizar_rdo(rdo_id):
    empresa_id = session.get("empresa_id")
    item = RDO.query.filter_by(id=rdo_id, empresa_id=empresa_id, ativo=True).first_or_404()

    # SECURITY: Verifica permissão na obra para leitura
    scope_ids = get_user_scope_ids()
    if scope_ids is not None and item.obra_id not in scope_ids:
        flash("Você não tem permissão para visualizar este RDO.", "danger")
        return redirect(url_for("auth.inicio"))

    selected_equip_ids = [eq.equipamento_id for eq in item.equipamentos if eq.equipamento_id]
    selected_tag_ids = [oc.tipo_ocorrencia for oc in item.ocorrencias if oc.tipo_ocorrencia]
    selected_clima_ids = [cid for cid in [item.clima_manha_id, item.clima_tarde_id] if cid]

    mao_de_obra_options = [{"id": m.id, "nome": m.descricao, "tipo": m.tipo} for m in AuxFuncoes.query.filter_by(ativo=True).order_by(AuxFuncoes.descricao.asc()).all()]
    equipamentos_options = [{"id": e.id, "nome": e.descricao} for e in AuxEquipamentos.query.filter(
        or_(AuxEquipamentos.ativo == True, AuxEquipamentos.id.in_(selected_equip_ids))
    ).order_by(AuxEquipamentos.descricao.asc()).all()]
    tags_options = [{"id": t.id, "nome": t.descricao} for t in AuxTagOcorrencia.query.filter(
        or_(AuxTagOcorrencia.ativo == True, AuxTagOcorrencia.id.in_(selected_tag_ids))
    ).order_by(AuxTagOcorrencia.descricao.asc()).all()]
    clima = AuxClima.query.filter(
        or_(AuxClima.ativo == True, AuxClima.id.in_(selected_clima_ids))
    ).order_by(AuxClima.nome.asc()).all()
    assinaturas = RDOAprovacao.query.filter_by(rdo_id=rdo_id, ativo=True).order_by(RDOAprovacao.nivel).all()
    usuarios_obra = Usuario.query.filter_by(
        empresa_id=session.get('empresa_id'), ativo=True
    ).all()
    
    ass_valida = RDOAprovacao.query.filter_by(rdo_id=rdo_id, status='APROVADO').order_by(RDOAprovacao.nivel.desc()).first()
    if ass_valida and ass_valida.hash:
        url_validacao = url_for('auth.validar_documento_publico', h=ass_valida.hash, _external=True)
    else:
        url_validacao = url_for('auth.visualizar_rdo', rdo_id=rdo_id, _external=True)

    qr_code_img = gerar_qrcode_b64(url_validacao)

    return render_template(
        "form_rdo.html",
        item=item,
        view_mode=True,
        obras=Obra.query.filter_by(empresa_id=empresa_id, ativo=True).all(),
        clima=AuxClima.query.filter_by(ativo=True).order_by(AuxClima.nome.asc()).all(),
        frente_trabalho=FrenteTrabalho.query.filter_by(empresa_id=session.get('empresa_id')).all(),
        equipamentos=AuxEquipamentos.query.filter_by(ativo=True).all(),
        assinaturas=assinaturas,
        mao_obra=RDOMaoObra.query.all(),
        usuarios=Usuario.query.filter_by(empresa_id=empresa_id, ativo=True).all(),
        usuarios_obra=usuarios_obra,
        mao_de_obra_options=mao_de_obra_options,
        equipamentos_options=equipamentos_options,
        tags_options=tags_options,
        qr_code_b64=qr_code_img
    )

@auth_bp.get("/editar-rdo/<int:rdo_id>")
@login_required
@permission_required('rdo.update')
def editar_rdo(rdo_id):
    empresa_id = session.get("empresa_id")
    item = RDO.query.filter_by(id=rdo_id, empresa_id=empresa_id, ativo=True).first_or_404()

    # SECURITY: Verifica se usuario tem acesso à obra deste RDO
    scope_ids = get_user_scope_ids()
    if scope_ids is not None and item.obra_id not in scope_ids:
        abort(403)

    usuarios_obra = Usuario.query.filter_by(
        empresa_id=session.get('empresa_id'), ativo=True
    ).all()
    assinaturas_realizadas = RDOAprovacao.query.filter_by(rdo_id=rdo_id).all()
    ids_usuarios_que_assinaram = [a.aprovador_id for a in assinaturas_realizadas]

    lista_assinaturas_status = []
    for u in usuarios_obra:
        ass_obj = next((a for a in assinaturas_realizadas if a.aprovador_id == u.id), None)
        if u.id == item.criado_por or u.id in ids_usuarios_que_assinaram or (u.papeis and any(p.nome in [ROLE_ADMIN, ROLE_GESTOR] for p in u.papeis)):
            lista_assinaturas_status.append({
                "usuario": u,
                "assinado": True if ass_obj else False,
                "dados_assinatura": ass_obj
            })

    maos_obra_salvas = item.maos_obra.all()
    equipamentos_salvos = item.equipamentos.all()
    atividades_salvas = item.atividades.all()
    ocorrencias_salvas = item.ocorrencias.all()
    fotos_salvas = item.fotos.all()
    frente_trabalho=FrenteTrabalho.query.all()

    return render_template(
        "form_rdo.html",
        item=item,
        view_mode=False,
        obras=Obra.query.filter_by(empresa_id=session.get('empresa_id'), ativo=True).all(),
        frente_trabalho=frente_trabalho,
        clima=AuxClima.query.filter(
            or_(AuxClima.ativo == True, AuxClima.id.in_([cid for cid in [item.clima_manha_id, item.clima_tarde_id] if cid]))
        ).order_by(AuxClima.nome.asc()).all(),
        maos_obra_salvas=maos_obra_salvas,
        equipamentos_salvos=equipamentos_salvos,
        atividades_salvas=atividades_salvas,
        ocorrencias_salvas=ocorrencias_salvas,
        fotos_salvas=fotos_salvas,
        mao_de_obra_options=[{"id": m.id, "nome": m.nome, "tipo": m.tipo} for m in AuxFuncoes.query.filter_by(ativo=True).order_by(AuxFuncoes.nome.asc()).all()],
        equipamentos_options=[{"id": e.id, "nome": e.descricao} for e in AuxEquipamentos.query.filter(
            or_(AuxEquipamentos.ativo == True, AuxEquipamentos.id.in_([eq.equipamento_id for eq in equipamentos_salvos if eq.equipamento_id]))
        ).order_by(AuxEquipamentos.descricao.asc()).all()],
        tags_options=[{"id": t.id, "nome": t.descricao} for t in AuxTagOcorrencia.query.filter(
            or_(AuxTagOcorrencia.ativo == True, AuxTagOcorrencia.id.in_([oc.tipo_ocorrencia for oc in ocorrencias_salvas if oc.tipo_ocorrencia]))
        ).order_by(AuxTagOcorrencia.descricao.asc()).all()],
        usuarios_obra=usuarios_obra,
        lista_assinaturas_status=lista_assinaturas_status,
        assinaturas=assinaturas_realizadas
    )

@auth_bp.post("/excluir-rdo/<int:rdo_id>")
@login_required
@permission_required('rdo.approve')
def excluir_rdo(rdo_id):
    try:
        empresa_id = session.get("empresa_id")
        item_rdo = RDO.query.filter_by(id=rdo_id, empresa_id=empresa_id).first_or_404()
        
        # SECURITY: Scoping Check
        scope_ids = get_user_scope_ids()
        if scope_ids is not None and item_rdo.obra_id not in scope_ids:
            abort(403)

        with db.session.begin():
            # Exclusão lógica em transação
            item_rdo.soft_delete(usuario=current_user, motivo="exclusão RDO")


        flash(f"RDO #{item_rdo.id} enviado para lixeira com sucesso!", "success")
        return redirect(url_for('auth.inicio'))
    except Exception as e:
        db.session.rollback()
        flash(f"Ocorreu um erro ao excluir o RDO: {str(e)}", "danger")
        return redirect(url_for('auth.inicio'))

@auth_bp.get("/lista-rdo")
@login_required
def lista_rdo():
    empresa_id = session.get("empresa_id")
    current_user_id = session.get("user_id")
    user = Usuario.query.get(current_user_id)

    # SCOPING: Filtra RDOs ativos da empresa atual
    if user:
        if user.papel == ROLE_ADMIN:
             rdos = RDO.query.filter_by(ativo=True, empresa_id=empresa_id).order_by(RDO.data_rdo.desc()).all()
        else:
            ids_obras_permitidas = [obra.id for obra in user.obras_permitidas]
            rdos = RDO.query.filter(
                RDO.obra_id.in_(ids_obras_permitidas),
                RDO.ativo == True,
                RDO.empresa_id == empresa_id
            ).order_by(RDO.data_rdo.desc()).all()
    else:
        rdos = []
    
    lista_pendencias = RDOAprovacao.query.filter_by(
        aprovador_id=current_user_id, 
        status='PENDENTE',
        ativo=True
    ).all()
    
    minhas_pendencias = RDOAprovacao.query.filter_by(
        aprovador_id=current_user_id,
        status='PENDENTE',
        ativo=True
    ).count()

    return render_template("list_rdo.html", rdos=rdos, count_minhas_pendencias=minhas_pendencias, lista_pendencias=lista_pendencias)
