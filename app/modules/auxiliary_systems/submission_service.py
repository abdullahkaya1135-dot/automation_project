import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from ...config import Settings
from ...domain.auxiliary_payloads import (
    auxiliary_payload_from_body,
    auxiliary_recorded_date_from_body,
)
from ...domain.request_values import (
    client_recorded_datetime,
    client_request_id,
    stored_client_recorded_at,
)
from ...models import (
    SYNC_STATUS_PENDING_EXCEL,
    AuxiliarySystemsSubmission,
    utc_now,
)
from .repository import (
    add_auxiliary_submission,
    get_auxiliary_submission_by_client_request_id,
)


@dataclass(frozen=True)
class SavedAuxiliarySubmission:
    submission: AuxiliarySystemsSubmission
    idempotent_replay: bool


def save_auxiliary_submission(
    session: Session,
    settings: Settings,
    body: Mapping[str, Any],
) -> SavedAuxiliarySubmission:
    payload = dict(body)
    request_client_id = client_request_id(payload.get("client_request_id"))
    if request_client_id is not None:
        existing_submission = get_auxiliary_submission_by_client_request_id(
            session,
            request_client_id,
        )
        if existing_submission is not None:
            return SavedAuxiliarySubmission(
                submission=existing_submission,
                idempotent_replay=True,
            )

    client_recorded_at = client_recorded_datetime(
        payload.get("client_recorded_at"),
        settings,
    )
    stored_recorded_at = stored_client_recorded_at(client_recorded_at)
    recorded_date = auxiliary_recorded_date_from_body(
        payload,
        settings,
        client_recorded_at,
    )
    auxiliary_payload = auxiliary_payload_from_body(payload)
    submission = AuxiliarySystemsSubmission(
        client_request_id=request_client_id,
        client_recorded_at=stored_recorded_at,
        recorded_date=recorded_date,
        payload_json=json.dumps(auxiliary_payload, ensure_ascii=False),
        sync_status=SYNC_STATUS_PENDING_EXCEL,
        submitted_at=stored_recorded_at or utc_now(),
    )
    return SavedAuxiliarySubmission(
        submission=add_auxiliary_submission(session, submission),
        idempotent_replay=False,
    )
