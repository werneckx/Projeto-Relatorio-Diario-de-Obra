from app import db
from app.models.configuracao import ConfigDefinicao, EmpresaConfig
from app.models.workflow import WorkflowDefinicao


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
