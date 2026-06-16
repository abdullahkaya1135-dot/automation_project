from datetime import datetime
from typing import Any

from ...domain.entry_fields import ENTRY_FIELD_NAMES
from ...models import Entry, TourContext


def _timestamp(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat(timespec="seconds") + "Z"


def entry_payload(entry: Entry) -> dict[str, Any]:
    return {
        field_name: getattr(entry, field_name)
        for field_name in ENTRY_FIELD_NAMES
    }


def serialize_tour_context(context: TourContext | None) -> dict[str, Any] | None:
    if context is None:
        return None
    return {
        "id": context.id,
        "client_request_id": context.client_request_id,
        "client_recorded_at": _timestamp(context.client_recorded_at),
        "date": context.date,
        "ambient_temp": context.ambient_temp,
        "production_engineer": context.production_engineer,
        "shift_chief": context.shift_chief,
        "shift": context.shift,
        "created_at": _timestamp(context.created_at),
        "updated_at": _timestamp(context.updated_at),
    }


def serialize_entry(entry: Entry) -> dict[str, Any]:
    return {
        "id": entry.id,
        "client_request_id": entry.client_request_id,
        "client_recorded_at": _timestamp(entry.client_recorded_at),
        "tour_context_id": entry.tour_context_id,
        "tour_context": serialize_tour_context(entry.tour_context),
        "payload": entry_payload(entry),
        "status": entry.status,
        "notes": entry.notes,
        "mold_info": entry.mold_info,
        "sync_status": entry.sync_status,
        "excel_row_number": entry.excel_row_number,
        "last_error": entry.last_error,
        "submitted_at": _timestamp(entry.submitted_at),
        "created_at": _timestamp(entry.created_at),
        "updated_at": _timestamp(entry.updated_at),
        "synced_at": _timestamp(entry.synced_at),
    }
