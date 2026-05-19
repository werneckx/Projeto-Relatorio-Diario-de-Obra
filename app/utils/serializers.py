from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict


SENSITIVE_FIELDS = {
    "password",
    "senha",
    "token",
    "jwt",
    "access_token",
    "refresh_token",
    "cookie",
    "session",
    "session_id",
    "authorization",
    "secret",
    "secrets",
}


def _is_scalar(value: Any) -> bool:
    return isinstance(value, (str, int, float, bool, type(None)))


def _to_utc_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


def safe_model_to_dict(model: Any) -> Dict[str, Any]:
    """Serialização segura para auditoria.

    Regras:
    - ignora campos privados
    - ignora relacionamentos lazy (via tentativa de acesso controlada)
    - ignora binários/blobs
    - sanitiza campos sensíveis
    - datetime -> ISO8601 UTC
    """

    if model is None:
        return {}

    # SQLAlchemy models: preferir __table__.columns se existir
    cols = getattr(getattr(model, "__table__", None), "columns", None)
    result: Dict[str, Any] = {}

    if cols is not None:
        for col in cols:
            key = getattr(col, "key", None) or str(col)
            if not key or key.startswith("_"):
                continue

            lk = key.lower()
            if lk in SENSITIVE_FIELDS:
                continue

            val = getattr(model, key, None)

            if isinstance(val, datetime):
                result[key] = _to_utc_iso(val)
            elif isinstance(val, (bytes, bytearray)):
                continue
            elif _is_scalar(val) or isinstance(val, dict) or isinstance(val, list):
                result[key] = val
            else:
                # evita objetos complexos
                try:
                    # se for JSON serializável (dict/list/scalar) mantém; caso contrário, string curta
                    if hasattr(val, "isoformat"):
                        result[key] = val.isoformat()
                    else:
                        # fallback seguro
                        result[key] = str(val)
                except Exception:
                    continue

        return result

    # Fallback genérico
    for key, val in vars(model).items():
        if key.startswith("_"):
            continue
        lk = key.lower()
        if lk in SENSITIVE_FIELDS:
            continue

        if isinstance(val, datetime):
            result[key] = _to_utc_iso(val)
        elif isinstance(val, (bytes, bytearray)):
            continue
        elif _is_scalar(val) or isinstance(val, (dict, list)):
            result[key] = val

    return result

