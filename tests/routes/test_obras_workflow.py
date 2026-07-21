from app import db
from app.models.cliente import Cliente
from app.models.obra import FrenteTrabalho, Obra
from app.models.rdo import RDO
from app.models.usuario import Papel
from app.models.workflow import WorkflowDefinicao, WorkflowEtapa, WorkflowExecucao


def test_testar_workflow_bloqueia_fallback_sem_usuario_na_obra(client, empresa, papel, usuario):
    usuario.troca_senha_obrigatoria = False
    db.session.add(usuario)

    papel_aprovador = Papel(
        nome="Engenheiro Teste",
        empresa_id=empresa.id,
        ativo=True,
    )
    db.session.add(papel_aprovador)

    cliente = Cliente(
        empresa_id=empresa.id,
        razao_social="Cliente Workflow",
        nome_fantasia="Cliente Workflow",
        cnpj="11222333000144",
        ativo=True,
    )
    db.session.add(cliente)
    db.session.flush()

    obra = Obra(
        empresa_id=empresa.id,
        cliente_id=cliente.id,
        nome="Obra Workflow",
        ativo=True,
        criado_por=usuario.id,
    )
    db.session.add(obra)
    db.session.flush()

    frente = FrenteTrabalho(
        empresa_id=empresa.id,
        obra_id=obra.id,
        nome="Frente Workflow",
        ativo=True,
    )
    db.session.add(frente)

    workflow = WorkflowDefinicao(
        empresa_id=empresa.id,
        nome="Workflow Sem Usuario Vinculado",
        codigo="WF_SEM_USUARIO_VINCULADO",
        tipo_fluxo="SEQUENCIAL",
        ativo=True,
    )
    db.session.add(workflow)
    db.session.flush()

    db.session.add(
        WorkflowEtapa(
            empresa_id=empresa.id,
            workflow_id=workflow.id,
            nivel=1,
            ordem=1,
            nome="Aprovacao por papel",
            tipo_aprovador="PAPEL",
            papel_id=papel_aprovador.id,
            ativo=True,
        )
    )
    db.session.commit()

    with client.session_transaction() as sess:
        sess["user_id"] = usuario.id
        sess["empresa_id"] = empresa.id
        sess["user_role"] = usuario.papel or "Admin"

    resp = client.post(
        f"/auth/obras/{obra.id}/workflow-testar",
        json={"workflow_id": workflow.id},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )

    assert resp.status_code == 400
    payload = resp.get_json()
    assert payload["ok"] is False
    assert "nenhum usuario com este papel esta vinculado a obra" in payload["error"].lower()
    assert "history_html" in payload
    assert RDO.query.filter_by(obra_id=obra.id).count() == 0
    assert WorkflowExecucao.query.filter_by(obra_id=obra.id).count() == 0
