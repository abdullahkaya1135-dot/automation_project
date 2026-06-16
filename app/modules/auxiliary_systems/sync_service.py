from collections.abc import Sequence
from typing import Any

from sqlalchemy.orm import Session

from ...config import Settings
from ...database import commit_session, create_session
from ...models import (
    SYNC_STATUS_FAILED_EXCEL,
    SYNC_STATUS_PENDING_EXCEL,
    AuxiliarySystemsSubmission,
)
from ..sync.retry_results import retry_summary
from .repository import (
    count_auxiliary_submissions_by_statuses,
    list_unsynced_auxiliary_submissions,
)
from .repository import (
    latest_auxiliary_sync_error as _latest_auxiliary_sync_error,
)
from .serializers import (
    serialize_auxiliary_submission as serialize_auxiliary_submission,
)
from .serializers import submission_payload as submission_payload
from .sync_results import (
    failed_sync_result,
    mark_auxiliary_sync_failed,
    mark_auxiliary_synced,
    synced_sync_result,
)
from .workbook_service import (
    AuxiliaryWorkbookSubmission,
    append_auxiliary_submissions_to_workbook,
    append_auxiliary_systems_to_workbook,
)

AUXILIARY_UNSYNCED_STATUSES = (
    SYNC_STATUS_PENDING_EXCEL,
    SYNC_STATUS_FAILED_EXCEL,
)


def latest_auxiliary_sync_error(session: Session) -> str | None:
    return _latest_auxiliary_sync_error(session)


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
        error = str(exc) or exc.__class__.__name__
        mark_auxiliary_sync_failed(
            submission,
            failure_status=failure_status,
            error=error,
        )
        commit_session(session)
        return failed_sync_result(submission, error)

    mark_auxiliary_synced(submission, start_row=start_row, end_row=end_row)
    commit_session(session)
    return synced_sync_result(submission)


def sync_auxiliary_submissions_batch(
    settings: Settings,
    session: Session,
    submissions: Sequence[AuxiliarySystemsSubmission],
    *,
    failure_status: str,
) -> list[dict[str, Any]]:
    if not submissions:
        return []

    results: list[dict[str, Any]] = []
    try:
        block_results = append_auxiliary_submissions_to_workbook(
            settings,
            [
                AuxiliaryWorkbookSubmission(
                    payload=submission_payload(submission),
                    recorded_date=submission.recorded_date,
                    submission_id=submission.id,
                )
                for submission in submissions
            ],
            reuse_existing_matches=failure_status == SYNC_STATUS_FAILED_EXCEL,
        )
    except Exception as exc:
        error = str(exc) or exc.__class__.__name__
        for submission in submissions:
            mark_auxiliary_sync_failed(
                submission,
                failure_status=failure_status,
                error=error,
            )
            results.append(failed_sync_result(submission, error))
    else:
        for submission, block_result in zip(
            submissions,
            block_results,
            strict=True,
        ):
            mark_auxiliary_synced(
                submission,
                start_row=block_result.start_row,
                end_row=block_result.end_row,
            )
            results.append(synced_sync_result(submission))

    commit_session(session)
    return results


def retry_unsynced_auxiliary_submissions(
    settings: Settings,
    *,
    limit: int = 100,
) -> dict[str, Any]:
    with create_session(settings) as session:
        submissions = list_unsynced_auxiliary_submissions(
            session,
            statuses=AUXILIARY_UNSYNCED_STATUSES,
            limit=limit,
        )

        results: list[dict[str, Any]] = []
        if submissions:
            results = sync_auxiliary_submissions_batch(
                settings,
                session,
                submissions,
                failure_status=SYNC_STATUS_FAILED_EXCEL,
            )

        remaining = count_auxiliary_submissions_by_statuses(
            session,
            AUXILIARY_UNSYNCED_STATUSES,
        )

        return retry_summary(results, remaining=remaining)
