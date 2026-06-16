from collections.abc import Sequence

from sqlalchemy.orm import Session

from ...config import Settings
from ...models import (
    SYNC_STATUS_PENDING_EXCEL,
    AuxiliarySystemsSubmission,
    Entry,
)
from ..auxiliary_systems.sync_service import sync_auxiliary_submissions_batch
from ..sync.process_entry_sync import sync_process_entries_batch


def sync_offline_excel_targets(
    settings: Settings,
    session: Session,
    *,
    entries: Sequence[Entry],
    auxiliary_submissions: Sequence[AuxiliarySystemsSubmission],
) -> str | None:
    excel_error = sync_process_entries_to_excel(settings, session, entries)
    auxiliary_error = sync_auxiliary_submissions_to_excel(
        settings,
        session,
        auxiliary_submissions,
    )
    return excel_error or auxiliary_error


def sync_process_entries_to_excel(
    settings: Settings,
    session: Session,
    entries: Sequence[Entry],
) -> str | None:
    if not entries:
        return None

    results = sync_process_entries_batch(
        settings,
        session,
        entries,
        failure_status=SYNC_STATUS_PENDING_EXCEL,
        reuse_existing_matches=True,
    )
    return next(
        (result["last_error"] for result in results if not result["success"]),
        None,
    )


def sync_auxiliary_submissions_to_excel(
    settings: Settings,
    session: Session,
    submissions: Sequence[AuxiliarySystemsSubmission],
) -> str | None:
    if not submissions:
        return None

    auxiliary_results = sync_auxiliary_submissions_batch(
        settings,
        session,
        submissions,
        failure_status=SYNC_STATUS_PENDING_EXCEL,
    )
    return next(
        (
            result["last_error"]
            for result in auxiliary_results
            if not result["success"]
        ),
        None,
    )
