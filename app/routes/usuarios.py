from app.routes.auth_common import *


def _colaboradores_disponiveis_para_usuario(empresa_id, usuario=None):
    usuario_id = getattr(usuario, "id", None)
    colaborador_atual_id = getattr(usuario, "colaborador_id", None)

    usados_query = db.session.query(Usuario.colaborador_id).filter(
        Usuario.empresa_id == empresa_id,
        Usuario.colaborador_id.isnot(None),
    )
    if usuario_id:
        usados_query = usados_query.filter(Usuario.id != usuario_id)

    usados_ids = [cid for (cid,) in usados_query.all() if cid]

    query = Colaborador.query.filter(Colaborador.empresa_id == empresa_id)
    if colaborador_atual_id:
        query = query.filter(or_(Colaborador.ativo.is_(True), Colaborador.id == colaborador_atual_id))
    else:
        query = query.filter(Colaborador.ativo.is_(True))
    if usados_ids:
        query = query.filter(~Colaborador.id.in_(usados_ids))

    return query.order_by(Colaborador.nome.asc()).all()


def _resolver_papel_usuario(nome_papel, empresa_id):
    papel_norm = (nome_papel or ROLE_LEITOR).strip().upper()
    papeis = (
        Papel.query
        .filter(
            Papel.ativo.is_(True),
            func.upper(func.trim(Papel.nome)) == papel_norm,
            or_(Papel.empresa_id == empresa_id, Papel.empresa_id.is_(None)),
        )
        .all()
    )
    if not papeis:
        return None
    return next((papel for papel in papeis if papel.empresa_id == empresa_id), papeis[0])


def _sincronizar_papel_usuario(usuario, nome_papel, empresa_id):
    papel = _resolver_papel_usuario(nome_papel, empresa_id)
    if not papel:
        raise ValueError(f"Papel {nome_papel or ROLE_LEITOR} nÃ£o encontrado.")

    db.session.query(UsuarioPapel).filter(
        UsuarioPapel.usuario_id == usuario.id,
        UsuarioPapel.empresa_id == empresa_id,
    ).delete(synchronize_session=False)
    db.session.add(UsuarioPapel(
        empresa_id=empresa_id,
        usuario_id=usuario.id,
        papel_id=papel.id,
        ativo=True,
    ))
    return papel

@auth_bp.get("/lista-usuarios")
@auth_bp.get("/usuarios")
@login_required
@permission_required('usuario.manage')
def lista_usuarios():
    # SCOPING: Gestor/Operador só veem usuários da empresa atual (e, na prática, das suas obras)
    empresa_id = session.get('empresa_id')
    query = Usuario.query.filter_by(empresa_id=empresa_id)

    current_user_obj = Usuario.query.get(session.get("user_id"))
    if not (current_user_obj and current_user_obj.is_admin):
        ids_permitidos = [o.id for o in Obra.query.filter_by(empresa_id=empresa_id).all()]
        query = query.filter(Usuario.obras_permitidas.any(Obra.id.in_(ids_permitidos)))

    usuarios = query.order_by(Usuario.id.asc()).all()

    return render_template("cadastros/usuarios/list_usuarios.html", opcoes=usuarios, categoria="usuario")

@auth_bp.get("/criar-usuario")
@auth_bp.get("/usuarios/novo")
@login_required
@permission_required('usuario.manage')
def criar_usuario():
    empresa_id = session.get('empresa_id')
    colaborador_id = request.args.get("colaborador_id")
    if colaborador_id:
        colaborador = Colaborador.query.filter_by(id=colaborador_id, empresa_id=empresa_id).first()
        if colaborador:
            return redirect(url_for('auth.editar_colaborador', id=colaborador.id))
    return redirect(url_for('auth.criar_colaborador'))

