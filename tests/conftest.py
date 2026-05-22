import pytest

import os
from pathlib import Path

from app import create_app, db
from app.models.empresa import Empresa
from app.models.obra import Obra, FrenteTrabalho
from app.models.rdo import RDO
from app.models.usuario import Usuario, Papel, Colaborador


def _should_run_db_script(database_uri: str) -> bool:
    """
    Controla se o script SQL completo deve ser executado no reset do banco.

    Por padrão, os testes usam SQLite in-memory e criam tabelas via SQLAlchemy.
    O arquivo `data/Script Banco de Dados.sql` é voltado a MySQL e não roda em SQLite.

    Para habilitar a execução do script, exporte:
      - TEST_RUN_DB_SCRIPT=1
    e use uma URI compatível (ex.: mysql+pymysql://...).
    """
    if os.environ.get("TEST_RUN_DB_SCRIPT", "").strip() not in {"1", "true", "True"}:
        return False

    uri = (database_uri or "").lower()
    return uri.startswith("mysql") or uri.startswith("mariadb")


def _execute_sql_script(sqlalchemy_db, script_path: Path) -> None:
    """
    Executa um arquivo .sql no banco atual (dialeto do driver).

    Observação: split simples por ';' funciona bem para este projeto, pois o script
    é composto por DDL/DML convencionais (sem DELIMITER/rotinas complexas).
    """
    if not script_path.exists():
        raise FileNotFoundError(f"Script SQL não encontrado: {script_path}")

    sql_text = script_path.read_text(encoding="utf-8", errors="ignore")

    # Remove BOM e normaliza quebras de linha
    sql_text = sql_text.lstrip("\ufeff").replace("\r\n", "\n")

    statements = []
    for chunk in sql_text.split(";"):
        stmt = chunk.strip()
        if not stmt:
            continue
        # Ignora comentários isolados
        if stmt.startswith("--") or stmt.startswith("#"):
            continue
        statements.append(stmt)

    engine = sqlalchemy_db.engine
    with engine.begin() as conn:
        for stmt in statements:
            conn.exec_driver_sql(stmt)


@pytest.fixture(scope="session")
def app():
    # Importante: definir flags antes de qualquer acesso ao engine.
    # Como create_app() não aceita args, ajustamos após criar o app e antes de usar o db.
    database_uri = os.environ.get("TEST_DATABASE_URI") or "sqlite:///:memory:"

    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": database_uri,
        "WTF_CSRF_ENABLED": False,
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
    })


    with app.app_context():
        db.drop_all()

        # Opcional: executar o script MySQL completo (DDL + seed) após reset.
        # Útil quando você roda testes apontando para um MySQL de teste.
        if _should_run_db_script(app.config.get("SQLALCHEMY_DATABASE_URI", "")):
            script = Path(app.root_path).parent / "data" / "Script Banco de Dados.sql"
            _execute_sql_script(db, script)
        else:
            db.create_all()

        yield app
        db.session.remove()
        db.drop_all()




@pytest.fixture
def db_session(app):
    """Retorna uma sessão do SQLAlchemy ligada ao app de teste."""
    return db.session


@pytest.fixture(autouse=True)
def _db_rollback_between_tests(app):
    """
    Garante que um teste que falhe no meio de um flush/commit não contamine os próximos.

    Isso evita efeitos colaterais no teardown de fixtures quando o SQLAlchemy entra em
    estado de rollback (ex.: após IntegrityError durante flush).
    """
    yield
    try:
        db.session.rollback()
    finally:
        db.session.remove()


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


@pytest.fixture
def empresa(app):
    """Cria uma empresa para testes."""
    emp = Empresa(
        nome="Empresa Teste",
        ativo=True,
    )
    db.session.add(emp)
    db.session.commit()
    yield emp
    # Evita updates de FK para NULL em relacionamentos (workflow_definicoes.empresa_id)
    db.session.rollback()
    db.drop_all()
    db.create_all()


