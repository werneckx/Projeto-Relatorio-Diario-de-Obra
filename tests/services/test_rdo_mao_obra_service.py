import pytest

from app import db
from app.models.obra import FrenteColaborador
from app.models.rdo import RDO, RDOMaoObra
from app.models.usuario import Colaborador


def _cria_colaborador(empresa_id: int, nome: str):
    return Colaborador(
        empresa_id=empresa_id,
        nome=nome,
        ativo=True,
    )


def test_preencher_por_frente_cria_linhas(empresa, obra, frente_trabalho):
    from app.services.rdo_mao_obra_service import RDOMaoObraService

    colab1 = _cria_colaborador(empresa.id, "João")
    colab2 = _cria_colaborador(empresa.id, "Pedro")
    db.session.add_all([colab1, colab2])
    db.session.flush()

    fc1 = FrenteColaborador(
        empresa_id=empresa.id,
        frente_id=frente_trabalho.id,
        colaborador_id=colab1.id,
        funcao_id=None,
        ativo=True,
    )
    fc2 = FrenteColaborador(
        empresa_id=empresa.id,
        frente_id=frente_trabalho.id,
        colaborador_id=colab2.id,
        funcao_id=None,
        ativo=True,
    )
    db.session.add_all([fc1, fc2])
    db.session.flush()

    rdo = RDO(
        empresa_id=empresa.id,
        obra_id=obra.id,
        frente_trabalho_id=frente_trabalho.id,
        status="RASCUNHO",
    )
    db.session.add(rdo)
    db.session.flush()

    criados = RDOMaoObraService.preencher_por_frente(
        rdo_id=rdo.id,
        frente_id=frente_trabalho.id,
    )

    assert len(criados) == 2
    assert RDOMaoObra.query.filter_by(rdo_id=rdo.id).count() == 2
    assert {m.colaborador_id for m in RDOMaoObra.query.filter_by(rdo_id=rdo.id).all()} == {
        colab1.id,
        colab2.id,
    }


def test_preencher_por_frente_idempotente_por_colaborador(empresa, obra, frente_trabalho):
    from app.services.rdo_mao_obra_service import RDOMaoObraService

    colab1 = _cria_colaborador(empresa.id, "João")
    db.session.add(colab1)
    db.session.flush()

    fc1 = FrenteColaborador(
        empresa_id=empresa.id,
        frente_id=frente_trabalho.id,
        colaborador_id=colab1.id,
        funcao_id=None,
        ativo=True,
    )
    db.session.add(fc1)
    db.session.flush()

    rdo = RDO(
        empresa_id=empresa.id,
        obra_id=obra.id,
        frente_trabalho_id=frente_trabalho.id,
        status="RASCUNHO",
    )
    db.session.add(rdo)
    db.session.flush()

    RDOMaoObraService.preencher_por_frente(rdo_id=rdo.id, frente_id=frente_trabalho.id)
    db.session.flush()

    # chamada repetida não deve duplicar
    RDOMaoObraService.preencher_por_frente(rdo_id=rdo.id, frente_id=frente_trabalho.id)
    db.session.flush()

    assert RDOMaoObra.query.filter_by(rdo_id=rdo.id).count() == 1
    assert RDOMaoObra.query.filter_by(rdo_id=rdo.id, colaborador_id=colab1.id).count() == 1
