from app.routes.auth_common import *

#######################################################################################################
####################################################################################################### Assinaturas RDO
#######################################################################################################

@auth_bp.route("/assinar-rdo/<int:rdo_id>/salvar-workflow", methods=["POST"])
@login_required
@role_required(PERM_MANAGEMENT) # Apenas Gestor/Admin define fluxo
def salvar_workflow_assinaturas(rdo_id):
    rdo = RDO.query.filter_by(id=rdo_id, ativo=True).first_or_404()
    
    # Scoping
    scope_ids = get_user_scope_ids()
    if scope_ids is not None and rdo.obra_id not in scope_ids:
        return jsonify({"success": False, "message": "Sem permissão na obra."}), 403
    
    if rdo.status in ['APROVADO', 'REJEITADO']:
         return jsonify({"success": False, "message": "RDO finalizado, não é possível alterar aprovadores."}), 403

    data = request.get_json()
    novos_assinantes_ids = [int(uid) for uid in data.get('usuarios_ids', [])] 
    
    owner_id = rdo.obra.criado_por if rdo.obra and rdo.obra.criado_por else rdo.id_criado_por
    if owner_id in novos_assinantes_ids:
        novos_assinantes_ids.remove(owner_id)
    if owner_id:
        novos_assinantes_ids.insert(0, owner_id)

    try:
        with db.session.begin():
            # Soft delete das assinaturas atuais
            for ass in RDOAprovacao.query.filter_by(rdo_id=rdo_id, ativo=True).all():
                ass.soft_delete(usuario=current_user, motivo="alteração de workflow")

            for index, user_id in enumerate(novos_assinantes_ids):
                nova_ass = RDOAprovacao(
                    empresa_id=session.get('empresa_id'),
                    rdo_id=rdo_id,
                    aprovador_id=user_id,
                    nivel=index + 1,
                    status='PENDENTE',
                    ativo=True
                )
                db.session.add(nova_ass)

            rdo.status = 'PENDENTE'
            return jsonify({"success": True})
        

        
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500

@auth_bp.route("/assinar-rdo/<int:rdo_id>/aprovar-rdo", methods=["POST"])
@login_required
@role_required(PERM_SIGNATURE) # Todos (exceto Leitor) podem assinar se estiverem no fluxo
def assinar_rdo(rdo_id):
    user_id = session.get("user_id")
    rdo = RDO.query.filter_by(id=rdo_id, ativo=True).first_or_404()

    # Scoping check: Tem que ter acesso à obra pra assinar
    scope_ids = get_user_scope_ids()
    if scope_ids is not None and rdo.obra_id not in scope_ids:
         return jsonify({"success": False, "message": "Sem permissão na obra."}), 403

    assinatura_pendente = RDOAprovacao.query.filter_by(
        rdo_id=rdo_id, 
        aprovador_id=user_id, 
        status='PENDENTE',
        ativo=True
    ).first()

    if not assinatura_pendente:
        return jsonify({"success": False, "message": "Você não tem assinaturas pendentes para este RDO."}), 400

    passo_anterior_pendente = RDOAprovacao.query.filter(
        RDOAprovacao.rdo_id == rdo_id,
        RDOAprovacao.nivel < assinatura_pendente.nivel,
        RDOAprovacao.status != 'APROVADO',
        RDOAprovacao.ativo == True
    ).count()

    if passo_anterior_pendente > 0:
        return jsonify({"success": False, "message": "Aguarde a aprovação do responsável anterior."}), 403

    dados = request.get_json()
    img_data = dados.get('assinatura_b64')
    latitude = dados.get('latitude')
    longitude = dados.get('longitude')
    
    if not img_data:
        return jsonify({"success": False, "message": "Imagem da assinatura não fornecida."}), 400

    try:
        header, encoded = img_data.split(",", 1)
        file_data = base64.b64decode(encoded)
        filename = f"sig_{rdo_id}_{user_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
        
        upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'assinaturas')
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)
            
        with open(os.path.join(upload_folder, filename), "wb") as f:
            f.write(file_data)

        user_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        if user_ip and ',' in user_ip:
            user_ip = user_ip.split(',')[0].strip()

        hash_string = f"{rdo_id}:{user_id}:{datetime.utcnow()}:{current_app.config['SECRET_KEY']}"
        document_hash = hashlib.sha256(hash_string.encode()).hexdigest()

        assinatura_pendente.imagem_assinatura = filename
        assinatura_pendente.data_aprovacao = datetime.now()
        assinatura_pendente.status = 'APROVADO'
        assinatura_pendente.endereco_ip = user_ip
        # RDOAprovacao não possui latitude e longitude
        # assinatura_pendente.latitude = latitude
        # assinatura_pendente.longitude = longitude
        assinatura_pendente.hash = document_hash 
        
        restantes = RDOAprovacao.query.filter(
            RDOAprovacao.rdo_id == rdo_id,
            RDOAprovacao.status == 'PENDENTE',
            RDOAprovacao.id != assinatura_pendente.id,
            RDOAprovacao.ativo == True
        ).count()
        
        if restantes == 0:
            rdo.status = 'APROVADO'
        else:
            rdo.status = 'PENDENTE'

        db.session.commit()
        return jsonify({"success": True})

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    
@auth_bp.route("/assinar-rdo/<int:id_assinatura>/rejeitar-rdo", methods=["POST"])
@login_required
@role_required(PERM_SIGNATURE)
def rejeitar_assinatura(id_assinatura):
    dados = request.get_json()
    motivo = dados.get('motivo')
    ass = RDOAprovacao.query.get_or_404(id_assinatura)
    
    if ass.aprovador_id != session.get('user_id'):
        return jsonify({"success": False, "message": "Não autorizado."}), 403

    try:
        ass.status = 'REJEITADO'
        ass.comentario = motivo
        ass.data_aprovacao = datetime.now()
        rdo = RDO.query.get(ass.rdo_id)
        rdo.status = 'REJEITADO'
        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    
#######################################################################################################
####################################################################################################### USUARIOS
#######################################################################################################
