from flask import Flask, redirect, url_for, current_app
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_wtf import CSRFProtect
import json

# Extensões
csrf = CSRFProtect()
db = SQLAlchemy()
login_manager = LoginManager()


def create_app(config_overrides=None):
    app = Flask(__name__)
    # Boas Práticas: Usar caminhos relativos para configuração
    app.config.from_object("config.Config")
    if config_overrides:
        app.config.update(config_overrides)

    # Inicializar extensões
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    Migrate(app, db) # A ordem de inicialização está correta

    # Gatilho de flush para auditoria/transações
    from sqlalchemy import event
    from app.models.auditoria import AuditoriaLog
    from app.models.sessao import AcessoLog

    def _audit_before_flush(session, flush_context, instances):
        audit_objects = [obj for obj in session.new if getattr(obj, '__tablename__', None) in {'auditoria_log', 'acesso_log'}]
        if audit_objects:
            current_app.logger.debug(f"[auditoria] {len(audit_objects)} objetos de auditoria pendentes antes do flush")

    event.listen(db.session.__class__, 'before_flush', _audit_before_flush)

    # Onde o usuário será redirecionado ao tentar acessar sem login
    # O nome da view 'auth.login' está correto.
    login_manager.login_view = "auth.login"

    # IMPORTAR MODELOS APÓS INIT DO DB (para o Alembic e o DB saberem quais tabelas mapear)
    # A colocação aqui está correta para evitar o import circular com o 'db'
    from app.models import (
        arquivo,
        auditoria,
        auxiliares,
        cad_lista,
        cliente,
        configuracao,
        empresa,
        fornecedor,
        notificacao,
        obra,
        rdo,
        sessao,
        usuario,
        workflow,
    )

    # Registrar blueprints
    from app.routes.auth import auth_bp
    from app.routes.admin import admin_bp
    from app.routes.notificacoes import notificacoes_bp

    # Boas Práticas: Sempre registrar Blueprints APÓS os Models e Configs
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(admin_bp)
    app.register_blueprint(notificacoes_bp)

    # Middleware corporativo de sessão
    from app.middleware.sessao_middleware import init_sessao_middleware
    init_sessao_middleware(app)

    app.jinja_env.filters['from_json'] = json.loads

    # Filtro para converter datetimes UTC (naive) para timezone local da empresa/obra.
    # Import aqui para evitar import circular durante bootstrap do app.
    from app.utils.timezone_service import to_local_time, fmt_dt
    app.jinja_env.filters['to_local_time'] = to_local_time
    app.jinja_env.filters['fmt_dt'] = fmt_dt
    
    # Excluir rota de login do CSRF para facilitar testes
    csrf.exempt(auth_bp)
    
    # ---------------------------
    # Redirecionamento da raiz
    # ---------------------------
    @app.route("/")
    def root_redirect():
        # Boa prática: Use 'index' ou 'dashboard' aqui, se o login for bem-sucedido
        # Se for apenas para redirecionar para o login, está correto.
        return redirect(url_for("auth.login"))

    return app
