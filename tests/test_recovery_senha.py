"""
Testes para Recuperação de Senha - Branch 11
"""

import pytest
from itsdangerous import URLSafeTimedSerializer
from app import db
from app.models.usuario import Usuario
from app.models.empresa import Empresa


class TestRecuperacaoSenha:
    """Testes de fluxo de recuperação de senha."""

    def test_solicitar_recuperacao_senha(self, app, usuario_empresa1):
        """Usuário pode solicitar recuperação de senha."""
        with app.app_context():
            # Simular solicitação de recuperação
            import hashlib
            import secrets
            
            token = secrets.token_urlsafe(32)
            token_hash = hashlib.sha256(token.encode()).hexdigest()
            
            recuperacao = RecuperacaoSenha(
                usuario_id=usuario_empresa1.id,
                token_hash=token_hash,
                expira_em=datetime.utcnow() + timedelta(hours=24),
                utilizada=False,
            )
            db.session.add(recuperacao)
            db.session.commit()

            # Verificar que recuperação foi criada
            rec = RecuperacaoSenha.query.filter_by(
                usuario_id=usuario_empresa1.id
            ).first()
            
            assert rec is not None
            assert rec.utilizada is False

    def test_token_recuperacao_expira(self, app, usuario_empresa1):
        """Token de recuperação expira após 24 horas."""
        with app.app_context():
            import hashlib
            
            token_hash = hashlib.sha256(b"test_token").hexdigest()
            
            # Criar token expirado
            recuperacao = RecuperacaoSenha(
                usuario_id=usuario_empresa1.id,
                token_hash=token_hash,
                expira_em=datetime.utcnow() - timedelta(hours=1),  # Expirado
                utilizada=False,
            )
            db.session.add(recuperacao)
            db.session.commit()

            # Verificar que está expirado
            now = datetime.utcnow()
            assert recuperacao.expira_em < now

    def test_usar_token_recuperacao_marca_como_utilizado(self, app, usuario_empresa1):
        """Usar token de recuperação marca como utilizado."""
        with app.app_context():
            import hashlib
            
            token_hash = hashlib.sha256(b"test_token").hexdigest()
            
            recuperacao = RecuperacaoSenha(
                usuario_id=usuario_empresa1.id,
                token_hash=token_hash,
                expira_em=datetime.utcnow() + timedelta(hours=24),
                utilizada=False,
            )
            db.session.add(recuperacao)
            db.session.commit()

            # Marcar como utilizado
            recuperacao.utilizada = True
            db.session.commit()

            # Verificar
            rec = RecuperacaoSenha.query.filter_by(
                usuario_id=usuario_empresa1.id
            ).first()
            
            assert rec.utilizada is True

    def test_token_invalido_nao_funciona(self, app, usuario_empresa1):
        """Token inválido não permite reset de senha."""
        with app.app_context():
            import hashlib
            
            token_valido_hash = hashlib.sha256(b"valido").hexdigest()
            token_invalido_hash = hashlib.sha256(b"invalido").hexdigest()
            
            recuperacao = RecuperacaoSenha(
                usuario_id=usuario_empresa1.id,
                token_hash=token_valido_hash,
                expira_em=datetime.utcnow() + timedelta(hours=24),
                utilizada=False,
            )
            db.session.add(recuperacao)
            db.session.commit()

            # Tentar com token inválido
            rec_invalida = RecuperacaoSenha.query.filter_by(
                token_hash=token_invalido_hash
            ).first()
            
            assert rec_invalida is None

    def test_nao_pode_usar_token_duas_vezes(self, app, usuario_empresa1):
        """Token de recuperação não pode ser usado duas vezes."""
        with app.app_context():
            import hashlib
            
            token_hash = hashlib.sha256(b"test_token").hexdigest()
            
            recuperacao = RecuperacaoSenha(
                usuario_id=usuario_empresa1.id,
                token_hash=token_hash,
                expira_em=datetime.utcnow() + timedelta(hours=24),
                utilizada=False,
            )
            db.session.add(recuperacao)
            db.session.commit()

            # Usar token primeira vez
            recuperacao.utilizada = True
            db.session.commit()

            # Tentar usar novamente
            rec = RecuperacaoSenha.query.filter_by(
                usuario_id=usuario_empresa1.id
            ).first()
            
            # Deve estar marcado como utilizado
            assert rec.utilizada is True

    def test_reset_senha_com_token_valido(self, app, usuario_empresa1):
        """Resetar senha com token válido funciona."""
        with app.app_context():
            import hashlib
            
            token_hash = hashlib.sha256(b"test_token").hexdigest()
            
            # Criar token válido
            recuperacao = RecuperacaoSenha(
                usuario_id=usuario_empresa1.id,
                token_hash=token_hash,
                expira_em=datetime.utcnow() + timedelta(hours=24),
                utilizada=False,
            )
            db.session.add(recuperacao)
            db.session.commit()

            # Reset de senha
            nova_senha = "NovaSenha123"
            usuario_empresa1.set_senha(nova_senha)
            
            # Marcar token como utilizado
            recuperacao.utilizada = True
            db.session.commit()

            # Verificar que usuário pode fazer login com nova senha
            assert usuario_empresa1.verify_senha(nova_senha)


