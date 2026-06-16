from collections.abc import Sequence
from typing import Any

from sqlalchemy.orm import Session

from ...config import Settings
from ...database import commit_session, create_session
from ...models import (
    SYNC_STATUS_FAILED_EXCEL,
    SYNC_STATUS_PENDING_EXCEL,
    Entry,
)
from ..process_entry.repository import (
    count_entries_by_statuses,
    list_unsynced_entries,
)
from ..process_entry.repository import (
    latest_sync_error as _latest_sync_error,
)
from ..process_entry.workbook_service import (
    append_entries_to_workbook,
    append_entry_to_workbook,
)
from .process_entry_results import (
    failed_sync_result,
    mark_process_entry_sync_failed,
    mark_process_entry_synced,
    synced_sync_result,
)
from .retry_results import retry_summary

UNSYNCED_STATUSES = (SYNC_STATUS_PENDING_EXCEL, SYNC_STATUS_FAILED_EXCEL)


def latest_sync_error(session: Session) -> str | None:
    return _latest_sync_error(session)


def attempt_excel_append(
    settings: Settings,
    session: Session,
    entry: Entry,
    *,
    failure_status: str,
) -> dict[str, Any]:
    try:
        row_number = append_entry_to_workbook(
            settings,
            entry,
            reuse_existing_match=failure_status == SYNC_STATUS_FAILED_EXCEL,
        )
    except Exception as exc:
        error = str(exc) or exc.__class__.__name__
        mark_process_entry_sync_failed(
            entry,
            failure_status=failure_status,
            error=error,
        )
        commit_session(session)
        return failed_sync_result(entry, error)

    mark_process_entry_synced(entry, row_number=row_number)
    commit_session(session)
    return synced_sync_result(entry)


def sync_process_entries_batch(
    settings: Settings,
    session: Session,
    entries: Sequence[Entry],
    *,
    failure_status: str,
    reuse_existing_matches: bool,
) -> list[dict[str, Any]]:
    if not entries:
        return []

    results: list[dict[str, Any]] = []
    try:
        row_results = append_entries_to_workbook(
            settings,
            entries,
            reuse_existing_matches=reuse_existing_matches,
        )
    except Exception as exc:
        error = str(exc) or exc.__class__.__name__
        for entry in entries:
            mark_process_entry_sync_failed(
                entry,
                failure_status=failure_status,
                error=error,
            )
            results.append(failed_sync_result(entry, error))
    else:
        for entry, row_result in zip(entries, row_results, strict=True):
            mark_process_entry_synced(
                entry,
                row_number=row_result.row_number,
            )
            results.append(synced_sync_result(entry))

    commit_session(session)
    return results


def retry_unsynced_entries(
    settings: Settings,
    *,
    limit: int = 100,
) -> dict[str, Any]:
    with create_session(settings) as session:
        entries = list_unsynced_entries(
            session,
            statuses=UNSYNCED_STATUSES,
            limit=limit,
        )

        results: list[dict[str, Any]] = []
        if entries:
            results = sync_process_entries_batch(
                settings,
                session,
                entries,
                failure_status=SYNC_STATUS_FAILED_EXCEL,
                reuse_existing_matches=True,
            )

        remaining = count_entries_by_statuses(session, UNSYNCED_STATUSES)

        return retry_summary(
            results,
            remaining=remaining,
        )
