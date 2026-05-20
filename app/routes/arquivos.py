import os
from app.routes.auth_common import *
from app.services.arquivo_service import ArquivoService
from app.models.arquivo import Arquivo


@auth_bp.post("/arquivos/upload")
@login_required
def upload_arquivo():
    arquivo_enviado = request.files.get("arquivo")
    if not arquivo_enviado or not arquivo_enviado.filename:
        flash("Selecione um arquivo válido para envio.", "danger")
        return redirect(request.referrer or url_for("auth.inicio"))

    entidade = request.form.get("entidade")
    entidade_id = request.form.get("entidade_id")
    obra_id = request.form.get("obra_id")
    rdo_id = request.form.get("rdo_id")
    categoria = request.form.get("categoria") or "DOCUMENTO"
    publico = request.form.get("publico") in ["1", "true", "True", "on"]

    try:
        entidade_id_int = int(entidade_id) if entidade_id and entidade_id.isdigit() else None
        obra_id_int = int(obra_id) if obra_id and obra_id.isdigit() else None
        rdo_id_int = int(rdo_id) if rdo_id and rdo_id.isdigit() else None

        arquivo = ArquivoService.save_local_file(
            file_storage=arquivo_enviado,
            empresa_id=session.get("empresa_id"),
            usuario_id=session.get("user_id"),
            categoria=categoria,
            entidade=entidade,
            entidade_id=entidade_id_int,
            obra_id=obra_id_int,
            rdo_id=rdo_id_int,
            publico=publico,
            subfolder="documentos",
        )
        db.session.commit()
        flash("Arquivo enviado e registrado com sucesso.", "success")
    except Exception as exc:
        db.session.rollback()
        flash(f"Falha ao salvar arquivo: {str(exc)}", "danger")

    return redirect(request.referrer or url_for("auth.inicio"))


@auth_bp.get("/arquivos/<int:arquivo_id>/download")
@login_required
def download_arquivo(arquivo_id):
    arquivo = Arquivo.query.filter_by(id=arquivo_id, empresa_id=session.get("empresa_id"), ativo=True).first_or_404()

    if arquivo.storage_provider != ArquivoService.LOCAL_PROVIDER:
        abort(501)

    caminho_local = ArquivoService.get_local_file_path(arquivo)
    if not os.path.exists(caminho_local):
        abort(404)

    return send_file(
        caminho_local,
        mimetype=arquivo.mime_type or "application/octet-stream",
        as_attachment=True,
        download_name=arquivo.nome_original,
    )
