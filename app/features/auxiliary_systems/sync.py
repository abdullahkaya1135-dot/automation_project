import json
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...core.config import Settings
from ...core.database import commit_session, create_session
from .models import (
    SYNC_STATUS_FAILED_EXCEL,
    SYNC_STATUS_PENDING_EXCEL,
    SYNC_STATUS_SYNCED,
    AuxiliarySystemsSubmission,
    utc_now,
)
from .workbook import (
    AUXILIARY_FIELD_NAMES,
    append_auxiliary_systems_to_workbook,
)

AUXILIARY_UNSYNCED_STATUSES = (
    SYNC_STATUS_PENDING_EXCEL,
    SYNC_STATUS_FAILED_EXCEL,
)


def _timestamp(value: datetime | None) -> str | None:
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
        "client_recorded_at": _timestamp(submission.client_recorded_at),
        "recorded_date": submission.recorded_date,
        "payload": submission_payload(submission),
        "sync_status": submission.sync_status,
        "excel_start_row": submission.excel_start_row,
        "excel_end_row": submission.excel_end_row,
        "last_error": submission.last_error,
        "submitted_at": _timestamp(submission.submitted_at),
        "created_at": _timestamp(submission.created_at),
        "updated_at": _timestamp(submission.updated_at),
        "synced_at": _timestamp(submission.synced_at),
    }


def latest_auxiliary_sync_error(session: Session) -> str | None:
    submission = session.scalars(
        select(AuxiliarySystemsSubmission)
        .where(AuxiliarySystemsSubmission.last_error.is_not(None))
        .where(AuxiliarySystemsSubmission.last_error != "")
        .order_by(
            AuxiliarySystemsSubmission.updated_at.desc(),
            AuxiliarySystemsSubmission.id.desc(),
        )
    ).first()
    if submission is None:
        return None
    return submission.last_error


def attempt_auxiliary_excel_append(
    settings: Settings,
    session: Session,
    submission: AuxiliarySystemsSubmission,
    *,
    failure_status: str,
) -> dict[str, Any]:
    try:
        start_row, end_row = append_auxiliary_systems_to_workbook(
            settings,
            submission_payload(submission),
            submission.recorded_date,
            reuse_existing_match=failure_status == SYNC_STATUS_FAILED_EXCEL,
        )
    except Exception as exc:
        submission.sync_status = failure_status
        submission.last_error = str(exc) or exc.__class__.__name__
        submission.synced_at = None
        commit_session(session)
        return {
            "submission_id": submission.id,
            "success": False,
            "sync_status": submission.sync_status,
            "excel_start_row": submission.excel_start_row,
            "excel_end_row": submission.excel_end_row,
            "last_error": submission.last_error,
        }

    submission.sync_status = SYNC_STATUS_SYNCED
    submission.excel_start_row = start_row
    submission.excel_end_row = end_row
    submission.last_error = None
    submission.synced_at = utc_now()
    commit_session(session)
    return {
        "submission_id": submission.id,
        "success": True,
        "sync_status": submission.sync_status,
        "excel_start_row": submission.excel_start_row,
        "excel_end_row": submission.excel_end_row,
        "last_error": None,
    }


def retry_unsynced_auxiliary_submissions(
    settings: Settings,
    *,
    limit: int = 100,
) -> dict[str, Any]:
    with create_session(settings) as session:
        submissions = session.scalars(
            select(AuxiliarySystemsSubmission)
            .where(
                AuxiliarySystemsSubmission.sync_status.in_(
                    AUXILIARY_UNSYNCED_STATUSES
                )
            )
            .order_by(
                AuxiliarySystemsSubmission.created_at.asc(),
                AuxiliarySystemsSubmission.id.asc(),
            )
            .limit(limit)
        ).all()

        results: list[dict[str, Any]] = []
        stopped_on_error = False
        for submission in submissions:
            result = attempt_auxiliary_excel_append(
                settings,
                session,
                submission,
                failure_status=SYNC_STATUS_FAILED_EXCEL,
            )
            results.append(result)
            if not result["success"]:
                stopped_on_error = True
                break

        remaining = session.scalar(
            select(func.count())
            .select_from(AuxiliarySystemsSubmission)
            .where(
                AuxiliarySystemsSubmission.sync_status.in_(
                    AUXILIARY_UNSYNCED_STATUSES
                )
            )
        )

        return {
            "attempted": len(results),
            "synced": sum(1 for result in results if result["success"]),
            "failed": sum(1 for result in results if not result["success"]),
            "remaining": int(remaining or 0),
            "stopped_on_error": stopped_on_error,
            "results": results,
        }
