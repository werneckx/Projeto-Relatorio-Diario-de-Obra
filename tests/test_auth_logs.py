from app import db
from app.models.empresa import Empresa
from app.models.usuario import Usuario, Colaborador, Papel, UsuarioPapel
from app.models.sessao import SessaoUsuario, AcessoLog


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


def test_valid_login_creates_acesso_log_and_session(client, app):
    with app.app_context():
        user = create_admin_user()
        user_id = user.id

    # Obter csrf_token via GET e enviar no POST para simular browser
    csrf_token = client.get('/auth/login').data.decode('utf-8')
    from re import search
    m = search(r'name="csrf_token" value="([^"]+)"', csrf_token)
    token = m.group(1) if m else None

    response = client.post(
        "/auth/login",
        data={"email": "admin@test.com", "senha": "Senha123", "csrf_token": token},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert "/auth/inicio" in response.headers["Location"]

    with app.app_context():
        acesso_log = AcessoLog.query.filter_by(acao='LOGIN_SUCESSO').first()
        sessao = SessaoUsuario.query.filter_by(usuario_id=user_id, ativa=True).first()

        assert acesso_log is not None
        assert sessao is not None
        assert sessao.token_hash


def test_invalid_login_creates_failure_log(client, app):
    with app.app_context():
        create_admin_user()

    # Obter csrf_token via GET e enviar no POST para simular browser
    csrf_token = client.get('/auth/login').data.decode('utf-8')
    from re import search
    m = search(r'name="csrf_token" value="([^"]+)"', csrf_token)
    token = m.group(1) if m else None

    response = client.post(
        "/auth/login",
        data={"email": "admin@test.com", "senha": "SenhaErrada", "csrf_token": token},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]

    with app.app_context():
        acesso_log = AcessoLog.query.filter_by(acao='LOGIN_FALHA').first()
        assert acesso_log is not None
        # Motivo pode variar ('senha_invalida' ou 'credenciais inválidas'),
        # verificamos apenas que a chave existe e contém texto.
        assert isinstance(acesso_log.detalhes, dict)
        assert 'motivo' in acesso_log.detalhes
        assert isinstance(acesso_log.detalhes['motivo'], str)
