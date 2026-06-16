from typing import Any

from ...models import (
    SYNC_STATUS_SYNCED,
    Entry,
    TourContext,
)
from ..auxiliary_systems.serializers import serialize_auxiliary_submission
from ..sync.serializers import serialize_entry, serialize_tour_context
from .types import ProcessedOfflineRecord


def serialize_processed_records(
    processed: list[ProcessedOfflineRecord],
) -> list[dict[str, Any]]:
    return [serialize_processed_record(record) for record in processed]


def serialize_processed_record(record: ProcessedOfflineRecord) -> dict[str, Any]:
    if isinstance(record.item, TourContext):
        context_payload = serialize_tour_context(record.item)
        return {
            "type": record.record_type,
            "client_request_id": record.client_id,
            "server_id": record.item.id,
            "saved_locally": True,
            "synced_to_excel": None,
            "idempotent_replay": record.idempotent_replay,
            "tour_context": context_payload,
        }

    if isinstance(record.item, Entry):
        entry_payload = serialize_entry(record.item)
        return {
            "type": record.record_type,
            "client_request_id": record.client_id,
            "server_id": record.item.id,
            "saved_locally": True,
            "synced_to_excel": record.item.sync_status == SYNC_STATUS_SYNCED,
            "idempotent_replay": record.idempotent_replay,
            "entry": entry_payload,
        }

    submission_payload = serialize_auxiliary_submission(record.item)
    return {
        "type": record.record_type,
        "client_request_id": record.client_id,
        "server_id": record.item.id,
        "saved_locally": True,
        "synced_to_excel": record.item.sync_status == SYNC_STATUS_SYNCED,
        "idempotent_replay": record.idempotent_replay,
        "submission": submission_payload,
    }


def offline_bulk_response(
    records: list[dict[str, Any]],
    *,
    excel_error: str | None,
) -> dict[str, Any]:
    synced_count = sum(
        1 for record in records if record.get("synced_to_excel") is True
    )
    failed_count = sum(
        1
        for record in records
        if record.get("synced_to_excel") is False
        and record["type"] in {"entry", "auxiliary_submission"}
    )
    return {
        "saved_count": len(records),
        "synced_count": synced_count,
        "failed_count": failed_count,
        "excel_pending": failed_count > 0,
        "excel_error": excel_error,
        "records": records,
    }
