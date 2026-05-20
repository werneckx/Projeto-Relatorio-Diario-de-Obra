from flask import Blueprint, jsonify, session, abort
from flask_login import login_required
from app.services.notificacao_service import NotificacaoService
from app.services.auditoria_service import AuditoriaService

notificacoes_bp = Blueprint("notificacoes", __name__)


@notificacoes_bp.route("/notificacoes/<int:id>/lida", methods=["POST"])
@login_required
def marcar_lida(id):
    """Marca uma notificação específica como lida, retornando status JSON ou 404."""
    usuario_id = session.get("user_id")
    if not usuario_id:
        return jsonify({"error": "Usuário não autenticado"}), 401

    notificacao = NotificacaoService.marcar_como_lida(id, usuario_id)
    if not notificacao:
        return jsonify({"error": "Notificação não encontrada ou acesso não autorizado"}), 404

    # Registro de auditoria racionalizada como UPDATE de estado
    AuditoriaService.registrar_auditoria_entidade(
        acao="UPDATE",
        entidade="NOTIFICACAO",
        entidade_id=notificacao.id,
        antes={"lida": False},
        depois={"lida": True},
        payload={"descricao": "Notificação marcada como lida"}
    )

    # Após marcar como lida, recalcula total de não lidas
    total_nao_lidas = NotificacaoService.listar_nao_lidas(usuario_id, session.get('empresa_id'))
    total = len(total_nao_lidas)
    return jsonify({"success": True, "nao_lidas": total})


@notificacoes_bp.app_context_processor
def inject_notifications():
    """Injeta até 10 notificações não lidas no contexto de renderização global das páginas."""
    if "user_id" not in session:
        return {}

    nao_lidas = NotificacaoService.listar_nao_lidas(
        session.get("user_id"),
        session.get("empresa_id"),
        limit=10
    )

    return {
        "notifications": {
            "nao_lidas": nao_lidas
        }
    }
