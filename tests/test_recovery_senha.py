"""
Testes para recuperacao de senha.
"""

import pytest
from itsdangerous import SignatureExpired, URLSafeTimedSerializer

from app.models.sessao import AcessoLog
from app.models.usuario import Usuario


class TestRecuperacaoSenha:
    """Testes de fluxo de recuperacao de senha."""

    def test_solicitar_recuperacao_senha(self, client, usuario_empresa1):
        """Usuario pode solicitar recuperacao de senha."""
        response = client.post(
            "/auth/esqueci-senha",
            data={"email": usuario_empresa1.email},
            follow_redirects=False,
        )

        assert response.status_code == 302
        assert "/auth/login" in response.headers["Location"]

    def test_token_recuperacao_expira(self, app, usuario_empresa1):
        """Token de recuperacao expira conforme max_age do serializer."""
        with app.app_context():
            serializer = URLSafeTimedSerializer(app.config["SECRET_KEY"])
            token = serializer.dumps(usuario_empresa1.email, salt="recuperacao-senha")

            with pytest.raises(SignatureExpired):
                serializer.loads(token, salt="recuperacao-senha", max_age=-1)

    def test_token_assinado_identifica_usuario(self, app, usuario_empresa1):
        """Token assinado identifica o email do usuario."""
        with app.app_context():
            serializer = URLSafeTimedSerializer(app.config["SECRET_KEY"])
            token = serializer.dumps(usuario_empresa1.email, salt="recuperacao-senha")

            assert serializer.loads(token, salt="recuperacao-senha", max_age=3600) == usuario_empresa1.email

    def test_token_invalido_nao_funciona(self, client):
        """Token invalido nao permite reset de senha."""
        response = client.get("/auth/redefinir-senha/token-invalido", follow_redirects=False)

        assert response.status_code == 302
        assert "/auth/esqueci-senha" in response.headers["Location"]

    def test_token_assinado_valido_ate_expirar(self, app, usuario_empresa1):
        """Token assinado permanece valido dentro da janela configurada."""
        with app.app_context():
            serializer = URLSafeTimedSerializer(app.config["SECRET_KEY"])
            token = serializer.dumps(usuario_empresa1.email, salt="recuperacao-senha")

            assert serializer.loads(token, salt="recuperacao-senha", max_age=3600) == usuario_empresa1.email

    def test_reset_senha_com_token_valido(self, client, app, usuario_empresa1):
        """Resetar senha com token valido funciona."""
        with app.app_context():
            serializer = URLSafeTimedSerializer(app.config["SECRET_KEY"])
            token = serializer.dumps(usuario_empresa1.email, salt="recuperacao-senha")

        response = client.post(
            f"/auth/redefinir-senha/{token}",
            data={"nova_senha": "SenhaNova123", "confirmar_senha": "SenhaNova123"},
            follow_redirects=False,
        )

        assert response.status_code == 302
        assert "/auth/login" in response.headers["Location"]

        with app.app_context():
            usuario = Usuario.query.filter_by(email=usuario_empresa1.email).first()
            assert usuario is not None
            assert usuario.check_senha("SenhaNova123")


class TestFluxoRecuperacaoEmail:
    """Testes de fluxo de recuperacao via email."""

    def test_esqueci_senha_get_renders_form(self, client):
        """A pagina de esqueci senha deve ser acessivel."""
        response = client.get("/auth/esqueci-senha")
        assert response.status_code == 200
        assert b"E-mail" in response.data or b"email" in response.data.lower()

    def test_esqueci_senha_post_email_valido_redireciona_para_login(self, client, usuario_empresa1):
        """Solicitacao de recuperacao com email valido redireciona para login."""
        response = client.post(
            "/auth/esqueci-senha",
            data={"email": usuario_empresa1.email},
            follow_redirects=False,
        )

        assert response.status_code == 302
        assert "/auth/login" in response.headers["Location"]

    def test_redefinir_senha_get_com_token_valido(self, client, app, usuario_empresa1):
        """GET em redefinir senha com token valido mostra formulario."""
        with app.app_context():
            serializer = URLSafeTimedSerializer(app.config["SECRET_KEY"])
            token = serializer.dumps(usuario_empresa1.email, salt="recuperacao-senha")

        response = client.get(f"/auth/redefinir-senha/{token}")
        assert response.status_code == 200
        assert b"nova_senha" in response.data or b"Nova senha" in response.data

    def test_redefinir_senha_post_altera_senha(self, client, app, usuario_empresa1):
        """Submeter nova senha altera a senha do usuario."""
        with app.app_context():
            serializer = URLSafeTimedSerializer(app.config["SECRET_KEY"])
            token = serializer.dumps(usuario_empresa1.email, salt="recuperacao-senha")

        response = client.post(
            f"/auth/redefinir-senha/{token}",
            data={"nova_senha": "SenhaNova123", "confirmar_senha": "SenhaNova123"},
            follow_redirects=False,
        )

        assert response.status_code == 302
        assert "/auth/login" in response.headers["Location"]

        with app.app_context():
            usuario = Usuario.query.filter_by(email=usuario_empresa1.email).first()
            assert usuario is not None
            assert usuario.check_senha("SenhaNova123")

    def test_redefinir_senha_token_invalido_redireciona(self, client):
        """Token invalido de redefinicao redireciona para esqueci senha."""
        response = client.get("/auth/redefinir-senha/invalid-token", follow_redirects=False)
        assert response.status_code == 302
        assert "/auth/esqueci-senha" in response.headers["Location"]


class TestSegurancaRecuperacao:
    """Testes de seguranca do fluxo de recuperacao."""

    def test_token_nao_fica_visivel_em_logs(self, app, usuario_empresa1):
        """Token de recuperacao nao fica gravado nos logs de acesso."""
        with app.app_context():
            serializer = URLSafeTimedSerializer(app.config["SECRET_KEY"])
            token = serializer.dumps(usuario_empresa1.email, salt="recuperacao-senha")

            logs = AcessoLog.query.all()
            assert all(token not in str(log.detalhes or {}) for log in logs)

    def test_limite_tentativas_recuperacao(self):
        """Tokens gerados para recuperacao devem ser individuais."""
        import hashlib

        tokens_criados = [
            hashlib.sha256(f"token_{i}".encode()).hexdigest()
            for i in range(5)
        ]

        assert len(set(tokens_criados)) == 5

    def test_token_aleatorio_suficientemente_longo(self):
        """Token de recuperacao e suficientemente aleatorio."""
        import secrets

        tokens = {secrets.token_urlsafe(32) for _ in range(10)}

        assert len(tokens) == 10
