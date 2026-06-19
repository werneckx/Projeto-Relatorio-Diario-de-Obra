from app.routes.auth_common import *
from app.services.auditoria_service import AuditoriaService
from app.services.workflow_service import WorkflowService
from app.utils.serializers import safe_model_to_dict

#######################################################################################################
####################################################################################################### Assinaturas RDO
#######################################################################################################


@auth_bp.route("/assinar-rdo/<int:rdo_id>/salvar-workflow", methods=["POST"])
@login_required
@role_required(PERM_MANAGEMENT)  # Apenas Gestor/Admin define fluxo
def salvar_workflow_assinaturas(rdo_id):
    rdo = RDO.query.filter_by(id=rdo_id, ativo=True).first_or_404()

    scope_ids = get_user_scope_ids()
    if scope_ids is not None and rdo.obra_id not in scope_ids:
        return jsonify({"success": False, "message": "Sem permissão na obra."}), 403

    if rdo.status in ['APROVADO', 'REJEITADO']:
        return jsonify({"success": False, "message": "RDO finalizado, não é possível alterar aprovadores."}), 403

    data = request.get_json() or {}
    novos_assinantes_ids = [int(uid) for uid in data.get('usuarios_ids', [])]

    owner_id = rdo.criado_por
    if owner_id in novos_assinantes_ids:
        novos_assinantes_ids.remove(owner_id)
    if owner_id:
        novos_assinantes_ids.insert(0, owner_id)

    try:
        with db.session.begin():
            assinaturas_antes = [
                safe_model_to_dict(ass)
                for ass in RDOAprovacao.query.filter_by(rdo_id=rdo_id, ativo=True).all()
            ]

            novas_assinaturas = WorkflowService.salvar_fluxo_manual(
                rdo_id=rdo_id,
                usuarios_ids=novos_assinantes_ids,
                sobrescrever=True,
            )

            first_approver = next((ass for ass in novas_assinaturas if ass.nivel == 1), None)
            if first_approver:
                from app.models.notificacao import TipoNotificacao
                from app.services.notificacao_service import NotificacaoService

                NotificacaoService.criar_notificacao(
                    empresa_id=session.get('empresa_id'),
                    usuario_id=first_approver.aprovador_id,
                    tipo=TipoNotificacao.APROVACAO_PENDENTE,
                    titulo=f"Aprovação Pendente: RDO #{rdo.numero_sequencial or rdo.id}",
                    mensagem=f"O RDO #{rdo.numero_sequencial or rdo.id} da obra '{rdo.obra.nome}' aguarda sua aprovação.",
                    link=url_for('auth.visualizar_rdo', rdo_id=rdo.id),
                    obra_id=rdo.obra_id,
                    rdo_id=rdo.id,
                    criado_por=session.get('user_id')
                )

            AuditoriaService.registrar_operacao(
                acao="UPDATE_WORKFLOW",
                entidade="RDO_WORKFLOW",
                entidade_id=rdo_id,
                antes=assinaturas_antes,
                depois=[safe_model_to_dict(ass) for ass in novas_assinaturas],
                empresa_id=session.get('empresa_id'),
                usuario_id=session.get('user_id'),
                ip=request.headers.get('X-Forwarded-For', request.remote_addr),
                user_agent=request.headers.get('User-Agent'),
                endpoint=request.endpoint,
                metodo_http=request.method,
                payload={"usuarios_ids": novos_assinantes_ids},
            )

            return jsonify({"success": True})

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500


