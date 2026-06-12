from datetime import datetime
from typing import Any

from ..config import Settings
from ..services.auxiliary_systems_service import (
    AUXILIARY_CHECK_FIELD_NAMES,
    AUXILIARY_FIELD_NAMES,
)
from . import shifts
from .request_values import optional_bool, optional_text, validation_error


def auxiliary_payload_from_body(body: dict[str, Any]) -> dict[str, str | bool | None]:
    raw_payload = body.get("payload", {})
    if raw_payload is None:
        raw_payload = {}
    if not isinstance(raw_payload, dict):
        raise validation_error("payload bir nesne olmalıdır.")

    payload: dict[str, str | bool | None] = {}
    for field_name in AUXILIARY_FIELD_NAMES:
        raw_value = raw_payload.get(field_name)
        if field_name in body:
            raw_value = body[field_name]
        if field_name in AUXILIARY_CHECK_FIELD_NAMES:
            payload[field_name] = optional_bool(raw_value, field_name)
        else:
            payload[field_name] = optional_text(raw_value, field_name, 64)
    return payload


def auxiliary_recorded_date_from_body(
    body: dict[str, Any],
    settings: Settings,
    client_recorded_at: datetime | None = None,
) -> str:
    raw_date = body.get("recorded_date") or body.get("date")
    if raw_date is not None:
        return shifts.recorded_date_text(str(raw_date).strip())
    if client_recorded_at is not None:
        return shifts.recorded_date(client_recorded_at.date())
    return shifts.recorded_date(shifts.request_datetime(settings).date())
