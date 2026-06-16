from typing import Any

from fastapi import status

from ...config import Settings
from ...database import commit_session, create_session
from ...models import SYNC_STATUS_PENDING_EXCEL, SYNC_STATUS_SYNCED
from ...schemas import AuxiliarySubmissionCreate
from ..use_case_result import UseCaseResult
from .repository import list_auxiliary_submissions
from .serializers import serialize_auxiliary_submission
from .submission_service import save_auxiliary_submission
from .sync_service import attempt_auxiliary_excel_append


def create_auxiliary_submission(
    settings: Settings,
    payload: AuxiliarySubmissionCreate,
) -> UseCaseResult:
    body = payload.model_dump(mode="python")

    with create_session(settings) as session:
        saved_submission = save_auxiliary_submission(session, settings, body)
        submission = saved_submission.submission
        response_payload = {
            "saved_locally": True,
            "synced_to_excel": submission.sync_status == SYNC_STATUS_SYNCED,
            "submission": serialize_auxiliary_submission(submission),
        }
        if saved_submission.idempotent_replay:
            response_payload["idempotent_replay"] = True
            return UseCaseResult(status.HTTP_200_OK, response_payload)

        commit_session(session)
        sync_result = attempt_auxiliary_excel_append(
            settings,
            session,
            submission,
            failure_status=SYNC_STATUS_PENDING_EXCEL,
        )
        response_payload["synced_to_excel"] = sync_result["success"]
        response_payload["submission"] = serialize_auxiliary_submission(submission)
        return UseCaseResult(status.HTTP_201_CREATED, response_payload)


def list_auxiliary_submission_payloads(
    settings: Settings,
    *,
    sync_status: str | None,
    limit: int,
) -> dict[str, Any]:
    with create_session(settings) as session:
        submissions = list_auxiliary_submissions(
            session,
            sync_status=sync_status,
            limit=limit,
        )
        return {
            "submissions": [
                serialize_auxiliary_submission(submission)
                for submission in submissions
            ]
        }
