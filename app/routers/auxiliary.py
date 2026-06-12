import json
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy import select

from ..auth import require_api_auth
from ..database import commit_session, create_session
from ..domain.auxiliary_payloads import (
    auxiliary_payload_from_body,
    auxiliary_recorded_date_from_body,
)
from ..domain.request_settings import settings_from_request
from ..domain.request_values import (
    client_recorded_datetime,
    client_request_id,
    stored_client_recorded_at,
)
from ..models import (
    SYNC_STATUS_PENDING_EXCEL,
    SYNC_STATUS_SYNCED,
    AuxiliarySystemsSubmission,
    utc_now,
)
from ..services.auxiliary_systems_sync_service import (
    attempt_auxiliary_excel_append,
    retry_unsynced_auxiliary_submissions,
    serialize_auxiliary_submission,
)
from .validators import validate_sync_status

router = APIRouter(prefix="/api", dependencies=[Depends(require_api_auth)])


@router.post(
    "/auxiliary-systems/submissions",
    status_code=status.HTTP_201_CREATED,
)
def create_auxiliary_systems_submission(
    payload: dict[str, Any],
    request: Request,
    response: Response,
) -> dict[str, Any]:
    settings = settings_from_request(request)
    request_client_id = client_request_id(payload.get("client_request_id"))
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

    with create_session(settings) as session:
        if request_client_id is not None:
            existing_submission = session.scalars(
                select(AuxiliarySystemsSubmission).where(
                    AuxiliarySystemsSubmission.client_request_id
                    == request_client_id
                )
            ).first()
            if existing_submission is not None:
                response.status_code = status.HTTP_200_OK
                return {
                    "saved_locally": True,
                    "synced_to_excel": existing_submission.sync_status
                    == SYNC_STATUS_SYNCED,
                    "submission": serialize_auxiliary_submission(
                        existing_submission
                    ),
                    "idempotent_replay": True,
                }

        submission = AuxiliarySystemsSubmission(
            client_request_id=request_client_id,
            client_recorded_at=stored_recorded_at,
            recorded_date=recorded_date,
            payload_json=json.dumps(auxiliary_payload, ensure_ascii=False),
            sync_status=SYNC_STATUS_PENDING_EXCEL,
            submitted_at=stored_recorded_at or utc_now(),
        )
        session.add(submission)
        commit_session(session)

        sync_result = attempt_auxiliary_excel_append(
            settings,
            session,
            submission,
            failure_status=SYNC_STATUS_PENDING_EXCEL,
        )
        return {
            "saved_locally": True,
            "synced_to_excel": sync_result["success"],
            "submission": serialize_auxiliary_submission(submission),
        }


@router.get("/auxiliary-systems/submissions")
def list_auxiliary_systems_submissions(
    request: Request,
    sync_status: str | None = None,
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    validate_sync_status(sync_status)

    settings = settings_from_request(request)
    query = (
        select(AuxiliarySystemsSubmission)
        .order_by(
            AuxiliarySystemsSubmission.created_at.desc(),
            AuxiliarySystemsSubmission.id.desc(),
        )
        .limit(limit)
    )
    if sync_status is not None:
        query = query.where(AuxiliarySystemsSubmission.sync_status == sync_status)

    with create_session(settings) as session:
        submissions = session.scalars(query).all()
        return {
            "submissions": [
                serialize_auxiliary_submission(submission)
                for submission in submissions
            ]
        }


@router.post("/auxiliary-systems/sync/retry")
def retry_auxiliary_systems_sync(request: Request) -> dict[str, Any]:
    return retry_unsynced_auxiliary_submissions(settings_from_request(request))
