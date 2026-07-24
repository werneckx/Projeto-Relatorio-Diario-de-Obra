import json

from app import db
from app.models.cliente import Cliente
from app.models.configuracao import ObraConfig
from app.models.obra import FrenteTrabalho, Obra, ObraUsuario
from app.models.rdo import RDO
from app.models.usuario import Papel
from app.models.workflow import WorkflowDefinicao, WorkflowEtapa, WorkflowExecucao, WorkflowGrupo
from app.services.workflow_service import WorkflowService


def test_criar_obra_salva_workflow_individual_como_rascunho(client, empresa, usuario):
    usuario.troca_senha_obrigatoria = False
    db.session.add(usuario)

    papel_aprovador = Papel(
        nome="Engenheiro Obra Nova",
        empresa_id=empresa.id,
        ativo=True,
    )
    cliente = Cliente(
        empresa_id=empresa.id,
        razao_social="Cliente Obra Nova",
        nome_fantasia="Cliente Obra Nova",
        cnpj="22333444000155",
        ativo=True,
    )
    workflow = WorkflowDefinicao(
        empresa_id=empresa.id,
        nome="Workflow Obra Nova",
        codigo="WF_OBRA_NOVA",
        tipo_fluxo="SEQUENCIAL",
        ativo=True,
    )
    db.session.add_all([papel_aprovador, cliente, workflow])
    db.session.commit()

    with client.session_transaction() as sess:
        sess["user_id"] = usuario.id
        sess["empresa_id"] = empresa.id
        sess["user_role"] = usuario.papel or "Admin"

    resp = client.post(
        "/auth/obras/salvar",
        data={
            "nome": "Obra Nova Sem Workflow Individual",
            "cliente_id": str(cliente.id),
            "cnpj_obra": "99888777000166",
            "workflow_selecionado_id": str(workflow.id),
            "workflow_config_json": json.dumps({
                "workflow_id": workflow.id,
                "customizado": True,
                "aprovacao_paralela": False,
                "assignments": {},
                "custom_stages": [
                    {
                        "nome": "Etapa 1",
                        "tipo_aprovador": "PAPEL",
                        "papel_id": papel_aprovador.id,
                        "usuario_aprovador_id": None,
                        "responsavel_usuario_id": None,
                        "workflow_group": "1",
                        "grupo_paralelo": None,
                        "regra_etapa": "TODOS",
                    }
                ],
            }),
        },
        follow_redirects=False,
    )

    assert resp.status_code == 302
    obra = Obra.query.filter_by(nome="Obra Nova Sem Workflow Individual", empresa_id=empresa.id).first()
    assert obra
    workflow_obra = WorkflowDefinicao.query.filter_by(empresa_id=empresa.id, obra_id=obra.id, ativo=True).first()
    assert workflow_obra
    etapa = WorkflowEtapa.query.filter_by(workflow_id=workflow_obra.id).first()
    assert etapa
    assert etapa.papel_id == papel_aprovador.id
    assert WorkflowGrupo.query.filter_by(workflow_id=workflow_obra.id, ativo=True).count() == 1
    assert WorkflowExecucao.query.filter_by(empresa_id=empresa.id).count() == 0
    assert ObraConfig.query.filter_by(
        empresa_id=empresa.id,
        obra_id=obra.id,
        chave=WorkflowService.WORKFLOW_ASSIGNMENTS_CONFIG_KEY,
    ).first() is None
    preview = WorkflowService.construir_preview_workflow_obra(
        empresa_id=empresa.id,
        obra_id=obra.id,
        workflow_id=workflow_obra.id,
    )
    assert len(preview["etapas"]) == 1
    assert preview["etapas"][0]["papel_id"] == papel_aprovador.id

    ObraConfig.query.filter_by(empresa_id=empresa.id, obra_id=obra.id).delete(synchronize_session=False)
    ObraUsuario.query.filter_by(empresa_id=empresa.id, obra_id=obra.id).delete(synchronize_session=False)
    WorkflowEtapa.query.filter_by(workflow_id=workflow_obra.id).delete(synchronize_session=False)
    WorkflowGrupo.query.filter_by(workflow_id=workflow_obra.id).delete(synchronize_session=False)
    db.session.delete(workflow_obra)
    db.session.delete(obra)
    db.session.delete(workflow)
    db.session.delete(cliente)
    db.session.delete(papel_aprovador)
    db.session.commit()


def test_criar_obra_com_workflow_padrao_mantem_heranca(client, empresa, usuario):
    usuario.troca_senha_obrigatoria = False
    db.session.add(usuario)

    cliente = Cliente(
        empresa_id=empresa.id,
        razao_social="Cliente Heranca Workflow",
        nome_fantasia="Cliente Heranca Workflow",
        cnpj="22333444000156",
        ativo=True,
    )
    workflow = WorkflowDefinicao(
        empresa_id=empresa.id,
        nome="Workflow Herdado",
        codigo="WF_HERDADO",
        tipo_fluxo="SEQUENCIAL",
        ativo=True,
    )
    db.session.add_all([cliente, workflow])
    db.session.flush()
    db.session.add(
        WorkflowEtapa(
            empresa_id=empresa.id,
            workflow_id=workflow.id,
            nivel=1,
            ordem=1,
            nome="Etapa herdada",
            tipo_aprovador="USUARIO",
            usuario_aprovador_id=usuario.id,
            ativo=True,
        )
    )
    db.session.commit()

    with client.session_transaction() as sess:
        sess["user_id"] = usuario.id
        sess["empresa_id"] = empresa.id
        sess["user_role"] = usuario.papel or "Admin"

    resp = client.post(
        "/auth/obras/salvar",
        data={
            "nome": "Obra Nova Herdando Workflow",
            "cliente_id": str(cliente.id),
            "cnpj_obra": "99888777000167",
            "workflow_selecionado_id": str(workflow.id),
            "workflow_config_json": json.dumps({
                "workflow_id": workflow.id,
                "customizado": False,
                "aprovacao_paralela": False,
                "assignments": {},
                "custom_stages": [],
            }),
        },
        follow_redirects=False,
    )

    assert resp.status_code == 302
    obra = Obra.query.filter_by(nome="Obra Nova Herdando Workflow", empresa_id=empresa.id).first()
    assert obra
    assert WorkflowDefinicao.query.filter_by(empresa_id=empresa.id, obra_id=obra.id, ativo=True).first() is None
    assert ObraConfig.query.filter_by(
        empresa_id=empresa.id,
        obra_id=obra.id,
        chave=WorkflowService.WORKFLOW_DEFAULT_CONFIG_KEY,
    ).first().valor == f"id:{workflow.id}"

    ObraConfig.query.filter_by(empresa_id=empresa.id, obra_id=obra.id).delete(synchronize_session=False)
    ObraUsuario.query.filter_by(empresa_id=empresa.id, obra_id=obra.id).delete(synchronize_session=False)
    db.session.delete(obra)
    WorkflowEtapa.query.filter_by(workflow_id=workflow.id).delete(synchronize_session=False)
    db.session.delete(workflow)
    db.session.delete(cliente)
    db.session.commit()


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
