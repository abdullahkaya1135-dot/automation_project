from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ...config import Settings
from ...domain.entry_payloads import combined_entry_payload
from ...domain.request_values import (
    client_recorded_datetime,
    client_request_id,
    optional_text,
    stored_client_recorded_at,
    tour_context_id_from_body,
    validation_error,
)
from ...models import (
    SYNC_STATUS_PENDING_EXCEL,
    Entry,
    utc_now,
)
from ..tour_context.repository import get_tour_context
from .repository import (
    add_entry,
    get_entry_by_client_request_id,
)


@dataclass(frozen=True)
class SavedEntry:
    entry: Entry
    idempotent_replay: bool


def request_body(payload: Mapping[str, Any] | object) -> dict[str, Any]:
    if isinstance(payload, Mapping):
        return dict(payload)
    model_dump = getattr(payload, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump(mode="python")
        if isinstance(dumped, dict):
            return dumped
    return dict(vars(payload))


def save_process_entry(
    session: Session,
    settings: Settings,
    body: Mapping[str, Any],
    *,
    missing_context_status: int = status.HTTP_422_UNPROCESSABLE_CONTENT,
) -> SavedEntry:
    payload = dict(body)
    request_client_id = client_request_id(payload.get("client_request_id"))
    if request_client_id is not None:
        existing_entry = get_entry_by_client_request_id(session, request_client_id)
        if existing_entry is not None:
            return SavedEntry(entry=existing_entry, idempotent_replay=True)

    context_id = tour_context_id_from_body(payload)
    context = get_tour_context(session, context_id)
    if context is None:
        if missing_context_status == status.HTTP_404_NOT_FOUND:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tur bilgileri bulunamadi.",
            )
        raise validation_error("Tur bilgileri bulunamadi.")

    client_recorded_at = client_recorded_datetime(
        payload.get("client_recorded_at"),
        settings,
    )
    stored_recorded_at = stored_client_recorded_at(client_recorded_at)
    entry_payload = combined_entry_payload(context, payload)
    entry = Entry(
        client_request_id=request_client_id,
        client_recorded_at=stored_recorded_at,
        tour_context_id=context.id,
        status=optional_text(payload.get("status"), "durum", 64),
        notes=optional_text(payload.get("notes"), "notlar"),
        mold_info=optional_text(payload.get("mold_info"), "kalip bilgisi"),
        sync_status=SYNC_STATUS_PENDING_EXCEL,
        submitted_at=stored_recorded_at or utc_now(),
        **entry_payload,
    )
    return SavedEntry(entry=add_entry(session, entry), idempotent_replay=False)