@auth_bp.route("/assinar-rdo/<int:rdo_id>/aprovar-rdo", methods=["POST"])
@login_required
@role_required(PERM_SIGNATURE)  # Todos (exceto Leitor) podem assinar se estiverem no fluxo
def assinar_rdo(rdo_id):
    user_id = session.get("user_id")
    rdo = RDO.query.filter_by(id=rdo_id, ativo=True).first_or_404()

    scope_ids = get_user_scope_ids()
    if scope_ids is not None and rdo.obra_id not in scope_ids:
        return jsonify({"success": False, "message": "Sem permissão na obra."}), 403

    assinatura_pendente = RDOAprovacao.query.filter_by(
        rdo_id=rdo_id,
        aprovador_id=user_id,
        status='PENDENTE',
        ativo=True,
    ).first()

    if not assinatura_pendente:
        return jsonify({"success": False, "message": "Você não tem assinaturas pendentes para este RDO."}), 400

    antes_assinatura = safe_model_to_dict(assinatura_pendente)

    dados = request.get_json() or {}
    img_data = dados.get('assinatura_b64')
    if not img_data:
        return jsonify({"success": False, "message": "Imagem da assinatura não fornecida."}), 400

    try:
        _, encoded = img_data.split(",", 1)
        file_data = base64.b64decode(encoded)
        now = utcnow_naive()

        filename = f"sig_{rdo_id}_{user_id}_{now.strftime('%Y%m%d%H%M%S')}.png"
        upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'assinaturas')
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)

        with open(os.path.join(upload_folder, filename), "wb") as f:
            f.write(file_data)

        user_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        if user_ip and ',' in user_ip:
            user_ip = user_ip.split(',')[0].strip()

        hash_string = f"{rdo_id}:{user_id}:{now}:{current_app.config['SECRET_KEY']}"
        document_hash = hashlib.sha256(hash_string.encode()).hexdigest()

        sucesso, mensagem = WorkflowService.assinar_etapa(
            aprovacao_id=assinatura_pendente.id,
            assinatura_path=filename,
            ip=user_ip,
            hash_doc=document_hash,
            user_agent=request.headers.get('User-Agent'),
            commit=False,
        )
        if not sucesso:
            raise RuntimeError(mensagem)

        assinatura_pendente = db.session.get(RDOAprovacao, assinatura_pendente.id)
        rdo = db.session.get(RDO, rdo_id)
        restantes = RDOAprovacao.query.filter(
            RDOAprovacao.rdo_id == rdo_id,
            RDOAprovacao.status == 'PENDENTE',
            RDOAprovacao.ativo == True,
        ).count()

        if rdo and rdo.status == 'APROVADO':
            if rdo.criado_por:
                from app.models.notificacao import TipoNotificacao
                from app.services.notificacao_service import NotificacaoService

                NotificacaoService.criar_notificacao(
                    empresa_id=session.get('empresa_id'),
                    usuario_id=rdo.criado_por,
                    tipo=TipoNotificacao.RDO_APROVADO,
                    titulo=f"RDO #{rdo.numero_sequencial or rdo.id} Aprovado",
                    mensagem=f"O RDO #{rdo.numero_sequencial or rdo.id} da obra '{rdo.obra.nome}' foi totalmente aprovado.",
                    link=url_for('auth.visualizar_rdo', rdo_id=rdo.id),
                    obra_id=rdo.obra_id,
                    rdo_id=rdo.id,
                    criado_por=session.get('user_id')
                )
        else:
            next_approver = RDOAprovacao.query.filter_by(
                rdo_id=rdo_id,
                status='PENDENTE',
                ativo=True,
            ).order_by(RDOAprovacao.nivel).first()
            if next_approver:
                from app.models.notificacao import TipoNotificacao
                from app.services.notificacao_service import NotificacaoService

                NotificacaoService.criar_notificacao(
                    empresa_id=session.get('empresa_id'),
                    usuario_id=next_approver.aprovador_id,
                    tipo=TipoNotificacao.APROVACAO_PENDENTE,
                    titulo=f"Aprovação Pendente: RDO #{rdo.numero_sequencial or rdo.id}",
                    mensagem=f"O RDO #{rdo.numero_sequencial or rdo.id} da obra '{rdo.obra.nome}' aguarda sua aprovação.",
                    link=url_for('auth.visualizar_rdo', rdo_id=rdo.id),
                    obra_id=rdo.obra_id,
                    rdo_id=rdo.id,
                    criado_por=session.get('user_id')
                )

        depois_assinatura = safe_model_to_dict(assinatura_pendente)
        AuditoriaService.registrar_operacao(
            acao="APPROVE",
            entidade="RDO_APROVACAO",
            entidade_id=assinatura_pendente.id,
            antes=antes_assinatura,
            depois=depois_assinatura,
            empresa_id=session.get('empresa_id'),
            usuario_id=session.get('user_id'),
            ip=user_ip,
            user_agent=request.headers.get('User-Agent'),
            endpoint=request.endpoint,
            metodo_http=request.method,
            payload={"rdo_id": rdo_id, "restantes": restantes, "novo_status_rdo": (rdo.status if rdo else None)},
        )

        db.session.commit()
        return jsonify({"success": True})

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500


@auth_bp.route("/assinar-rdo/<int:id_assinatura>/rejeitar-rdo", methods=["POST"])
@login_required
@role_required(PERM_SIGNATURE)
def rejeitar_assinatura(id_assinatura):
    dados = request.get_json() or {}
    motivo = dados.get('motivo')

    ass = db.session.get(RDOAprovacao, id_assinatura)
    if not ass or not ass.ativo:
        abort(404)

    if ass.aprovador_id != session.get('user_id'):
        return jsonify({"success": False, "message": "Não autorizado."}), 403

    try:
        antes_assinatura = safe_model_to_dict(ass)

        sucesso, mensagem = WorkflowService.rejeitar_etapa(
            aprovacao_id=ass.id,
            motivo=motivo,
            ip=request.headers.get('X-Forwarded-For', request.remote_addr),
            reabrir=False,
            commit=False,
        )
        if not sucesso:
            raise RuntimeError(mensagem)

        ass = db.session.get(RDOAprovacao, ass.id)
        rdo = db.session.get(RDO, ass.rdo_id)
        if rdo and rdo.criado_por:
            from app.models.notificacao import TipoNotificacao
            from app.services.notificacao_service import NotificacaoService

            NotificacaoService.criar_notificacao(
                empresa_id=session.get('empresa_id'),
                usuario_id=rdo.criado_por,
                tipo=TipoNotificacao.REJEICAO,
                titulo=f"RDO #{rdo.numero_sequencial or rdo.id} Rejeitado",
                mensagem=f"O RDO #{rdo.numero_sequencial or rdo.id} da obra '{rdo.obra.nome}' foi rejeitado por {current_user.nome}. Motivo: {motivo}",
                link=url_for('auth.editar_rdo', rdo_id=rdo.id),
                obra_id=rdo.obra_id,
                rdo_id=rdo.id,
                criado_por=session.get('user_id')
            )

        depois_assinatura = safe_model_to_dict(ass)
        AuditoriaService.registrar_operacao(
            acao="REJECT",
            entidade="RDO_APROVACAO",
            entidade_id=ass.id,
            antes=antes_assinatura,
            depois=depois_assinatura,
            empresa_id=session.get('empresa_id'),
            usuario_id=session.get('user_id'),
            ip=request.headers.get('X-Forwarded-For', request.remote_addr),
            user_agent=request.headers.get('User-Agent'),
            endpoint=request.endpoint,
            metodo_http=request.method,
            payload={"rdo_id": ass.rdo_id, "motivo": motivo},
        )

        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500


#######################################################################################################
####################################################################################################### USUARIOS
#######################################################################################################
