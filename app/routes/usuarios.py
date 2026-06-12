from app.routes.auth_common import *

@auth_bp.get("/lista-usuarios")
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

    # Preenchimento de supervisor (mantido)
    sup_ids = set()
    for u in usuarios:
        try:
            if u.id_supervisor is not None and str(u.id_supervisor).strip() != '':
                sup_ids.add(int(str(u.id_supervisor).strip()))
        except Exception: continue

    sup_map = {}
    if sup_ids:
        supervisors = Usuario.query.filter(Usuario.id.in_(list(sup_ids))).all()
        sup_map = {s.id: s.nome for s in supervisors}

    for u in usuarios:
        nome_sup = None
        try:
            if u.id_supervisor is not None and str(u.id_supervisor).strip() != '':
                sup_id = int(str(u.id_supervisor).strip())
                nome_sup = sup_map.get(sup_id)
        except Exception: pass
        setattr(u, 'nome_supervisor', nome_sup)

    return render_template("cadastros/usuarios/list_usuarios.html", opcoes=usuarios, categoria="usuario")

@auth_bp.get("/criar-usuario")
@login_required
@permission_required('usuario.manage')
def criar_usuario():
    # SCOPING: Gestor só pode vincular às suas obras
    empresa_id = session.get('empresa_id')
    user = Usuario.query.get(session.get("user_id"))
    if user and user.is_admin:
        obras = Obra.query.filter_by(empresa_id=empresa_id, status=1).order_by(Obra.nome).all()
    else:
        obras = [o for o in Obra.query.filter_by(empresa_id=empresa_id).all() if o.status == 1]
    
    admin = (
        Usuario.query
        .join(UsuarioPapel, UsuarioPapel.usuario_id == Usuario.id)
        .join(Papel, Papel.id == UsuarioPapel.papel_id)
        .filter(
            Usuario.empresa_id == empresa_id,
            UsuarioPapel.empresa_id == empresa_id,
            Usuario.ativo.is_(True),
            UsuarioPapel.ativo.is_(True),
            func.upper(Papel.nome) == ROLE_ADMIN,
        )
        .first()
    )
    default_supervisor = {'id': admin.id, 'nome': admin.nome, 'email': admin.email} if admin else None

    return render_template(
        "cadastros/usuarios/form_usuario.html", 
        categoria="usuario", 
        obras=obras,
        default_supervisor=default_supervisor
    )

@auth_bp.post("/gerar-usuario")
@login_required
@permission_required('usuario.manage')
def gerar_usuario():
    categoria = request.form.get("categoria")
    user_id = request.form.get("id")
    empresa_id = session.get('empresa_id')
    current_user_obj = Usuario.query.get(session.get("user_id"))
    
    # SCOPING: Para reload do template em caso de erro
    if current_user_obj.is_admin:
        obras_ativas = Obra.query.filter_by(empresa_id=empresa_id, status=1).order_by(Obra.nome).all()
    else:
        obras_ativas = [o for o in current_user_obj.obras_permitidas if o.status == 1 and o.empresa_id == empresa_id]

    if categoria == "usuario":
        nome = request.form.get("nome")
        email = request.form.get("email")
        papel = request.form.get("papel")
        cpf = request.form.get("cpf") 
        senha = request.form.get("senha")
        status_raw = (request.form.get("status") or "").strip().lower()
        status = status_raw in {"1", "true", "on", "ativo"}
        obras_ids = request.form.getlist("obras_permitidas")
        id_supervisor_raw = request.form.get('id_supervisor')

        # SECURITY: Gestor não pode criar Admin
        papel_norm = (papel or "").strip().upper()

        if (current_user_obj.papel or "").strip().upper() == ROLE_GESTOR and papel_norm == ROLE_ADMIN:
            flash("Gestores não podem criar usuários Administradores.", "danger")
            return render_template("cadastros/usuarios/form_usuario.html", item=None, obras=obras_ativas)

        item_form = {'id': user_id, 'nome': nome, 'email': email, 'papel': papel, 'cpf': cpf}

        if user_id:
            user = Usuario.query.filter_by(id=user_id, empresa_id=empresa_id).first_or_404()
            # Validar se Gestor pode editar este usuário
            if not current_user_obj.is_admin:
                # Simplificação: Se o usuário alvo tem alguma obra em comum, permite (ou restringe mais conforme regra)
                # Por segurança, impede edição de admin por gestor
                if user.is_admin:
                    flash("Gestores não podem editar Admins.", "danger")
                    return redirect(url_for('auth.lista_usuarios'))

            if Usuario.query.filter(Usuario.empresa_id == empresa_id, Usuario.cpf == cpf, Usuario.id != user_id).first():
                flash("Este CPF já está cadastrado.", "danger")
                return render_template("cadastros/usuarios/form_usuario.html", item=item_form, obras=obras_ativas)
            
            user.nome, user.email, user.papel, user.cpf, user.status = nome, email, papel, cpf, status
            try: user.id_supervisor = int(id_supervisor_raw) if id_supervisor_raw else None
            except Exception: user.id_supervisor = None
        else:
            if Usuario.query.filter_by(cpf=cpf).first():
                flash("CPF já cadastrado.", "danger")
                return render_template("cadastros/usuarios/form_usuario.html", item=item_form, obras=obras_ativas)

            user = Usuario(nome=nome, email=email, papel=papel, cpf=cpf, status=status, primeiro_acesso=True)
            try: user.id_supervisor = int(id_supervisor_raw) if id_supervisor_raw else None
            except Exception: user.id_supervisor = None
            user.set_senha(senha if senha else "Usuario123")
            db.session.add(user)

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

        if not getattr(user, 'id_supervisor', None):
            try:
                admin = next((u for u in Usuario.query.filter_by(empresa_id=empresa_id, ativo=True).all() if u.is_admin), None)
                if admin: user.id_supervisor = admin.id
            except Exception: pass

        try:
            db.session.commit()
            flash("Usuário salvo com sucesso!", "success")
            return render_template("cadastros/usuarios/form_usuario.html", item=user, obras=obras_ativas, view_mode=True)
        except Exception as e:
            db.session.rollback()
            flash(f"Erro: {str(e)}", "danger")
            return render_template("cadastros/usuarios/form_usuario.html", item=item_form, obras=obras_ativas)

