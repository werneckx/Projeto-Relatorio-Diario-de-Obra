import hashlib
import mimetypes
import os
from datetime import datetime
from flask import current_app
from werkzeug.utils import secure_filename

from app import db
from app.models.arquivo import Arquivo


class ArquivoService:
    LOCAL_PROVIDER = "LOCAL"
    SUPPORTED_PROVIDERS = {"LOCAL", "S3", "AZURE", "MINIO"}
    DEFAULT_CATEGORY = "ANEXO"
    DEFAULT_SUBFOLDER = "arquivos"

    @classmethod
    def get_local_upload_root(cls):
        upload_root = current_app.config.get("UPLOAD_FOLDER")
        if not upload_root:
            upload_root = os.path.join(current_app.root_path, "static", "uploads")
        return upload_root

    @classmethod
    def get_local_storage_folder(cls, empresa_id=None, subfolder=None):
        folder_parts = [cls.get_local_upload_root()]
        if subfolder:
            folder_parts.append(subfolder)
        if empresa_id is not None:
            folder_parts.append(str(empresa_id))
        storage_folder = os.path.join(*folder_parts)
        os.makedirs(storage_folder, exist_ok=True)
        return storage_folder

    @classmethod
    def compute_hash(cls, data: bytes):
        return hashlib.sha256(data).hexdigest()

    @classmethod
    def guess_mime_type(cls, filename, mimetype=None):
        if mimetype:
            return mimetype
        guess, _ = mimetypes.guess_type(filename)
        return guess or "application/octet-stream"

    @classmethod
    def save_local_file(
        cls,
        file_storage=None,
        raw_bytes=None,
        filename=None,
        content_type=None,
        empresa_id=None,
        usuario_id=None,
        categoria=None,
        entidade=None,
        entidade_id=None,
        obra_id=None,
        rdo_id=None,
        publico=False,
        subfolder=None,
    ):
        if raw_bytes is None:
            if file_storage is None:
                raise ValueError("Arquivo inválido para salvar.")
            if not getattr(file_storage, "filename", None):
                raise ValueError("Arquivo inválido para salvar.")
            filename = secure_filename(file_storage.filename)
            if not filename:
                raise ValueError("Nome de arquivo inválido.")
            file_storage.stream.seek(0)
            raw_bytes = file_storage.read()
            content_type = content_type or getattr(file_storage, "mimetype", None)

        if raw_bytes is None or filename is None:
            raise ValueError("Arquivo ou conteúdo ausente.")

        filename = secure_filename(filename)
        if not filename:
            raise ValueError("Nome de arquivo inválido.")

        nome_armazenado = f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S%f')}_{filename}"
        folder = cls.get_local_storage_folder(empresa_id=empresa_id, subfolder=subfolder or cls.DEFAULT_SUBFOLDER)
        caminho_absoluto = os.path.join(folder, nome_armazenado)

        with open(caminho_absoluto, "wb") as f:
            f.write(raw_bytes)

        hash_arquivo = cls.compute_hash(raw_bytes)
        mime_type = cls.guess_mime_type(filename, content_type)
        storage_path_parts = [subfolder or cls.DEFAULT_SUBFOLDER]
        if empresa_id is not None:
            storage_path_parts.append(str(empresa_id))
        storage_path_parts.append(nome_armazenado)
        storage_path = os.path.join(*storage_path_parts).replace("\\", "/")

        arquivo = Arquivo(
            empresa_id=empresa_id,
            obra_id=obra_id,
            rdo_id=rdo_id,
            entidade=entidade,
            entidade_id=entidade_id,
            categoria=categoria or cls.DEFAULT_CATEGORY,
            nome_original=filename,
            nome_armazenado=nome_armazenado,
            mime_type=mime_type,
            tamanho_bytes=len(raw_bytes),
            storage_provider=cls.LOCAL_PROVIDER,
            storage_path=storage_path,
            hash_arquivo=hash_arquivo,
            publico=publico,
            criado_por=usuario_id,
            modificado_por=usuario_id,
        )
        db.session.add(arquivo)
        return arquivo

    @classmethod
    def get_local_file_path(cls, arquivo: Arquivo):
        if arquivo.storage_provider != cls.LOCAL_PROVIDER:
            raise NotImplementedError("Provider de armazenamento não suportado.")
        upload_root = cls.get_local_upload_root()
        return os.path.join(upload_root, arquivo.storage_path)