@pytest.fixture
def papel(app, empresa):
    """Cria um papel para testes."""
    pap = Papel(
        nome="Admin",
        empresa_id=empresa.id,
        ativo=True,
    )
    db.session.add(pap)
    db.session.commit()
    yield pap
    db.session.delete(pap)
    db.session.commit()


@pytest.fixture
def usuario(app, empresa, papel):
    """Cria um usuário para testes."""
    usr = Usuario(
        nome="Usuário Teste 1",
        email="usuario1@teste.com",
        empresa_id=empresa.id,
        ativo=True,
    )
    usr.set_senha("senha123")
    db.session.add(usr)
    db.session.flush()

    # A associação usuario<->papel exige empresa_id (NOT NULL na tabela usuario_papel)
    from app.models.usuario import UsuarioPapel
    usuario_papel = UsuarioPapel(
        empresa_id=empresa.id,
        usuario_id=usr.id,
        papel_id=papel.id,
        ativo=True,
    )
    db.session.add(usuario_papel)
    db.session.commit()
    yield usr
    from app.models.usuario import UsuarioPapel
    from app.models.arquivo import Arquivo
    from app.models.sessao import SessaoUsuario, AcessoLog
    from app.models.auditoria import AuditoriaLog

    db.session.query(UsuarioPapel).filter(UsuarioPapel.usuario_id == usr.id).delete(synchronize_session=False)
    db.session.query(Arquivo).filter(
        (Arquivo.criado_por == usr.id) | (Arquivo.modificado_por == usr.id)
    ).delete(synchronize_session=False)
    db.session.query(SessaoUsuario).filter(
        (SessaoUsuario.usuario_id == usr.id) | (SessaoUsuario.encerrada_por == usr.id)
    ).delete(synchronize_session=False)
    db.session.query(AcessoLog).filter(AcessoLog.usuario_id == usr.id).delete(synchronize_session=False)
    db.session.query(AuditoriaLog).filter(AuditoriaLog.usuario_id == usr.id).delete(synchronize_session=False)
    db.session.flush()
    db.session.expire_all()
    db.session.delete(usr)
    db.session.commit()


@pytest.fixture
def usuario2(app, empresa, papel):
    """Cria um segundo usuário para testes."""
    usr = Usuario(
        nome="Usuário Teste 2",
        email="usuario2@teste.com",
        empresa_id=empresa.id,
        ativo=True,
    )
    usr.set_senha("senha123")
    db.session.add(usr)
    db.session.flush()

    from app.models.usuario import UsuarioPapel
    usuario_papel = UsuarioPapel(
        empresa_id=empresa.id,
        usuario_id=usr.id,
        papel_id=papel.id,
        ativo=True,
    )
    db.session.add(usuario_papel)
    db.session.commit()
    yield usr
    from app.models.usuario import UsuarioPapel
    from app.models.arquivo import Arquivo
    from app.models.sessao import SessaoUsuario, AcessoLog
    from app.models.auditoria import AuditoriaLog

    db.session.query(UsuarioPapel).filter(UsuarioPapel.usuario_id == usr.id).delete(synchronize_session=False)
    db.session.query(Arquivo).filter(
        (Arquivo.criado_por == usr.id) | (Arquivo.modificado_por == usr.id)
    ).delete(synchronize_session=False)
    db.session.query(SessaoUsuario).filter(
        (SessaoUsuario.usuario_id == usr.id) | (SessaoUsuario.encerrada_por == usr.id)
    ).delete(synchronize_session=False)
    db.session.query(AcessoLog).filter(AcessoLog.usuario_id == usr.id).delete(synchronize_session=False)
    db.session.query(AuditoriaLog).filter(AuditoriaLog.usuario_id == usr.id).delete(synchronize_session=False)
    db.session.delete(usr)
    db.session.commit()


