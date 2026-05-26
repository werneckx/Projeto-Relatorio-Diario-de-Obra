import pytest


def test_list_equipamentos_smoke_status_200(client, usuario):
    """
    Smoke test isolado do template list_equipamentos.html:
    - garante acesso via login
    - não testa DataTables/export/workflow
    """
    login_resp = client.post(
        "/auth/login",
        data={"email": usuario.email, "senha": "senha123"},
        follow_redirects=False,
    )
    assert login_resp.status_code == 302

    resp = client.get("/auth/lista-equipamentos", follow_redirects=True)
    assert resp.status_code == 200


def test_list_equipamentos_smoke_table_macros_present(client, usuario):
    """
    Valida que a macro enterprise de tabela foi aplicada (wrapper/overflow).
    """
    login_resp = client.post(
        "/auth/login",
        data={"email": usuario.email, "senha": "senha123"},
        follow_redirects=False,
    )
    assert login_resp.status_code == 302

    resp = client.get("/auth/lista-equipamentos", follow_redirects=True)
    assert resp.status_code == 200

    body = resp.data.decode("utf-8", errors="ignore").lower()
    assert "overflow-x-auto" in body

