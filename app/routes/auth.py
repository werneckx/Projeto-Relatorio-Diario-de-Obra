from app.routes.auth_common import *

#######################################################################################################
####################################################################################################### Rota Raiz
#######################################################################################################

@auth_bp.get("/")
def index():
    if "user_id" in session:
        return redirect(url_for("auth.inicio"))
    return redirect(url_for("auth.login"))

#######################################################################################################
####################################################################################################### Login e Logout
#######################################################################################################

@auth_bp.route("/setup", methods=["GET", "POST"])
def setup():
    from app.routes.admin import seed_system_roles_and_permissions

    # Verifica se já existe algum admin no banco
    admin_exists = Usuario.query.join(Usuario.papeis).filter(
        Papel.nome == ROLE_ADMIN,
        Papel.is_system == True
    ).first()

    if admin_exists:
        flash("O sistema já está configurado.", "danger")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        empresa_nome = request.form.get("empresa_nome", "").strip()
        admin_nome = request.form.get("admin_nome", "").strip()
        admin_email = request.form.get("admin_email", "").strip()
        admin_senha = request.form.get("admin_senha", "")

        if not all([empresa_nome, admin_nome, admin_email, admin_senha]):
            flash("Todos os campos são obrigatórios.", "danger")
            return render_template("setup.html")

        try:
            # 1. Garantir que roles e permissões globais existam
            seed_system_roles_and_permissions()

            # 2. Criar Empresa principal
            nova_empresa = Empresa(nome=empresa_nome, ativo=True)
            db.session.add(nova_empresa)
            db.session.flush()

            # 3. Criar Colaborador admin
            novo_colab = Colaborador(
                nome=admin_nome,
                empresa_id=nova_empresa.id,
                tipo='PROPRIO',
                ativo=True
            )
            db.session.add(novo_colab)
            db.session.flush()

            # 4. Criar Usuário admin
            novo_user = Usuario(
                email=admin_email,
                empresa_id=nova_empresa.id,
                colaborador_id=novo_colab.id,
                ativo=True,
            )
            novo_user.set_senha(admin_senha)
            db.session.add(novo_user)
            db.session.flush()

            # 5. Buscar papel global ADMIN e vincular ao usuário
            papel_admin = Papel.query.filter_by(nome=ROLE_ADMIN, empresa_id=None).first()
            if papel_admin:
                db.session.add(UsuarioPapel(
                    empresa_id=nova_empresa.id,
                    usuario_id=novo_user.id,
                    papel_id=papel_admin.id,
                    ativo=True
                ))

            db.session.commit()
            flash("Sistema configurado com sucesso! Faça login.", "success")
            return redirect(url_for("auth.login"))

        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao configurar sistema: {str(e)}", "danger")

    return render_template("setup.html")

@auth_bp.get("/login")
def login():
    admin_exists = Usuario.query.join(Usuario.papeis).filter(Papel.nome == ROLE_ADMIN).first()
    if not admin_exists:
        return redirect(url_for("auth.setup"))
    return render_template("login.html")


