import io
from openpyxl import Workbook
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


def _build_excel_file(content_rows, filename="teste.xlsx"):
    workbook = Workbook()
    sheet = workbook.active
    for row in content_rows:
        sheet.append(row)

    buffer = io.BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    return FileStorage(
        stream=io.BytesIO(buffer.getvalue()),
        filename=filename,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


def test_upload_batch_route_processes_multiple_xlsx_files(client, app, empresa, usuario):
    login_resp = client.post(
        "/auth/login",
        data={"email": usuario.email, "senha": "senha123"},
        follow_redirects=False,
    )
    assert login_resp.status_code == 302

    file1 = _build_excel_file([("Coluna1", "Coluna2"), (1, 2)], filename="planilha1.xlsx")
    file2 = _build_excel_file([("A", "B"), (3, 4)], filename="planilha2.xlsx")

    response = client.post(
        "/auth/arquivos/upload/batch",
        data={"files": [file1, file2]},
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["arquivos_processados"] == 2
    assert payload["sucesso"] == 2
    assert payload["falhas"] == 0
    assert len(payload["detalhes"]) == 2
    assert payload["detalhes"][0]["sucesso"] is True
    assert payload["detalhes"][1]["sucesso"] is True
