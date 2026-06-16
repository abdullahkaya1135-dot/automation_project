import json
from datetime import datetime
from typing import Any

from ...models import AuxiliarySystemsSubmission
from .fields import AUXILIARY_FIELD_NAMES


def timestamp(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat(timespec="seconds") + "Z"


def submission_payload(submission: AuxiliarySystemsSubmission) -> dict[str, Any]:
    try:
        payload = json.loads(submission.payload_json)
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    return {
        field_name: payload.get(field_name)
        for field_name in AUXILIARY_FIELD_NAMES
    }


def serialize_auxiliary_submission(
    submission: AuxiliarySystemsSubmission,
) -> dict[str, Any]:
    return {
        "id": submission.id,
        "client_request_id": submission.client_request_id,
        "client_recorded_at": timestamp(submission.client_recorded_at),
        "recorded_date": submission.recorded_date,
        "payload": submission_payload(submission),
        "sync_status": submission.sync_status,
        "excel_start_row": submission.excel_start_row,
        "excel_end_row": submission.excel_end_row,
        "last_error": submission.last_error,
        "submitted_at": timestamp(submission.submitted_at),
        "created_at": timestamp(submission.created_at),
        "updated_at": timestamp(submission.updated_at),
        "synced_at": timestamp(submission.synced_at),
    }
