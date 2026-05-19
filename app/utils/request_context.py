from __future__ import annotations

from typing import Any, Dict, Optional

from flask import has_request_context, request
from flask_login import current_user


def _safe_get_user_id() -> Optional[int]:
    try:
        # current_user pode ser AnonymousUser
        if getattr(current_user, "is_authenticated", False):
            return getattr(current_user, "id", None)
    except Exception:
        return None
    return None


def _safe_get_empresa_id() -> Optional[int]:
    try:
        if getattr(current_user, "is_authenticated", False):
            return getattr(current_user, "empresa_id", None)
    except Exception:
        return None
    return None


def capturar_request_context() -> Dict[str, Any]:
    """Captura contexto HTTP e identidade com fallback seguro.

    Não lança exception quando não há request context (background jobs, testes, etc.).
    """

    ctx: Dict[str, Any] = {
        "ip": None,
        "user_agent": None,
        "endpoint": None,
        "method": None,
        "usuario_id": _safe_get_user_id(),
        "empresa_id": _safe_get_empresa_id(),
    }

    try:
        if has_request_context():
            # IP real mesmo atrás de proxy
            xff = request.headers.get("X-Forwarded-For")
            if xff:
                # pega primeiro IP
                ctx["ip"] = xff.split(",")[0].strip() if "," in xff else xff.strip()
            else:
                ctx["ip"] = request.remote_addr

            ctx["user_agent"] = request.headers.get("User-Agent")
            ctx["endpoint"] = request.endpoint
            ctx["method"] = request.method
    except Exception:
        # fallback: mantém None
        pass

    return ctx