@pytest.fixture
def usuario3(app, empresa, papel):
    """Cria um terceiro usuário para testes."""
    usr = Usuario(
        nome="Usuário Teste 3",
        email="usuario3@teste.com",
        empresa_id=empresa.id,
        ativo=True,
    )
    usr.set_senha("senha123")
    db.session.add(usr)
    db.session.flush()

    from app.models.usuario import UsuarioPapel
    usuario_papel = UsuarioPapel(
        empresa_id=empresa.id,
        usuario_id=usr.id,
        papel_id=papel.id,
        ativo=True,
    )
    db.session.add(usuario_papel)
    db.session.commit()
    yield usr
    db.session.delete(usr)
    db.session.commit()


@pytest.fixture
def empresa1(app):
    """Cria primeira empresa para testes multiempresa."""
    emp = Empresa(nome="Empresa Teste 1", ativo=True)
    db.session.add(emp)
    db.session.commit()
    yield emp
    db.session.rollback()


@pytest.fixture
def empresa2(app):
    """Cria segunda empresa para testes multiempresa."""
    emp = Empresa(nome="Empresa Teste 2", ativo=True)
    db.session.add(emp)
    db.session.commit()
    yield emp
    db.session.rollback()


@pytest.fixture
def cliente_empresa1(app, empresa1):
    """Cria um cliente para a empresa 1."""
    from app.models.cliente import Cliente
    cli = Cliente(
        razao_social="Cliente Empresa 1",
        nome_fantasia="Cliente Empresa 1",
        cnpj="12345678000199",
        empresa_id=empresa1.id,
        ativo=True,
    )
    db.session.add(cli)
    db.session.commit()
    yield cli
    db.session.delete(cli)
    db.session.commit()


@pytest.fixture
def cliente_empresa2(app, empresa2):
    """Cria um cliente para a empresa 2."""
    from app.models.cliente import Cliente
    cli = Cliente(
        razao_social="Cliente Empresa 2",
        nome_fantasia="Cliente Empresa 2",
        cnpj="98765432000199",
        empresa_id=empresa2.id,
        ativo=True,
    )
    db.session.add(cli)
    db.session.commit()
    yield cli
    db.session.delete(cli)
    db.session.commit()


@pytest.fixture
def usuario_empresa1(app, empresa1):
    """Cria usuário da empresa 1."""
    papel = Papel(nome="Admin", empresa_id=empresa1.id, ativo=True)
    db.session.add(papel)
    db.session.flush()

    usr = Usuario(
        nome="Usuário Empresa 1",
        email="usuario1@empresa1.com",
        empresa_id=empresa1.id,
        ativo=True,
    )
    usr.set_senha("senha123")
    db.session.add(usr)
    db.session.flush()

    from app.models.usuario import UsuarioPapel
    usuario_papel = UsuarioPapel(
        empresa_id=empresa1.id,
        usuario_id=usr.id,
        papel_id=papel.id,
        ativo=True,
    )
    db.session.add(usuario_papel)
    db.session.commit()
    yield usr
    db.session.delete(usr)
    db.session.commit()


@pytest.fixture
def usuario_empresa2(app, empresa2):
    """Cria usuário da empresa 2."""
    papel = Papel(nome="Admin", empresa_id=empresa2.id, ativo=True)
    db.session.add(papel)
    db.session.flush()

    usr = Usuario(
        nome="Usuário Empresa 2",
        email="usuario2@empresa2.com",
        empresa_id=empresa2.id,
        ativo=True,
    )
    usr.set_senha("senha123")
    db.session.add(usr)
    db.session.flush()

    from app.models.usuario import UsuarioPapel
    usuario_papel = UsuarioPapel(
        empresa_id=empresa2.id,
        usuario_id=usr.id,
        papel_id=papel.id,
        ativo=True,
    )
    db.session.add(usuario_papel)
    db.session.commit()
    yield usr
    db.session.delete(usr)
    db.session.commit()