@auth_bp.post("/mudar-status-usuario/<int:userId>")
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
    try:
        db.session.commit()
        return jsonify({"message": "Status atualizado", "status": user_alvo.status}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": str(e)}), 500
     
@auth_bp.post("/usuario-resetar-senha/<int:id>")
@login_required
@permission_required('usuario.manage')
def reset_senha_usuario(id):
    empresa_id = session.get('empresa_id')
    user = Usuario.query.filter_by(id=id, empresa_id=empresa_id).first_or_404()
    # SECURITY
    current_user_obj = Usuario.query.get(session.get("user_id"))
    if current_user_obj and (current_user_obj.papel or "").strip().upper() == ROLE_GESTOR and user.is_admin:
         return {"message": "Gestor não reseta senha de Admin"}, 403

    user.set_senha("Usuario123")
    user.primeiro_acesso = True
    db.session.commit()
    return {"message": "Sucesso"}, 200
    

@auth_bp.route("/editar-usuario/<int:id>", methods=['GET', 'POST'])
@login_required
@permission_required('usuario.manage')
def editar_usuario(id):
    empresa_id = session.get('empresa_id')
    user_edit = Usuario.query.filter_by(id=id, empresa_id=empresa_id).first_or_404()
    current_user_obj = Usuario.query.get(session.get("user_id"))

    # SECURITY Scope
    if (current_user_obj.papel or "").strip().upper() == ROLE_GESTOR:
        if user_edit.is_admin:
            flash("Acesso negado.", "danger")
            return redirect(url_for('auth.lista_usuarios'))
        obras = [o for o in current_user_obj.obras_permitidas if o.status == 1]
    else:
        obras = Obra.query.filter_by(empresa_id=session.get('empresa_id'), status=1).order_by(Obra.nome).all()

    return render_template("cadastros/usuarios/form_usuario.html", item=user_edit, categoria="usuario", obras=obras)
    
@auth_bp.get("/visualizar-usuario/<int:id>")
@login_required
@permission_required('usuario.manage')
def visualizar_usuario(id):
    empresa_id = session.get('empresa_id')
    user_view = Usuario.query.filter_by(id=id, empresa_id=empresa_id).first_or_404()
    current_user_obj = Usuario.query.get(session.get("user_id"))
    
    # SECURITY Scope check
    if not current_user_obj.is_admin:
        # Verifica se tem obras em comum
        meus_ids = {o.id for o in current_user_obj.obras_permitidas}
        alvo_ids = {o.id for o in user_view.obras_permitidas}
        if not meus_ids.intersection(alvo_ids) and current_user_obj.id != user_view.id:
             flash("Você não tem permissão para visualizar este usuário.", "danger")
             return redirect(url_for('auth.lista_usuarios'))
        obras = [o for o in current_user_obj.obras_permitidas if o.status == 1]
    else:
        obras = Obra.query.filter_by(empresa_id=session.get('empresa_id'), status=1).order_by(Obra.nome).all()
    
    view_mode = True
    supervisor_chain = get_supervisor_chain_for_user(user_view)

    nome_supervisor = None
    if getattr(user_view, 'id_supervisor', None):
        try:
            sup = Usuario.query.get(int(user_view.id_supervisor))
            nome_supervisor = sup.nome if sup else None
        except Exception: pass
    setattr(user_view, 'nome_supervisor', nome_supervisor)

    default_supervisor = None
    try:
        admin = next((u for u in Usuario.query.filter_by(empresa_id=session.get('empresa_id'), ativo=True).all() if u.is_admin), None)
        if admin: default_supervisor = {'id': admin.id, 'nome': admin.nome, 'email': admin.email}
    except Exception: pass

    return render_template(
        "cadastros/usuarios/form_usuario.html", 
        item=user_view, 
        categoria="usuario", 
        obras=obras, 
        view_mode=view_mode, 
        supervisor_chain=supervisor_chain, 
        default_supervisor=default_supervisor
    )

def get_supervisor_chain_for_user(user):
    chain = []
    visited = set()
    current = user
    while current and getattr(current, 'id_supervisor', None):
        try: sup_id = int(getattr(current, 'id_supervisor'))
        except Exception: break
        if sup_id in visited: break
        sup = Usuario.query.get(sup_id)
        if not sup: break
        chain.append({'id': sup.id, 'nome': sup.nome, 'email': sup.email})
        visited.add(sup.id)
        current = sup
    return chain

@auth_bp.get('/supervisores')
@login_required
def lista_supervisores():
    empresa_id = session.get('empresa_id')
    users = Usuario.query.filter_by(empresa_id=empresa_id).order_by(Usuario.nome.asc()).all()
    result = [{'id': u.id, 'nome': u.nome, 'papel': u.papel, 'email': u.email} for u in users]
    return jsonify(result)

@auth_bp.before_app_request
def check_primeiro_acesso():
    user_id = session.get("user_id")
    if user_id:
        user = Usuario.query.get(user_id)
        if user and getattr(user, 'primeiro_acesso', False):
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
        user.primeiro_acesso = False 
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
