from __future__ import annotations

from datetime import datetime, timezone, tzinfo

try:
    from zoneinfo import ZoneInfo
    from zoneinfo import ZoneInfoNotFoundError
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore
    ZoneInfoNotFoundError = Exception  # type: ignore


UTC_TZ: tzinfo = timezone.utc


def utcnow_naive() -> datetime:
    """Agora em UTC sem tzinfo.

    Observação:
    - O schema atual usa colunas `DATETIME`/`DateTime` sem timezone.
    - Para arquitetura multiempresa, persistimos em UTC e convertemos na camada de aplicação.
    """

    return datetime.now(timezone.utc).replace(tzinfo=None)


def as_aware_utc(dt_naive_utc: datetime) -> datetime:
    """Interpreta um datetime naive como UTC e retorna aware."""

    return dt_naive_utc.replace(tzinfo=UTC_TZ)


def convert_utc_to_tz(dt_naive_utc: datetime, tz_name: str) -> datetime:
    """Converte um datetime naive (UTC) para um datetime aware no fuso alvo."""

    # Windows frequentemente não tem tzdata embutido; ZoneInfo pode falhar.
    if ZoneInfo is None:
        return as_aware_utc(dt_naive_utc)

    try:
        tz = ZoneInfo(tz_name or "UTC")
    except ZoneInfoNotFoundError:
        # Fallback seguro: mantém em UTC se o timezone IANA não estiver disponível.
        return as_aware_utc(dt_naive_utc)

    return as_aware_utc(dt_naive_utc).astimezone(tz)
