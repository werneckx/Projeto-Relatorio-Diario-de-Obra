from datetime import datetime, timedelta

from app import db
from app.models.empresa import Empresa
from app.models.usuario import Usuario, Colaborador, Papel, UsuarioPapel
from app.models.sessao import SessaoUsuario, AcessoLog
from app.services.auth_service import AuthService


def create_admin_user():
    empresa = Empresa(nome="TesteEmpresa", ativo=True)
    db.session.add(empresa)
    db.session.flush()

    colaborador = Colaborador(
        nome="Admin Teste",
        empresa_id=empresa.id,
        tipo="PROPRIO",
        ativo=True,
    )
    db.session.add(colaborador)
    db.session.flush()

    papel = Papel(nome="ADMIN", ativo=True, is_system=True)
    db.session.add(papel)
    db.session.flush()

    usuario = Usuario(
        email="admin@test.com",
        empresa_id=empresa.id,
        colaborador_id=colaborador.id,
        ativo=True,
        troca_senha_obrigatoria=False,
    )
    usuario.set_senha("Senha123")
    db.session.add(usuario)
    db.session.flush()

    usuario_papel = UsuarioPapel(
        empresa_id=empresa.id,
        usuario_id=usuario.id,
        papel_id=papel.id,
        ativo=True,
    )
    db.session.add(usuario_papel)
    db.session.commit()
    return usuario


def test_expired_session_redirects_to_login(client, app):
    with app.app_context():
        user = create_admin_user()
        user_id = user.id
        empresa_id = user.empresa_id
        sessao = SessaoUsuario(
            empresa_id=empresa_id,
            usuario_id=user_id,
            token_hash="expired-token",
            ip="127.0.0.1",
            user_agent="pytest",
            iniciada_em=datetime.utcnow() - timedelta(days=1),
            expira_em=datetime.utcnow() - timedelta(hours=1),
            ativa=True,
        )
        db.session.add(sessao)
        db.session.commit()

    with client.session_transaction() as sess:
        sess["session_uuid"] = "expired-token"
        sess["user_id"] = user_id
        sess["empresa_id"] = empresa_id

    response = client.get("/auth/inicio", follow_redirects=False)
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]

    with app.app_context():
        sessao = SessaoUsuario.query.filter_by(token_hash="expired-token").first()
        assert sessao is not None
        assert sessao.ativa is False
        assert AcessoLog.query.filter_by(acao='SESSAO_EXPIRADA').count() == 1


def test_auth_service_revogar_sessao_marks_session_inactive(app):
    with app.app_context():
        user = create_admin_user()
        sessao = SessaoUsuario(
            empresa_id=user.empresa_id,
            usuario_id=user.id,
            token_hash="revoke-token",
            ip="127.0.0.1",
            user_agent="pytest",
            iniciada_em=datetime.utcnow(),
            expira_em=datetime.utcnow() + timedelta(hours=24),
            ativa=True,
        )
        db.session.add(sessao)
        db.session.commit()

        AuthService.revogar_sessao("revoke-token", motivo="teste remoto")
        db.session.commit()

        sessao = SessaoUsuario.query.filter_by(token_hash="revoke-token").first()
        assert sessao is not None
        assert sessao.ativa is False
        assert sessao.motivo_encerramento == "teste remoto"
        assert AcessoLog.query.filter_by(acao='LOGOUT_REMOTO').count() == 1


def test_delete_usuario_removes_sessoes(app):
    with app.app_context():
        usuario = create_admin_user()
        sessao = SessaoUsuario(
            empresa_id=usuario.empresa_id,
            usuario_id=usuario.id,
            token_hash="delete-token",
            ip="127.0.0.1",
            user_agent="pytest",
            iniciada_em=datetime.utcnow(),
            expira_em=datetime.utcnow() + timedelta(hours=1),
            ativa=True,
        )
        db.session.add(sessao)
        db.session.commit()

        db.session.delete(usuario)
        db.session.commit()

        assert SessaoUsuario.query.filter_by(token_hash="delete-token").count() == 0
