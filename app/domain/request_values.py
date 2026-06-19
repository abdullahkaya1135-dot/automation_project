from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status

from ..core.config import Settings
from ..models import SYNC_STATUSES
from . import shifts


def validation_error(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=message,
    )


def validate_sync_status(sync_status: str | None) -> None:
    if sync_status is not None and sync_status not in SYNC_STATUSES:
        raise validation_error(
            "sync_status şunlardan biri olmalıdır: " + ", ".join(SYNC_STATUSES)
        )


def required_text(value: Any, field_name: str, max_length: int) -> str:
    text = str(value).strip()
    if not text:
        raise validation_error(f"{field_name} zorunludur.")
    if len(text) > max_length:
        raise validation_error(
            f"{field_name} en fazla {max_length} karakter olabilir."
        )
    return text


def optional_text(
    value: Any,
    field_name: str,
    max_length: int | None = None,
) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if max_length is not None and len(text) > max_length:
        raise validation_error(
            f"{field_name} en fazla {max_length} karakter olabilir."
        )
    return text


def shift_chief(value: Any) -> str:
    text = required_text(value, "vardiya amiri", 255)
    for option in shifts.SHIFT_CHIEF_OPTIONS:
        if text.casefold() == option.casefold():
            return option
    raise validation_error(
        "vardiya amiri "
        + ", ".join(shifts.SHIFT_CHIEF_OPTIONS)
        + " seçeneklerinden biri olmalıdır."
    )


def client_request_id(value: Any) -> str | None:
    return optional_text(value, "client_request_id", 64)


def client_recorded_datetime(value: Any, settings: Settings) -> datetime | None:
    text = optional_text(value, "client_recorded_at", 64)
    if text is None:
        return None

    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise validation_error(
            "client_recorded_at ISO tarih/saat değeri olmalıdır."
        ) from exc

    request_timezone = shifts.request_timezone(settings)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=request_timezone)
    return parsed.astimezone(request_timezone)


def stored_client_recorded_at(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.astimezone(UTC).replace(tzinfo=None)


def optional_bool(value: Any, field_name: str) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    text = str(value).strip().casefold()
    if not text:
        return False
    if text in {"1", "true", "on", "yes", "evet"}:
        return True
    if text in {"0", "false", "off", "no", "hayir", "hayır"}:
        return False
    raise validation_error(f"{field_name} evet/hayır değeri olmalıdır.")


def tour_context_id_from_body(body: dict[str, Any]) -> int:
    raw_context_id = body.get("tour_context_id")
    if raw_context_id is None:
        raise validation_error("tour_context_id zorunludur.")
    try:
        context_id = int(raw_context_id)
    except (TypeError, ValueError) as exc:
        raise validation_error("tour_context_id tam sayı olmalıdır.") from exc
    if context_id < 1:
        raise validation_error("tour_context_id pozitif tam sayı olmalıdır.")
    return context_id
