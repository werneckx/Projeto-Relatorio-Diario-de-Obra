import pytest

from app import db
from app.models.obra import FrenteTrabalho, FrenteColaborador
from app.models.rdo import RDO, RDOMaoObra
from app.models.usuario import Colaborador, Usuario
from app.models.empresa import Empresa


def test_gerar_rdo_preenche_mao_de_obra_por_frente(
    app, client, empresa, usuario, obra, frente_trabalho
):
    # Observação:
    # - Este teste exercita apenas o endpoint /gerar-rdo.
    # - O app/config do teste deve fornecer login/autenticação via fixtures (client, usuario_empresa1).
    #
    # Se as fixtures do projeto não autenticarem automaticamente,
    # o teste falhará por 401/302 e deve ser ajustado com as utilidades existentes no suite.

    colab = Colaborador(empresa_id=empresa.id, nome="João", ativo=True)
    db.session.add(colab)
    db.session.flush()

    fc = FrenteColaborador(
        empresa_id=empresa.id,
        frente_id=frente_trabalho.id,
        colaborador_id=colab.id,
        funcao_id=None,
        ativo=True,
    )
    db.session.add(fc)
    db.session.flush()

    payload = {
        "obra_id": str(obra.id),
        "frente_trabalho_id": str(frente_trabalho.id),
        "data_rdo": "2026-01-01",
        "climas_manha": "",
        "climas_tarde": "",
        "comentarios_gerais": "Teste",
        "hora_entrada": "",
        "hora_saida": "",
        "intervalo_entrada": "",
        "intervalo_saida": "",
        # nada adicional de mao obra: o service deve preencher automaticamente
    }

    with client.session_transaction() as sess:
        sess["user_id"] = usuario.id
        sess["empresa_id"] = empresa.id
        sess["user_role"] = usuario.papel or "Admin"

    resp = client.post("/auth/gerar-rdo", data=payload, follow_redirects=False)
    assert resp.status_code in (200, 302)

    # Encontrar o RDO criado: o endpoint redireciona para visualizar; mas aqui validamos o banco.
    # Como não temos garantia de qual RDO foi criado, usamos os filhos como prova.
    mao = RDOMaoObra.query.filter(RDOMaoObra.colaborador_id == colab.id).all()
    assert len(mao) >= 1