@auth_bp.post("/login")
def login_post():
    form = LoginForm()
    if not form.validate_on_submit():
        for field_errors in form.errors.values():
            for error in field_errors:
                flash(error, "danger")
        return redirect(url_for("auth.login"))

    email = form.email.data
    senha = form.senha.data

    # 1. Adicionar o filtro 'ativo=1'
    user = Usuario.query.filter_by(email=email, ativo=True).first()

    # 2. Verificar se o usuário existe e se a senha está correta
    if not user or not user.check_senha(senha):
        # Auditoria + acesso log de falha
        user_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        if user_ip and ',' in user_ip:
            user_ip = user_ip.split(',')[0].strip()

        try:
            from app.models.sessao import AcessoLog
            from app.services.auditoria_service import AuditoriaService

            acesso = AcessoLog(
                empresa_id=getattr(user, "empresa_id", None),
                usuario_id=getattr(user, "id", None),
                email=email,
                acao='LOGIN_FALHA',
                ip=user_ip,
                user_agent=request.headers.get('User-Agent'),
                detalhes={"sucesso": False, "motivo": "credenciais inválidas"},
            )
            db.session.add(acesso)

            AuditoriaService.registrar_login(
                sucesso=False,
                motivo="credenciais inválidas",
                login_informado=email,
                ip=user_ip,
                user_agent=request.headers.get('User-Agent'),
                endpoint=request.endpoint,
                metodo_http=request.method,
                empresa_id=getattr(user, "empresa_id", None),
                usuario_id=getattr(user, "id", None),
            )
            db.session.commit()
        except Exception:
            db.session.rollback()

        flash("E-mail, senha ou status de usuário inválido.", "error")
        return redirect(url_for("auth.login"))

    
    # --- Captura de contexto (sem commit fragmentado) ---
    user_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if user_ip and ',' in user_ip:
        user_ip = user_ip.split(',')[0].strip()

    # --- Atualiza usuário e cria auditoria/acesso/sessão (transação única) ---
    user.ultimo_login = datetime.now()
    user.ultimo_login_ip = user_ip

    from uuid import uuid4
    from app.models.sessao import SessaoUsuario, AcessoLog
    from app.services.auditoria_service import AuditoriaService

    session_uuid = str(uuid4())
    acesso = AcessoLog(
        empresa_id=getattr(user, "empresa_id", None),
        usuario_id=user.id,
        email=user.email,
        acao='LOGIN_SUCESSO',
        ip=user_ip,
        user_agent=request.headers.get('User-Agent'),
        detalhes={"success": True},
    )
    db.session.add(acesso)

    sessao = SessaoUsuario(
        empresa_id=user.empresa_id,
        usuario_id=user.id,
        token_hash=session_uuid,
        ip=user_ip,
        user_agent=request.headers.get('User-Agent'),
        iniciada_em=datetime.utcnow(),
        expira_em=datetime.utcnow() + timedelta(hours=24),
        ativa=True,
    )
    db.session.add(sessao)

    # Auditoria (before/after não aplicável aqui; registramos evento de login)
    AuditoriaService.registrar_login(
        sucesso=True,
        empresa_id=user.empresa_id,
        usuario_id=user.id,
        ip=user_ip,
        user_agent=request.headers.get('User-Agent'),
        endpoint=request.endpoint,
        metodo_http=request.method,
        login_informado=email,
    )

    db.session.add(user)
    db.session.commit()

    # --- LOGIN NO FLASK-LOGIN ---
    login_user(user)


    
    session["session_uuid"] = session_uuid
    session["user_id"] = user.id

    session["empresa_id"] = user.empresa_id
    session["user_name"] = user.nome
    session["user_email"] = user.email
    session["user_role"] = user.papel if user.papel else "Leitor"

    # SECURITY: permissões efetivas (RBAC) para menu/validações de UI
    # Calcula a partir dos papéis realmente atribuídos ao usuário (RBAC real).
    # OBS: Papel.permissoes pode ser uma relationship que nem sempre retorna uma lista
    # (pode ser lazy/dynamic). Então tratamos como iterável.
    try:
        perms = set()

        user_papeis = user.papeis or []
        for papel in user_papeis:
            papel_perms = papel.permissoes or []
            for perm in papel_perms:
                if perm and perm.ativo:
                    perms.add(perm.chave)

        session["permissions"] = sorted(perms)
    except Exception as e:
        # Se falhar, não quebra login; menu ficará mais restrito
        print(f"[SECURITY] Falha ao calcular permissions no login: {e}")
        session["permissions"] = []

    return redirect(url_for("auth.inicio"))

