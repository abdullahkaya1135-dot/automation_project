from datetime import UTC, datetime
from datetime import date as Date
from typing import Any

from ...core.config import Settings
from ...domain import shifts
from ...domain.request_values import required_text, validation_error


def amount_control_record_date(value: Any) -> str:
    text = required_text(value, "tarih", 10)
    try:
        return Date.fromisoformat(text).isoformat()
    except ValueError as exc:
        raise validation_error("tarih YYYY-AA-GG formatinda olmalidir.") from exc


def amount_control_shift(value: Any) -> str:
    text = required_text(value, "vardiya", 16)
    if text in shifts.SHIFT_OPTIONS:
        return text
    raise validation_error(
        "vardiya sunlardan biri olmalidir: " + ", ".join(shifts.SHIFT_OPTIONS)
    )


def amount_control_quantity(value: Any) -> int:
    if isinstance(value, bool):
        raise validation_error("uretilen miktar tam sayi olmalidir.")
    try:
        quantity = int(value)
    except (TypeError, ValueError) as exc:
        raise validation_error("uretilen miktar tam sayi olmalidir.") from exc
    if quantity < 0:
        raise validation_error("uretilen miktar 0 veya daha buyuk olmalidir.")
    return quantity


def amount_control_datetime(
    value: Any,
    settings: Settings,
    field_name: str,
) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise validation_error(f"{field_name} ISO tarih/saat degeri olmalidir.") from exc

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=shifts.request_timezone(settings))
    return parsed.astimezone(UTC).replace(tzinfo=None)


def amount_control_breakdown_times(
    stopped_at: Any,
    resumed_at: Any,
    settings: Settings,
) -> tuple[datetime | None, datetime | None]:
    stopped = amount_control_datetime(stopped_at, settings, "durus baslangici")
    resumed = amount_control_datetime(resumed_at, settings, "durus bitisi")
    if stopped is not None and resumed is not None and resumed < stopped:
        raise validation_error("durus bitisi durus baslangicindan once olamaz.")
    return stopped, resumed
