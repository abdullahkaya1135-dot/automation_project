from collections.abc import Sequence
from typing import Any

from sqlalchemy import Integer, cast, func, select
from sqlalchemy.orm import Session

from ...core.config import Settings
from ...core.database import commit_session, create_session
from ...services.excel_service import (
    append_entries_to_workbook,
    append_entry_to_workbook,
)
from ..serialization import timestamp as _timestamp
from .fields import ENTRY_FIELD_NAMES
from .models import (
    SYNC_STATUS_FAILED_EXCEL,
    SYNC_STATUS_PENDING_EXCEL,
    SYNC_STATUS_SYNCED,
    Entry,
    TourContext,
    utc_now,
)
from .normalization import normalize_process_date

UNSYNCED_STATUSES = (SYNC_STATUS_PENDING_EXCEL, SYNC_STATUS_FAILED_EXCEL)


def entry_payload(entry: Entry) -> dict[str, Any]:
    return {
        field_name: getattr(entry, field_name)
        for field_name in ENTRY_FIELD_NAMES
    }


def serialize_tour_context(context: TourContext | None) -> dict[str, Any] | None:
    if context is None:
        return None
    return {
        "id": context.id,
        "client_request_id": context.client_request_id,
        "client_recorded_at": _timestamp(context.client_recorded_at),
        "date": context.date,
        "ambient_temp": context.ambient_temp,
        "production_engineer": context.production_engineer,
        "shift_chief": context.shift_chief,
        "shift": context.shift,
        "created_at": _timestamp(context.created_at),
        "updated_at": _timestamp(context.updated_at),
    }


def serialize_entry(entry: Entry) -> dict[str, Any]:
    return {
        "id": entry.id,
        "client_request_id": entry.client_request_id,
        "client_recorded_at": _timestamp(entry.client_recorded_at),
        "tour_context_id": entry.tour_context_id,
        "tour_context": serialize_tour_context(entry.tour_context),
        "payload": entry_payload(entry),
        "process_date": entry.process_date,
        "machine_code": entry.machine_code,
        "production_engineer_id": entry.production_engineer_id,
        "status": entry.status,
        "notes": entry.notes,
        "mold_info": entry.mold_info,
        "sync_status": entry.sync_status,
        "excel_row_number": entry.excel_row_number,
        "last_error": entry.last_error,
        "submitted_at": _timestamp(entry.submitted_at),
        "created_at": _timestamp(entry.created_at),
        "updated_at": _timestamp(entry.updated_at),
        "synced_at": _timestamp(entry.synced_at),
    }


def latest_tour_context(session: Session) -> TourContext | None:
    return session.scalars(
        select(TourContext).order_by(
            TourContext.updated_at.desc(),
            TourContext.id.desc(),
        )
    ).first()


def latest_sync_error(session: Session) -> str | None:
    entry = session.scalars(
        select(Entry)
        .where(Entry.last_error.is_not(None))
        .where(Entry.last_error != "")
        .order_by(Entry.updated_at.desc(), Entry.id.desc())
    ).first()
    if entry is None:
        return None
    return entry.last_error


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
        entry.sync_status = failure_status
        entry.last_error = str(exc) or exc.__class__.__name__
        entry.synced_at = None
        commit_session(session)
        return {
            "entry_id": entry.id,
            "success": False,
            "sync_status": entry.sync_status,
            "excel_row_number": entry.excel_row_number,
            "last_error": entry.last_error,
        }

    entry.sync_status = SYNC_STATUS_SYNCED
    entry.excel_row_number = row_number
    entry.last_error = None
    entry.synced_at = utc_now()
    commit_session(session)
    return {
        "entry_id": entry.id,
        "success": True,
        "sync_status": entry.sync_status,
        "excel_row_number": entry.excel_row_number,
        "last_error": None,
    }


def retry_unsynced_entries(
    settings: Settings,
    *,
    limit: int = 100,
    process_date: str | None = None,
) -> dict[str, Any]:
    normalized_process_date = normalize_process_date(process_date)
    with create_session(settings) as session:
        base_query = select(Entry).where(Entry.sync_status.in_(UNSYNCED_STATUSES))
        count_query = (
            select(func.count())
            .select_from(Entry)
            .where(Entry.sync_status.in_(UNSYNCED_STATUSES))
        )
        if normalized_process_date is not None:
            base_query = base_query.where(Entry.process_date == normalized_process_date)
            count_query = count_query.where(Entry.process_date == normalized_process_date)

        entries = session.scalars(
            base_query.order_by(
                Entry.process_date.asc(),
                cast(Entry.machine_code, Integer).asc(),
                Entry.production_engineer_id.asc(),
                Entry.id.asc(),
            ).limit(limit)
        ).all()

        results = _bulk_append_results(settings, session, entries)
        remaining = session.scalar(count_query)

        return {
            "attempted": len(results),
            "synced": sum(1 for result in results if result["success"]),
            "failed": sum(1 for result in results if not result["success"]),
            "remaining": int(remaining or 0),
            "stopped_on_error": any(not result["success"] for result in results),
            "results": results,
            "process_date": normalized_process_date,
        }


def _bulk_append_results(
    settings: Settings,
    session: Session,
    entries: Sequence[Entry],
) -> list[dict[str, Any]]:
    if not entries:
        return []

    try:
        row_numbers = append_entries_to_workbook(
            settings,
            entries,
            reuse_existing_matches=True,
        )
    except Exception as exc:
        error = str(exc) or exc.__class__.__name__
        for entry in entries:
            entry.sync_status = SYNC_STATUS_FAILED_EXCEL
            entry.last_error = error
            entry.synced_at = None
        commit_session(session)
        return [
            {
                "entry_id": entry.id,
                "success": False,
                "sync_status": entry.sync_status,
                "excel_row_number": entry.excel_row_number,
                "last_error": entry.last_error,
            }
            for entry in entries
        ]

    synced_at = utc_now()
    for entry, row_number in zip(entries, row_numbers, strict=True):
        entry.sync_status = SYNC_STATUS_SYNCED
        entry.excel_row_number = row_number
        entry.last_error = None
        entry.synced_at = synced_at
    commit_session(session)
    return [
        {
            "entry_id": entry.id,
            "success": True,
            "sync_status": entry.sync_status,
            "excel_row_number": entry.excel_row_number,
            "last_error": None,
        }
        for entry in entries
    ]
