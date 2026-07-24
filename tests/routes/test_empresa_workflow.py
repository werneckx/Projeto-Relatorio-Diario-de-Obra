from app import db
from app.models.configuracao import ConfigDefinicao, EmpresaConfig
from app.models.workflow import WorkflowDefinicao, WorkflowEtapa, WorkflowGrupo
from app.routes.empresa import _workflow_etapa_template_payload


def test_api_workflow_default_aceita_workflow_id(client, empresa, usuario):
    usuario.troca_senha_obrigatoria = False
    db.session.add(usuario)

    workflow_antigo = WorkflowDefinicao(
        empresa_id=empresa.id,
        obra_id=None,
        codigo="WF_ANTIGO",
        nome="Workflow Antigo",
        tipo_fluxo="SIMPLES",
        ativo=True,
    )
    workflow_novo = WorkflowDefinicao(
        empresa_id=empresa.id,
        obra_id=None,
        codigo="WF_NOVO",
        nome="Workflow Novo",
        tipo_fluxo="SEQUENCIAL",
        ativo=True,
    )
    db.session.add_all([
        ConfigDefinicao(
            chave="workflow.default",
            descricao="Workflow padrão da empresa",
            tipo="STRING",
            valor_padrao="WF_ANTIGO",
            is_system=True,
        ),
        workflow_antigo,
        workflow_novo,
    ])
    db.session.flush()
    db.session.add(
        EmpresaConfig(
            empresa_id=empresa.id,
            chave="workflow.default",
            valor=workflow_antigo.codigo,
        )
    )
    db.session.commit()

    with client.session_transaction() as sess:
        sess["user_id"] = usuario.id
        sess["empresa_id"] = empresa.id
        sess["user_role"] = usuario.papel or "Admin"

    resp = client.post(
        "/auth/empresa/api_workflow_default",
        json={"workflow_id": workflow_novo.id},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )

    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["ok"] is True
    assert payload["codigo"] == workflow_novo.codigo

    config = EmpresaConfig.query.filter_by(empresa_id=empresa.id, chave="workflow.default").first()
    assert config.valor == f"id:{workflow_novo.id}"


def test_payload_etapa_usa_ordem_do_grupo_para_diagrama(empresa):
    workflow = WorkflowDefinicao(
        empresa_id=empresa.id,
        obra_id=None,
        codigo="WF_GRUPO_DIAGRAMA",
        nome="Workflow Grupo Diagrama",
        tipo_fluxo="SIMPLES",
        ativo=True,
    )
    db.session.add(workflow)
    db.session.flush()

    grupo = WorkflowGrupo(
        empresa_id=empresa.id,
        workflow_id=workflow.id,
        nome="Etapa 1",
        ordem=1,
        regra_aprovacao="TODOS",
        ativo=True,
    )
    db.session.add(grupo)
    db.session.flush()

    etapa_engenheiro = WorkflowEtapa(
        empresa_id=empresa.id,
        workflow_id=workflow.id,
        nivel=1,
        ordem=1,
        nome="ENGENHEIRO",
        tipo_aprovador="PAPEL",
        grupo_id=grupo.id,
        ativo=True,
    )
    etapa_gestor = WorkflowEtapa(
        empresa_id=empresa.id,
        workflow_id=workflow.id,
        nivel=2,
        ordem=2,
        nome="GESTOR",
        tipo_aprovador="PAPEL",
        grupo_id=grupo.id,
        ativo=True,
    )
    db.session.add_all([etapa_engenheiro, etapa_gestor])
    db.session.flush()

    payload_engenheiro = _workflow_etapa_template_payload(etapa_engenheiro, workflow=workflow, index=0)
    payload_gestor = _workflow_etapa_template_payload(etapa_gestor, workflow=workflow, index=1)

    assert payload_engenheiro["grupo_ordem"] == 1
    assert payload_gestor["grupo_ordem"] == 1
    assert payload_engenheiro["workflow_group"] == 1
    assert payload_gestor["workflow_group"] == 1
