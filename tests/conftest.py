import pytest

from app import create_app, db


@pytest.fixture
def app():
    app = create_app()
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    # Habilita CSRF nos testes para refletir comportamento do browser
    app.config["WTF_CSRF_ENABLED"] = True

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def obter_csrf(client):
    """Retorna uma função auxiliar para extrair csrf_token de uma página."""
    import re

    def _obter(url="/auth/login"):
        resp = client.get(url)
        body = resp.data.decode("utf-8", errors="ignore")
        m = re.search(r'name=["\']csrf_token["\']\s+value=["\']([^"\']+)["\']', body)
        return m.group(1) if m else None

    return _obter