@auth_bp.post("/gerar-usuario")
@auth_bp.post("/usuarios/salvar")
@login_required
@permission_required('usuario.manage')
def gerar_usuario():
    flash("Gerenciamento de usuarios foi centralizado no cadastro de colaboradores.", "warning")
    return redirect(url_for('auth.criar_colaborador'))

    categoria = request.form.get("categoria")
    user_id = request.form.get("id")
    empresa_id = session.get('empresa_id')
    current_user_obj = Usuario.query.get(session.get("user_id"))
    audit_user_id = get_current_user_id()
    
    # SCOPING: Para reload do template em caso de erro
    if current_user_obj.is_admin:
        obras_ativas = Obra.query.filter_by(empresa_id=empresa_id, status=1).order_by(Obra.nome).all()
    else:
        obras_ativas = [o for o in current_user_obj.obras_permitidas if o.status == 1 and o.empresa_id == empresa_id]

    if categoria == "usuario":
        email = request.form.get("email")
        papel = request.form.get("papel")
        senha = request.form.get("senha")
        status_raw = (request.form.get("status") or "").strip().lower()
        status = status_raw in {"1", "true", "on", "ativo"}
        obras_ids = request.form.getlist("obras_permitidas")
        colaborador_id_raw = (request.form.get("colaborador_id") or "").strip()

        # SECURITY: Gestor não pode criar Admin
        papel_norm = (papel or "").strip().upper()
        item_form = {
            'id': user_id,
            'email': email,
            'papel': papel,
            'colaborador_id': colaborador_id_raw,
            'status': status,
        }

        user = Usuario.query.filter_by(id=user_id, empresa_id=empresa_id).first() if user_id else None
        colaboradores_disponiveis = _colaboradores_disponiveis_para_usuario(empresa_id, usuario=user)

        if (current_user_obj.papel or "").strip().upper() == ROLE_GESTOR and papel_norm == ROLE_ADMIN:
            flash("Gestores não podem criar usuários Administradores.", "danger")
            return render_template("cadastros/colaboradores/form_colaborador.html", item=None, usuario_acesso=item_form, access_form=True, obras=obras_ativas, colaboradores=colaboradores_disponiveis, selected_colaborador_id=colaborador_id_raw)

        if not colaborador_id_raw:
            flash("Selecione um colaborador para vincular o acesso.", "danger")
            return render_template("cadastros/colaboradores/form_colaborador.html", item=None, usuario_acesso=item_form, access_form=True, obras=obras_ativas, colaboradores=colaboradores_disponiveis, selected_colaborador_id=colaborador_id_raw)

        try:
            colaborador_id = int(colaborador_id_raw)
        except (TypeError, ValueError):
            flash("Colaborador inválido.", "danger")
            return render_template("cadastros/colaboradores/form_colaborador.html", item=None, usuario_acesso=item_form, access_form=True, obras=obras_ativas, colaboradores=colaboradores_disponiveis, selected_colaborador_id=colaborador_id_raw)

        colaborador = Colaborador.query.filter_by(id=colaborador_id, empresa_id=empresa_id).first()
        if not colaborador:
            flash("Colaborador não encontrado.", "danger")
            return render_template("cadastros/colaboradores/form_colaborador.html", item=None, usuario_acesso=item_form, access_form=True, obras=obras_ativas, colaboradores=colaboradores_disponiveis, selected_colaborador_id=colaborador_id_raw)

        usuario_vinculado = Usuario.query.filter(
            Usuario.empresa_id == empresa_id,
            Usuario.colaborador_id == colaborador_id,
            Usuario.id != int(user_id or 0),
        ).first()
        if usuario_vinculado:
            flash("Este colaborador já possui um usuário vinculado.", "danger")
            return render_template("cadastros/colaboradores/form_colaborador.html", item=colaborador, usuario_acesso=item_form, access_form=True, obras=obras_ativas, colaboradores=colaboradores_disponiveis, selected_colaborador_id=colaborador_id_raw)

        if Usuario.query.filter(Usuario.empresa_id == empresa_id, Usuario.email == email, Usuario.id != int(user_id or 0)).first():
            flash("Este e-mail já está cadastrado.", "danger")
            return render_template("cadastros/colaboradores/form_colaborador.html", item=colaborador, usuario_acesso=item_form, access_form=True, obras=obras_ativas, colaboradores=colaboradores_disponiveis, selected_colaborador_id=colaborador_id_raw)

        if user_id:
            user = Usuario.query.filter_by(id=user_id, empresa_id=empresa_id).first_or_404()
            # Validar se Gestor pode editar este usuário
            if not current_user_obj.is_admin:
                # Simplificação: Se o usuário alvo tem alguma obra em comum, permite (ou restringe mais conforme regra)
                # Por segurança, impede edição de admin por gestor
                if user.is_admin:
                    flash("Gestores não podem editar Admins.", "danger")
                    return redirect(url_for('auth.lista_usuarios'))

            user.email = email
            user.colaborador_id = colaborador_id
            user.status = status
            set_audit_on_update(user, user_id=audit_user_id)
        else:
            user = Usuario(
                empresa_id=empresa_id,
                colaborador_id=colaborador_id,
                email=email,
                ativo=status,
            )
            user.primeiro_acesso = True
            user.set_senha(senha if senha else "Usuario123")
            set_audit_on_create(user, user_id=audit_user_id)
            db.session.add(user)
            db.session.flush()

        if papel_norm == ROLE_ADMIN:
            user.obras_permitidas = Obra.query.filter_by(empresa_id=empresa_id).all()
        else:
            obras_selecionadas = []
            if obras_ids:
                # SECURITY: Garantir que Gestor só vincula obras que ele tem acesso
                allowed_ids = [o.id for o in obras_ativas]
                for oid in obras_ids:
                    if oid:
                        if current_user_obj.is_admin or int(oid) in allowed_ids:
                            obra = Obra.query.get(int(oid))
                            if obra: obras_selecionadas.append(obra)
            user.obras_permitidas = obras_selecionadas

        try:
            _sincronizar_papel_usuario(user, papel, empresa_id)
            db.session.commit()
            flash("Usuário salvo com sucesso!", "success")
            return redirect(url_for('auth.lista_usuarios'))
        except Exception as e:
            db.session.rollback()
            flash(f"Erro: {str(e)}", "danger")
            return render_template("cadastros/colaboradores/form_colaborador.html", item=colaborador, usuario_acesso=item_form, access_form=True, obras=obras_ativas, colaboradores=colaboradores_disponiveis, selected_colaborador_id=colaborador_id_raw)

