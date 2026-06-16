from typing import Any

from ...models import (
    SYNC_STATUS_SYNCED,
    AuxiliarySystemsSubmission,
    utc_now,
)


def mark_auxiliary_sync_failed(
    submission: AuxiliarySystemsSubmission,
    *,
    failure_status: str,
    error: str,
) -> None:
    submission.sync_status = failure_status
    submission.last_error = error
    submission.synced_at = None


def mark_auxiliary_synced(
    submission: AuxiliarySystemsSubmission,
    *,
    start_row: int,
    end_row: int,
) -> None:
    submission.sync_status = SYNC_STATUS_SYNCED
    submission.excel_start_row = start_row
    submission.excel_end_row = end_row
    submission.last_error = None
    submission.synced_at = utc_now()


def failed_sync_result(
    submission: AuxiliarySystemsSubmission,
    error: str,
) -> dict[str, Any]:
    return {
        "submission_id": submission.id,
        "success": False,
        "sync_status": submission.sync_status,
        "excel_start_row": submission.excel_start_row,
        "excel_end_row": submission.excel_end_row,
        "last_error": error,
    }


def synced_sync_result(submission: AuxiliarySystemsSubmission) -> dict[str, Any]:
    return {
        "submission_id": submission.id,
        "success": True,
        "sync_status": submission.sync_status,
        "excel_start_row": submission.excel_start_row,
        "excel_end_row": submission.excel_end_row,
        "last_error": None,
    }

