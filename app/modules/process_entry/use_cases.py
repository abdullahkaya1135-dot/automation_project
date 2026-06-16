from typing import Any

from fastapi import status

from ...config import Settings
from ...database import commit_session, create_session
from ...models import SYNC_STATUS_PENDING_EXCEL, SYNC_STATUS_SYNCED
from ...schemas import ProcessEntryCreate
from ..sync.process_entry_sync import attempt_excel_append
from ..sync.serializers import serialize_entry
from ..use_case_result import UseCaseResult
from .repository import list_entries
from .service import request_body, save_process_entry


def create_process_entry(
    settings: Settings,
    payload: ProcessEntryCreate,
) -> UseCaseResult:
    body = request_body(payload)

    with create_session(settings) as session:
        saved_entry = save_process_entry(
            session,
            settings,
            body,
            missing_context_status=status.HTTP_404_NOT_FOUND,
        )
        entry = saved_entry.entry
        response_payload = {
            "saved_locally": True,
            "synced_to_excel": entry.sync_status == SYNC_STATUS_SYNCED,
            "entry": serialize_entry(entry),
        }
        if saved_entry.idempotent_replay:
            response_payload["idempotent_replay"] = True
            return UseCaseResult(status.HTTP_200_OK, response_payload)

        commit_session(session)
        sync_result = attempt_excel_append(
            settings,
            session,
            entry,
            failure_status=SYNC_STATUS_PENDING_EXCEL,
        )
        response_payload["synced_to_excel"] = sync_result["success"]
        response_payload["entry"] = serialize_entry(entry)
        return UseCaseResult(status.HTTP_201_CREATED, response_payload)


def list_process_entries(
    settings: Settings,
    *,
    sync_status: str | None,
    limit: int,
) -> dict[str, Any]:
    with create_session(settings) as session:
        entries = list_entries(
            session,
            sync_status=sync_status,
            limit=limit,
        )
        return {"entries": [serialize_entry(entry) for entry in entries]}
