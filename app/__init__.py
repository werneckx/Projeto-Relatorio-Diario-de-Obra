from flask import Flask, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_wtf import CSRFProtect
import json

# Extensões
csrf = CSRFProtect()
db = SQLAlchemy()
login_manager = LoginManager()


def create_app():
    app = Flask(__name__)
    # Boas Práticas: Usar caminhos relativos para configuração
    app.config.from_object("config.Config") 

    # Inicializar extensões
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    Migrate(app, db) # A ordem de inicialização está correta

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
    
    # Boas Práticas: Sempre registrar Blueprints APÓS os Models e Configs
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(admin_bp)
    app.jinja_env.filters['from_json'] = json.loads
    
    # ---------------------------
    # Redirecionamento da raiz
    # ---------------------------
    @app.route("/")
    def root_redirect():
        # Boa prática: Use 'index' ou 'dashboard' aqui, se o login for bem-sucedido
        # Se for apenas para redirecionar para o login, está correto.
        return redirect(url_for("auth.login"))

    return app
