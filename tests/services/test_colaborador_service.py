import pytest

from app import db
from app.models.usuario import Colaborador, Usuario, UsuarioPapel, Papel
from app.services.colaborador_service import ColaboradorService


def _cria_papel_operador(empresa_id=None):
    # papel já existente no banco pode existir no fixture; garantimos criação mínima se faltar
    from app.routes.auth_common import ROLE_OPERADOR

    papel = Papel.query.filter_by(ativo=True, nome=ROLE_OPERADOR).first()
    if papel:
        return papel

    papel = Papel(
        empresa_id=empresa_id,
        nome=ROLE_OPERADOR,
        descricao="",
        is_system=False,
        ativo=True,
    )
    db.session.add(papel)
    db.session.flush()
    return papel


def test_cria_colaborador_sem_usuario(empresa):
    dados = {
        "empresa_id": empresa.id,
        "nome": "João",
        "ativo": True,
    }

    colaborador = ColaboradorService.criar_colaborador(dados=dados, criar_acesso=False)

    assert colaborador.id is not None
    assert Colaborador.query.filter_by(id=colaborador.id).count() == 1
    assert Usuario.query.filter_by(colaborador_id=colaborador.id).count() == 0


def test_cria_colaborador_com_usuario(empresa):
    _cria_papel_operador(empresa.id)

    dados = {
        "empresa_id": empresa.id,
        "nome": "Pedro",
        "ativo": True,
        "email": "pedro@test.com",
        "senha": "123456",
    }

    colaborador = ColaboradorService.criar_colaborador(dados=dados, criar_acesso=True)

    usuario = Usuario.query.filter_by(colaborador_id=colaborador.id, email=dados["email"]).first()
    assert usuario is not None

    assert UsuarioPapel.query.filter_by(usuario_id=usuario.id).count() == 1
    # atributo dinâmico deve estar setado
    assert getattr(colaborador, "eh_usuario", False) is True


def test_erro_quando_papel_operador_nao_existe(empresa):
    # garante que não existe
    from app.routes.auth_common import ROLE_OPERADOR
    Papel.query.filter_by(ativo=True, nome=ROLE_OPERADOR).delete(synchronize_session=False)
    db.session.flush()

    dados = {
        "empresa_id": empresa.id,
        "nome": "Ana",
        "ativo": True,
        "email": "ana@test.com",
        "senha": "123456",
    }

    with pytest.raises(ValueError) as exc:
        ColaboradorService.criar_colaborador(dados=dados, criar_acesso=True)

    assert "OPERADOR" in str(exc.value)


def test_rollback_quando_criacao_usuario_falha(empresa):
    _cria_papel_operador(empresa.id)

    # força falha: passar senha None (Usuario.set_senha vai exigir, e model pode quebrar)
    dados = {
        "empresa_id": empresa.id,
        "nome": "Rafa",
        "ativo": True,
        "email": "rafa@test.com",
        "senha": None,
    }

    with pytest.raises(ValueError):
        ColaboradorService.criar_colaborador(dados=dados, criar_acesso=True)

    # Colaborador não deve ter sido persistido
    assert Colaborador.query.filter_by(empresa_id=empresa.id, nome="Rafa").count() == 0