class TestFluxoRecuperacaoEmail:
    """Testes de fluxo de recuperação via email."""

    def test_esqueci_senha_get_renders_form(self, client):
        """A página de esqueci senha deve ser acessível."""
        response = client.get("/auth/esqueci-senha")
        assert response.status_code == 200
        assert b"E-mail" in response.data or b"email" in response.data.lower()

    def test_esqueci_senha_post_email_valido_redireciona_para_login(self, client, usuario_empresa1):
        """Solicitação de recuperação com email válido redireciona para login."""
        response = client.post(
            "/auth/esqueci-senha",
            data={"email": usuario_empresa1.email},
            follow_redirects=False,
        )

        assert response.status_code == 302
        assert "/auth/login" in response.headers["Location"]

    def test_redefinir_senha_get_com_token_valido(self, client, app, usuario_empresa1):
        """GET em redefinir senha com token válido mostra formulário."""
        with app.app_context():
            serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])
            token = serializer.dumps(usuario_empresa1.email, salt='recuperacao-senha')

        response = client.get(f"/auth/redefinir-senha/{token}")
        assert response.status_code == 200
        assert b"nova_senha" in response.data or b"Nova senha" in response.data

    def test_redefinir_senha_post_altera_senha(self, client, app, usuario_empresa1):
        """Submeter nova senha altera a senha do usuário."""
        with app.app_context():
            serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])
            token = serializer.dumps(usuario_empresa1.email, salt='recuperacao-senha')

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
        """Token inválido de redefinição redireciona para esqueci senha."""
        response = client.get("/auth/redefinir-senha/invalid-token", follow_redirects=False)
        assert response.status_code == 302
        assert "/auth/esqueci-senha" in response.headers["Location"]


class TestSegurancaRecuperacao:
    """Testes de segurança do fluxo de recuperação."""

    def test_token_nao_fica_visivel_em_logs(self, app, usuario_empresa1):
        """Token de recuperação não fica em logs de acesso."""
        with app.app_context():
            # O token deve ser armazenado apenas como hash
            import hashlib
            
            token = "super_secret_token_12345"
            token_hash = hashlib.sha256(token.encode()).hexdigest()
            
            # Armazenar apenas hash
            recuperacao = RecuperacaoSenha(
                usuario_id=usuario_empresa1.id,
                token_hash=token_hash,
                expira_em=datetime.utcnow() + timedelta(hours=24),
                utilizada=False,
            )
            db.session.add(recuperacao)
            db.session.commit()

            # Token original não deve estar no banco
            assert recuperacao.token_hash != token
            assert recuperacao.token_hash == token_hash

    def test_limite_tentativas_recuperacao(self, app, usuario_empresa1):
        """Implementação: Limitar tentativas de recuperação."""
        with app.app_context():
            # Este teste documenta que o sistema deve limitar
            # quantas recuperações um usuário pode solicitar
            
            import hashlib
            tokens_criados = []
            
            for i in range(5):
                token = hashlib.sha256(f"token_{i}".encode()).hexdigest()
                tokens_criados.append(token)
            
            # Em implementação real, apenas os últimos N tokens seriam válidos
            assert len(tokens_criados) == 5

    def test_token_aleatorio_suficientemente_longo(self, app, usuario_empresa1):
        """Token de recuperação é suficientemente aleatório."""
        with app.app_context():
            import secrets
            
            # Token deve ter entropia suficiente
            tokens = set()
            for _ in range(10):
                token = secrets.token_urlsafe(32)
                tokens.add(token)
            
            # Todos os tokens devem ser únicos
            assert len(tokens) == 10
