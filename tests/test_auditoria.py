from app import db
from app.models.empresa import Empresa
from app.models.auditoria import AuditoriaLog
from app.models.usuario import Usuario
from app.services.auditoria_service import AuditoriaService


def test_auditoria_service_registers_operation(app):
    with app.app_context():
        empresa = Empresa(nome="Auditoria Teste", ativo=True)
        db.session.add(empresa)
        db.session.commit()

        AuditoriaService.registrar_operacao(
            acao="TEST_OPERATION",
            entidade="TEST_ENTITY",
            entidade_id=10,
            antes={"campo": "valor_antigo"},
            depois={"campo": "valor_novo"},
            empresa_id=empresa.id,
            usuario_id=None,
            ip="127.0.0.1",
            user_agent="pytest",
            endpoint="test.endpoint",
            metodo_http="POST",
            payload={"foo": "bar"},
        )
        db.session.commit()

        log = AuditoriaLog.query.filter_by(acao="TEST_OPERATION").first()
        assert log is not None
        assert log.entidade == "TEST_ENTITY"
        assert log.dados_antes["campo"] == "valor_antigo"
        assert log.dados_depois["campo"] == "valor_novo"
        assert log.dados_antes["meta"]["foo"] == "bar"


def test_auditoria_service_registers_login_event(app):
    with app.app_context():
        empresa = Empresa(nome="Auditoria Login", ativo=True)
        db.session.add(empresa)
        db.session.commit()

        usuario = Usuario(
            empresa_id=empresa.id,
            email="login@test.com",
            senha_hash="testhash",
            ativo=True,
        )
        db.session.add(usuario)
        db.session.commit()

        AuditoriaService.registrar_login(
            sucesso=True,
            login_informado="login@test.com",
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            ip="127.0.0.1",
            user_agent="pytest",
            endpoint="auth.login",
            metodo_http="POST",
        )
        db.session.commit()

        log = AuditoriaLog.query.filter_by(acao="LOGIN_SUCESSO").first()
        assert log is not None
        assert log.dados_depois["sucesso"] is True
        assert log.dados_depois["login_informado"] == "login@test.com"
