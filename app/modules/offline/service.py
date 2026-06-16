from typing import Any

from ...config import Settings
from ...database import commit_session, create_session
from ...schemas import OfflineBulkSyncRequest
from .excel_sync import sync_offline_excel_targets
from .records import process_offline_records
from .response import offline_bulk_response, serialize_processed_records


def bulk_sync_offline_records(
    settings: Settings,
    payload: OfflineBulkSyncRequest,
) -> dict[str, Any]:
    excel_error: str | None = None

    with create_session(settings) as session:
        result = process_offline_records(session, settings, payload.records)
        commit_session(session)

        if payload.sync_excel:
            excel_error = sync_offline_excel_targets(
                settings,
                session,
                entries=result.entries_to_sync,
                auxiliary_submissions=result.auxiliary_to_sync,
            )

        records = serialize_processed_records(result.processed)

    return offline_bulk_response(records, excel_error=excel_error)
