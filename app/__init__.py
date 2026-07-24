from flask import Flask, redirect, url_for, current_app, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_wtf import CSRFProtect
import json
from sqlalchemy.engine import Engine
from app.utils.template_loader import FallbackEncodingLoader

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

    # Ativa foreign key em SQLite para ON DELETE CASCADE funcionar.
    from sqlalchemy import event
    from app.models.auditoria import AuditoriaLog
    from app.models.sessao import AcessoLog

    @event.listens_for(Engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, connection_record):
        if db.engine.url.drivername.startswith("sqlite"):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

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
    app.jinja_env.loader = FallbackEncodingLoader(app.jinja_env.loader)

    # Filtro para converter datetimes UTC (naive) para timezone local da empresa/obra.
    # Import aqui para evitar import circular durante bootstrap do app.
    from app.utils.timezone_service import to_local_time, fmt_dt
    app.jinja_env.filters['to_local_time'] = to_local_time
    app.jinja_env.filters['fmt_dt'] = fmt_dt
    
    # Excluir rota de login do CSRF para facilitar testes
    csrf.exempt(auth_bp)

    # Injetar configurações resolvidas em runtime para templates e views
    from app.services.config_service import ConfigService

    @app.context_processor
    def inject_config():
        empresa_id = session.get('empresa_id')
        obra_id = session.get('obra_id')
        if not empresa_id:
            return {'config': {}}
        try:
            mapa = ConfigService.obter_mapa_config(empresa_id=empresa_id, obra_id=obra_id)
        except Exception:
            mapa = {}
        return {'config': mapa}
    
    # ---------------------------
    # Redirecionamento da raiz
    # ---------------------------
    @app.route("/")
    def root_redirect():
        # Boa prática: Use 'index' ou 'dashboard' aqui, se o login for bem-sucedido
        # Se for apenas para redirecionar para o login, está correto.
        return redirect(url_for("auth.login"))

    # Garantir que roles/permissões do sistema existam (idempotente)
    try:
        from sqlalchemy import inspect
        with app.app_context():
            # somente rodar o seed se a tabela de permissões existir (DB migrado)
            if inspect(db.engine).has_table('permissoes'):
                from app.routes.admin import seed_system_roles_and_permissions
                try:
                    seed_system_roles_and_permissions()
                except Exception:
                    app.logger.exception('Falha ao garantir roles/perms do sistema')
            else:
                app.logger.debug('Tabela permissoes ausente — pulando seed de roles/perms')
    except Exception:
        # Ambiente sem DB pronto — ignorar
        app.logger.exception('Erro ao verificar existência de tabelas para seed')

    return app
