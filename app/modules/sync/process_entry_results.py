from typing import Any

from ...models import SYNC_STATUS_SYNCED, Entry, utc_now


def mark_process_entry_sync_failed(
    entry: Entry,
    *,
    failure_status: str,
    error: str,
) -> None:
    entry.sync_status = failure_status
    entry.last_error = error
    entry.synced_at = None


def mark_process_entry_synced(
    entry: Entry,
    *,
    row_number: int,
) -> None:
    entry.sync_status = SYNC_STATUS_SYNCED
    entry.excel_row_number = row_number
    entry.last_error = None
    entry.synced_at = utc_now()


def failed_sync_result(entry: Entry, error: str) -> dict[str, Any]:
    return {
        "entry_id": entry.id,
        "success": False,
        "sync_status": entry.sync_status,
        "excel_row_number": entry.excel_row_number,
        "last_error": error,
    }


def synced_sync_result(entry: Entry) -> dict[str, Any]:
    return {
        "entry_id": entry.id,
        "success": True,
        "sync_status": entry.sync_status,
        "excel_row_number": entry.excel_row_number,
        "last_error": None,
    }


__all__ = [
    "failed_sync_result",
    "mark_process_entry_sync_failed",
    "mark_process_entry_synced",
    "synced_sync_result",
]