@auth_bp.post("/mudar-status-usuario/<int:userId>")
@auth_bp.post("/usuarios/<int:userId>/toggle-status")
@login_required
@permission_required('usuario.manage')
def toggle_user_status(userId):
    # SECURITY: Verifica permissão sobre o usuário alvo (tenant)
    empresa_id = session.get('empresa_id')
    user_alvo = Usuario.query.filter_by(id=userId, empresa_id=empresa_id).first_or_404()
    current_user_obj = Usuario.query.get(session.get("user_id"))
    if current_user_obj and (current_user_obj.papel or "").strip().upper() == ROLE_GESTOR:
        if user_alvo.is_admin:
            return jsonify({"message": "Proibido alterar Admin"}), 403
    
    user_alvo.status = not user_alvo.status 
    set_audit_on_update(user_alvo)
    try:
        db.session.commit()
        return jsonify({"message": "Status atualizado", "status": user_alvo.status}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": str(e)}), 500
     
@auth_bp.post("/usuario-resetar-senha/<int:id>")
@auth_bp.post("/usuarios/<int:id>/resetar-senha")
@login_required
@permission_required('usuario.manage')
def reset_senha_usuario(id):
    empresa_id = session.get('empresa_id')
    user = Usuario.query.filter_by(id=id, empresa_id=empresa_id).first_or_404()
    if user.colaborador_id:
        return redirect(url_for('auth.editar_colaborador', id=user.colaborador_id))
    # SECURITY
    current_user_obj = Usuario.query.get(session.get("user_id"))
    if current_user_obj and (current_user_obj.papel or "").strip().upper() == ROLE_GESTOR and user.is_admin:
         return {"message": "Gestor não reseta senha de Admin"}, 403

    user.set_senha("Usuario123")
    user.primeiro_acesso = True
    set_audit_on_update(user)
    db.session.commit()
    return {"message": "Sucesso"}, 200
    

@auth_bp.route("/editar-usuario/<int:id>", methods=['GET', 'POST'])
@auth_bp.route("/usuarios/<int:id>/editar", methods=['GET', 'POST'])
@login_required
@permission_required('usuario.manage')
def editar_usuario(id):
    empresa_id = session.get('empresa_id')
    user_edit = Usuario.query.filter_by(id=id, empresa_id=empresa_id).first_or_404()
    if not user_edit.colaborador_id:
        flash("UsuÃ¡rio sem colaborador vinculado.", "danger")
        return redirect(url_for('auth.lista_usuarios'))
    return redirect(url_for('auth.editar_colaborador', id=user_edit.colaborador_id))
    
@auth_bp.get("/visualizar-usuario/<int:id>")
@auth_bp.get("/usuarios/<int:id>")
@login_required
@permission_required('usuario.manage')
def visualizar_usuario(id):
    empresa_id = session.get('empresa_id')
    user_view = Usuario.query.filter_by(id=id, empresa_id=empresa_id).first_or_404()
    if not user_view.colaborador_id:
        flash("UsuÃ¡rio sem colaborador vinculado.", "danger")
        return redirect(url_for('auth.lista_usuarios'))
    return redirect(url_for('auth.visualizar_colaborador', id=user_view.colaborador_id))

@auth_bp.before_app_request
def check_primeiro_acesso():
    user_id = session.get("user_id")
    if user_id:
        user = Usuario.query.get(user_id)
        if user and getattr(user, 'troca_senha_obrigatoria', False):
            rotas_permitidas = ['auth.alterar_senha_obrigatoria', 'auth.logout', 'static', 'auth.login']
            if request.endpoint not in rotas_permitidas:
                flash("Por segurança, você deve alterar sua senha no primeiro acesso.", "warning")
                return redirect(url_for('auth.alterar_senha_obrigatoria'))
        
@auth_bp.route("/alterar-senha-obrigatoria", methods=["GET", "POST"])
@login_required
def alterar_senha_obrigatoria():
    if request.method == "POST":
        nova_senha = request.form.get("nova_senha")
        confirmar_senha = request.form.get("confirmar_senha")

        if not nova_senha or not confirmar_senha:
            flash("Preencha todos os campos.", "danger")
            return render_template("auth/alterar_senha_obrigatoria.html")

        if nova_senha != confirmar_senha:
            flash("As senhas não conferem.", "danger")
            return render_template("auth/alterar_senha_obrigatoria.html")
            
        if len(nova_senha) < 6:
             flash("A senha deve ter no mínimo 6 caracteres.", "danger")
             return render_template("auth/alterar_senha_obrigatoria.html")

        user = Usuario.query.get(session.get("user_id"))
        user.set_senha(nova_senha)
        user.troca_senha_obrigatoria = False
        if getattr(user, 'primeiro_acesso_em', None) is None:
            user.primeiro_acesso_em = utcnow_naive()
        try:
            db.session.commit()
            flash("Senha alterada com sucesso! Bem-vindo.", "success")
            return redirect(url_for("auth.inicio"))
        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao salvar senha: {str(e)}", "danger")

    return render_template("auth/alterar_senha_obrigatoria.html")

#######################################################################################################
####################################################################################################### LISTAS AUXILIARES (Clima, Equip, MaoObra, Tags)
#######################################################################################################
# RBAC: Visualizar = Todos | Criar/Editar = Admin, Gestor, Operador | Excluir = Admin, Gestor
