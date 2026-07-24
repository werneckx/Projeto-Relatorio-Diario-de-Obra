import pytest
from pathlib import Path

from flask import Flask

from app import create_app
from app.utils.template_loader import FallbackEncodingLoader


@pytest.fixture
def client():
    """Cria um cliente de teste da aplicação Flask"""
    app = create_app()
    app.config["TESTING"] = True

    with app.test_client() as client:
        yield client


def test_app_running(client):
    """Verifica se a aplicação inicia corretamente"""
    response = client.get("/", follow_redirects=False)
    assert response.status_code in [200, 302, 404], "A aplicação não está respondendo como esperado."


def test_blueprints_registered():
    """Confirma que os blueprints foram registrados no create_app()"""
    app = create_app()
    assert len(app.blueprints) > 0, "Nenhum blueprint foi registrado."


def test_config_loaded():
    """Verifica se a configuração da aplicação foi carregada"""
    app = create_app()
    assert "SECRET_KEY" in app.config, "SECRET_KEY não foi carregado."


def test_jinja_loader_accepts_cp1252_template(tmp_path: Path):
    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    template_path = template_dir / "legacy.html"
    template_path.write_bytes("Configuração da empresa".encode("cp1252"))

    app = Flask(__name__, root_path=str(tmp_path), template_folder="templates")
    app.jinja_env.loader = FallbackEncodingLoader(app.jinja_env.loader)

    with app.app_context():
        rendered = app.jinja_env.get_template("legacy.html").render()

    assert rendered == "Configuração da empresa"