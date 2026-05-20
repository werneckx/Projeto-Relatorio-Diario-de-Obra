import io
from werkzeug.datastructures import FileStorage
from app.models.arquivo import Arquivo
from app.services.arquivo_service import ArquivoService


def test_save_local_file_creates_arquivo_record(app, db_session, empresa, usuario):
    payload = b"conteudo de teste"
    file_storage = FileStorage(
        stream=io.BytesIO(payload),
        filename="teste.txt",
        content_type="text/plain",
    )

    arquivo = ArquivoService.save_local_file(
        file_storage=file_storage,
        empresa_id=empresa.id,
        usuario_id=usuario.id,
        categoria="DOCUMENTO",
        entidade="TESTE",
        entidade_id=1,
        obra_id=None,
        rdo_id=None,
        publico=False,
        subfolder="testes",
    )
    db_session.commit()

    assert arquivo.id is not None
    assert arquivo.nome_original == "teste.txt"
    assert arquivo.nome_armazenado.endswith("_teste.txt")
    assert arquivo.mime_type == "text/plain"
    assert arquivo.tamanho_bytes == len(payload)
    assert arquivo.hash_arquivo is not None and len(arquivo.hash_arquivo) == 64
    assert arquivo.storage_provider == "LOCAL"
    assert arquivo.storage_path.startswith("testes/")
    assert arquivo.ativo is True

    caminho = ArquivoService.get_local_file_path(arquivo)
    assert caminho.endswith(arquivo.nome_armazenado)
    with open(caminho, "rb") as f:
        assert f.read() == payload


def test_download_arquivo_route_returns_file(client, app, db_session, empresa, usuario):
    # Log in the user
    login_resp = client.post(
        "/auth/login",
        data={"email": usuario.email, "senha": "senha123"},
        follow_redirects=False,
    )
    assert login_resp.status_code == 302

    payload = b"conteudo de download"
    file_storage = FileStorage(
        stream=io.BytesIO(payload),
        filename="download.txt",
        content_type="text/plain",
    )

    arquivo = ArquivoService.save_local_file(
        file_storage=file_storage,
        empresa_id=empresa.id,
        usuario_id=usuario.id,
        categoria="DOCUMENTO",
        entidade="TESTE",
        entidade_id=2,
        obra_id=None,
        rdo_id=None,
        publico=False,
        subfolder="testes",
    )
    db_session.commit()

    response = client.get(f"/auth/arquivos/{arquivo.id}/download")
    assert response.status_code == 200
    assert response.data == payload
    assert response.headers["Content-Disposition"].startswith("attachment;")
    assert "download.txt" in response.headers["Content-Disposition"]
    assert response.headers["Content-Type"].startswith("text/plain")