@pytest.fixture
def obra_empresa1(app, empresa1, usuario_empresa1, cliente_empresa1):
    """Cria obra para empresa 1."""
    obr = Obra(
        nome="Obra Empresa 1",
        empresa_id=empresa1.id,
        status=1,
        criado_por=usuario_empresa1.id,
        cliente_id=cliente_empresa1.id,
    )
    db.session.add(obr)
    db.session.commit()
    yield obr
    RDO.query.filter_by(obra_id=obr.id).delete(synchronize_session=False)
    db.session.delete(obr)
    db.session.commit()


@pytest.fixture
def obra_empresa2(app, empresa2, usuario_empresa2, cliente_empresa2):
    """Cria obra para empresa 2."""
    obr = Obra(
        nome="Obra Empresa 2",
        empresa_id=empresa2.id,
        status=1,
        criado_por=usuario_empresa2.id,
        cliente_id=cliente_empresa2.id,
    )
    db.session.add(obr)
    db.session.commit()
    yield obr
    RDO.query.filter_by(obra_id=obr.id).delete(synchronize_session=False)
    db.session.delete(obr)
    db.session.commit()


@pytest.fixture
def rdo_empresa1(app, empresa1, obra_empresa1):
    """Cria RDO para empresa 1."""
    frente = FrenteTrabalho(
        nome="Frente Empresa 1",
        empresa_id=empresa1.id,
        obra_id=obra_empresa1.id,
    )
    db.session.add(frente)
    db.session.commit()

    rdo = RDO(
        empresa_id=empresa1.id,
        obra_id=obra_empresa1.id,
        frente_trabalho_id=frente.id,
        status='RASCUNHO',
    )
    db.session.add(rdo)
    db.session.commit()
    yield rdo

    db.session.delete(rdo)
    db.session.delete(frente)
    db.session.commit()


@pytest.fixture
def rdo_empresa2(app, empresa2, obra_empresa2):
    """Cria RDO para empresa 2."""
    frente = FrenteTrabalho(
        nome="Frente Empresa 2",
        empresa_id=empresa2.id,
        obra_id=obra_empresa2.id,
    )
    db.session.add(frente)
    db.session.commit()

    rdo = RDO(
        empresa_id=empresa2.id,
        obra_id=obra_empresa2.id,
        frente_trabalho_id=frente.id,
        status='RASCUNHO',
    )
    db.session.add(rdo)
    db.session.commit()
    yield rdo

    db.session.delete(rdo)
    db.session.delete(frente)
    db.session.commit()


@pytest.fixture
def cliente(app, empresa):
    """Cria um cliente base para testes (empresa padrão)."""
    from app.models.cliente import Cliente
    cli = Cliente(
        razao_social="Cliente Teste",
        nome_fantasia="Cliente Teste",
        cnpj="12345678000199",
        empresa_id=empresa.id,
        ativo=True,
    )
    db.session.add(cli)
    db.session.commit()
    yield cli
    db.session.delete(cli)
    db.session.commit()


@pytest.fixture
def obra(app, empresa, usuario, cliente):
    """Cria uma obra para testes."""
    obr = Obra(
        nome="Obra Teste",
        empresa_id=empresa.id,
        status=1,
        criado_por=usuario.id,
        cliente_id=cliente.id,
    )
    db.session.add(obr)
    db.session.commit()
    yield obr
    # Evita que o SQLAlchemy tente desassociar RDOs (setando FK para NULL),
    # pois `rdo.obra_id` e `rdo.frente_trabalho_id` são NOT NULL.
    RDO.query.filter_by(obra_id=obr.id).delete(synchronize_session=False)
    db.session.delete(obr)
    db.session.commit()


@pytest.fixture
def frente_trabalho(app, empresa, obra):
    """Cria uma frente de trabalho para testes."""
    frente = FrenteTrabalho(
        nome="Frente Teste",
        empresa_id=empresa.id,
        obra_id=obra.id,
    )
    db.session.add(frente)
    db.session.commit()
    yield frente
    # Evita FK NOT NULL quando ainda existem RDOs apontando para esta frente.
    RDO.query.filter_by(frente_trabalho_id=frente.id).delete(synchronize_session=False)
    db.session.delete(frente)
    db.session.commit()

