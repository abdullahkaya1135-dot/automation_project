from typing import Any

from ...domain.request_values import client_request_id, validation_error
from ...schemas import OfflineBulkRecord


def body_for_record(record: OfflineBulkRecord) -> dict[str, Any]:
    body = record.body.model_dump(mode="python")
    envelope_client_id = client_request_id(record.client_request_id)
    body_client_id = client_request_id(body.get("client_request_id"))
    if (
        envelope_client_id is not None
        and body_client_id is not None
        and envelope_client_id != body_client_id
    ):
        raise validation_error("client_request_id alanlari eslesmiyor.")
    if body_client_id is None and envelope_client_id is not None:
        body["client_request_id"] = envelope_client_id

    if body.get("client_recorded_at") is None and record.client_recorded_at:
        body["client_recorded_at"] = record.client_recorded_at
    return body


__all__ = ["body_for_record"]