@auth_bp.get("/logout")
def logout():
    # Logout normal: encerra a sessão corporativa e registra trilha
    current_session_uuid = session.get("session_uuid")
    try:
        from app.models.sessao import SessaoUsuario, AcessoLog
        from app.services.auth_service import AuthService
        from app.services.auditoria_service import AuditoriaService

        if current_session_uuid:
            # encerra via serviço (operação transacional; não faz commit internamente)
            AuthService.revogar_sessao(current_session_uuid, motivo="logout")

            # registra AcessoLog LOGOUT (opcional; trilha operacional)
            try:
                sessao = (
                    SessaoUsuario.query.filter(
                        SessaoUsuario.token_hash == current_session_uuid
                    ).first()
                )
                if sessao:
                    acesso = AcessoLog(
                        empresa_id=sessao.empresa_id,
                        usuario_id=sessao.usuario_id,
                        email=None,
                        acao='LOGOUT',
                        ip=None,
                        user_agent=None,
                        detalhes={"motivo": "logout"},
                    )
                    db.session.add(acesso)
            except Exception:
                pass

            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
    except Exception:
        pass

    session.clear()
    flash("Você foi desconectado com sucesso.", "info")
    return redirect(url_for("auth.login"))


# --- ROTAS DE RECUPERAÇÃO DE SENHA ---

@auth_bp.route("/esqueci-senha", methods=["GET", "POST"])
def esqueci_senha():
    admin_contato = Usuario.query.join(Usuario.papeis).filter(Papel.nome == ROLE_ADMIN).first()

    if request.method == "GET":
        return render_template("esqueci_senha.html", admin=admin_contato)
    
    email = request.form.get("email")
    user = Usuario.query.filter_by(email=email).first()
    
    if user:
        s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        token = s.dumps(email, salt='recuperacao-senha')
        link = url_for('auth.redefinir_senha', token=token, _external=True)
        
        print(f"========================================")
        print(f"LINK DE RECUPERAÇÃO PARA {email}:")
        print(f"{link}")
        print(f"========================================")
        
        flash("Um link de recuperação foi enviado para seu e-mail.", "success")
    else:
        flash("Se o e-mail estiver cadastrado, você receberá um link.", "success")
        
    return redirect(url_for("auth.login"))

@auth_bp.route("/redefinir-senha/<token>", methods=["GET", "POST"])
def redefinir_senha(token):
    s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        email = s.loads(token, salt='recuperacao-senha', max_age=3600)
    except SignatureExpired:
        flash("O link de recuperação expirou.", "danger")
        return redirect(url_for("auth.esqueci_senha"))
    except Exception:
        flash("Link de recuperação inválido.", "danger")
        return redirect(url_for("auth.esqueci_senha"))
    
    if request.method == "GET":
        return render_template("redefinir_senha.html", token=token)
    
    nova_senha = request.form.get("nova_senha")
    confirmar_senha = request.form.get("confirmar_senha")
    
    if nova_senha != confirmar_senha:
        flash("As senhas não conferem.", "danger")
        return render_template("redefinir_senha.html", token=token)
        
    user = Usuario.query.filter_by(email=email).first()
    
    if user:
        user.set_senha(nova_senha)
        db.session.commit()
        flash("Sua senha foi redefinida com sucesso! Faça login.", "success")
        return redirect(url_for("auth.login"))
        
    flash("Erro ao redefinir senha.", "danger")
    return redirect(url_for("auth.login"))

#######################################################################################################
####################################################################################################### Rotas Institucionais
#######################################################################################################

@auth_bp.get("/termos")
def termos():
    return render_template("termos.html")

@auth_bp.get("/privacidade")
def privacidade():
    return render_template("privacidade.html")

@auth_bp.get("/suporte")
def suporte():
    email_usuario = session.get("user_email", "")
    return render_template("suporte.html", email_usuario=email_usuario)



# Importa os dominios que registram rotas no mesmo auth_bp.
from app.routes import dashboard  # noqa: F401,E402
from app.routes import empresa  # noqa: F401,E402
from app.routes import documentos  # noqa: F401,E402
from app.routes import rdo  # noqa: F401,E402
from app.routes import rdo_assinaturas  # noqa: F401,E402
from app.routes import usuarios  # noqa: F401,E402
from app.routes import auxiliares  # noqa: F401,E402
from app.routes import obras  # noqa: F401,E402
from app.routes import perfil  # noqa: F401,E402
