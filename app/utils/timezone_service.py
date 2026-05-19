from __future__ import annotations

from datetime import datetime
from typing import Optional

from flask import has_request_context, session
from flask_login import current_user

from app.services.config_service import ConfigService
from app.utils.datetime_utils import convert_utc_to_tz


def to_local_time(
    dt_naive_utc: Optional[datetime],
    *,
    empresa_id: Optional[int] = None,
    obra_id: Optional[int] = None,
) -> Optional[datetime]:
    if dt_naive_utc is None:
        return None

    resolved_empresa_id = empresa_id

    if resolved_empresa_id is None:
        try:
            if getattr(current_user, "is_authenticated", False):
                resolved_empresa_id = getattr(current_user, "empresa_id", None)
        except Exception:
            resolved_empresa_id = None

    if resolved_empresa_id is None and has_request_context():
        resolved_empresa_id = session.get("empresa_id")

    if resolved_empresa_id is None:
        tz_name = "UTC"
    else:
        tz_name = ConfigService.obter_timezone(empresa_id=resolved_empresa_id, obra_id=obra_id)

    return convert_utc_to_tz(dt_naive_utc, tz_name)


def fmt_dt(
    dt_naive_utc: Optional[datetime],
    *,
    empresa_id: Optional[int] = None,
    obra_id: Optional[int] = None,
    fmt: str = "%d/%m/%Y %H:%M",
) -> str:
    """Formata datetime (UTC naive) no timezone local resolvido (empresa/obra)."""

    dt_local = to_local_time(dt_naive_utc, empresa_id=empresa_id, obra_id=obra_id)
    if dt_local is None:
        return ""
    return dt_local.strftime(fmt)
