import pytest


def test_form_obra_smoke_status_200(client, usuario):
    """
    Smoke test isolado do template form_obra.html:
    - garante acesso via login
    - nÃ£o testa workflow/RBAC/DB profunda
    """
    login_resp = client.post(
        "/auth/login",
        data={"email": usuario.email, "senha": "senha123"},
        follow_redirects=False,
    )
    assert login_resp.status_code == 302

    resp = client.get("/auth/criar-obra", follow_redirects=True)
    assert resp.status_code == 200


def test_form_obra_smoke_flash_messages_present(client, usuario):
    """
    Valida que a partial de flash foi incluÃ­da no form_obra.html.
    """
    login_resp = client.post(
        "/auth/login",
        data={"email": usuario.email, "senha": "senha123"},
        follow_redirects=False,
    )
    assert login_resp.status_code == 302

    resp = client.get("/auth/criar-obra", follow_redirects=True)
    assert resp.status_code == 200
    body = resp.data.decode("utf-8", errors="ignore").lower()
    assert "flash" in body

