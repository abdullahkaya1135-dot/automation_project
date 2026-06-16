from typing import Any

from fastapi import APIRouter, Depends, Query, Request, Response, status

from ..domain.request_settings import settings_from_request
from ..modules.auth.service import require_api_auth
from ..modules.process_entry.use_cases import (
    create_process_entry,
    list_process_entries,
)
from ..modules.sync.process_entry_sync import (
    retry_unsynced_entries,
)
from ..modules.tour_context.use_cases import (
    create_tour_context as create_tour_context_use_case,
)
from ..schemas import ProcessEntryCreate, SyncRetryResponse, TourContextCreate
from .validators import validate_sync_status

router = APIRouter(prefix="/api", dependencies=[Depends(require_api_auth)])


@router.post("/tour-context", status_code=status.HTTP_201_CREATED)
def create_tour_context(
    payload: TourContextCreate,
    request: Request,
    response: Response,
) -> dict[str, Any]:
    result = create_tour_context_use_case(settings_from_request(request), payload)
    response.status_code = result.status_code
    return result.payload


@router.post("/entries", status_code=status.HTTP_201_CREATED)
def create_entry(
    payload: ProcessEntryCreate,
    request: Request,
    response: Response,
) -> dict[str, Any]:
    result = create_process_entry(settings_from_request(request), payload)
    response.status_code = result.status_code
    return result.payload


@router.get("/entries")
def list_entries(
    request: Request,
    sync_status: str | None = None,
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    validate_sync_status(sync_status)

    return list_process_entries(
        settings_from_request(request),
        sync_status=sync_status,
        limit=limit,
    )


@router.post("/sync/retry", response_model=SyncRetryResponse)
def retry_sync(request: Request) -> dict[str, Any]:
    return retry_unsynced_entries(settings_from_request(request))
