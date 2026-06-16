from collections.abc import Sequence
from typing import Any

from sqlalchemy.orm import Session

from ...config import Settings
from ...models import SYNC_STATUS_SYNCED
from ...schemas import OfflineBulkRecord
from ..auxiliary_systems.submission_service import save_auxiliary_submission
from ..process_entry.service import save_process_entry
from ..tour_context.service import save_tour_context
from .dependencies import resolve_entry_dependency
from .envelope import body_for_record
from .types import OfflineProcessingResult, ProcessedOfflineRecord


def process_offline_records(
    session: Session,
    settings: Settings,
    records: Sequence[OfflineBulkRecord],
) -> OfflineProcessingResult:
    result = OfflineProcessingResult()
    context_ids_by_client_id: dict[str, int] = {}

    for record in records:
        body = body_for_record(record)
        if record.type == "tour_context":
            process_tour_context_record(
                session,
                settings,
                body,
                record,
                context_ids_by_client_id,
                result,
            )
            continue

        if record.type == "entry":
            process_entry_record(
                session,
                settings,
                body,
                record,
                context_ids_by_client_id,
                result,
            )
            continue

        process_auxiliary_record(session, settings, body, record, result)

    return result


def process_tour_context_record(
    session: Session,
    settings: Settings,
    body: dict[str, Any],
    record: OfflineBulkRecord,
    context_ids_by_client_id: dict[str, int],
    result: OfflineProcessingResult,
) -> None:
    saved_context = save_tour_context(session, settings, body)
    context = saved_context.context
    if context.client_request_id is not None:
        context_ids_by_client_id[context.client_request_id] = context.id
    result.processed.append(
        ProcessedOfflineRecord(
            record_type=record.type,
            client_id=context.client_request_id,
            item=context,
            idempotent_replay=saved_context.idempotent_replay,
        )
    )


def process_entry_record(
    session: Session,
    settings: Settings,
    body: dict[str, Any],
    record: OfflineBulkRecord,
    context_ids_by_client_id: dict[str, int],
    result: OfflineProcessingResult,
) -> None:
    resolve_entry_dependency(
        session,
        body,
        record,
        context_ids_by_client_id,
    )
    saved_entry = save_process_entry(session, settings, body)
    entry = saved_entry.entry
    result.processed.append(
        ProcessedOfflineRecord(
            record_type=record.type,
            client_id=entry.client_request_id,
            item=entry,
            idempotent_replay=saved_entry.idempotent_replay,
        )
    )
    if entry.sync_status != SYNC_STATUS_SYNCED:
        result.entries_to_sync.append(entry)


def process_auxiliary_record(
    session: Session,
    settings: Settings,
    body: dict[str, Any],
    record: OfflineBulkRecord,
    result: OfflineProcessingResult,
) -> None:
    saved_submission = save_auxiliary_submission(session, settings, body)
    submission = saved_submission.submission
    result.processed.append(
        ProcessedOfflineRecord(
            record_type=record.type,
            client_id=submission.client_request_id,
            item=submission,
            idempotent_replay=saved_submission.idempotent_replay,
        )
    )
    if submission.sync_status != SYNC_STATUS_SYNCED:
        result.auxiliary_to_sync.append(submission)
