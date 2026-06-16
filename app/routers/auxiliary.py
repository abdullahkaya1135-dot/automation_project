from typing import Any

from fastapi import APIRouter, Depends, Query, Request, Response, status

from ..domain.request_settings import settings_from_request
from ..modules.auth.service import require_api_auth
from ..modules.auxiliary_systems.sync_service import (
    retry_unsynced_auxiliary_submissions,
)
from ..modules.auxiliary_systems.use_cases import (
    create_auxiliary_submission,
    list_auxiliary_submission_payloads,
)
from ..schemas import AuxiliarySubmissionCreate, SyncRetryResponse
from .validators import validate_sync_status

router = APIRouter(prefix="/api", dependencies=[Depends(require_api_auth)])


@router.post(
    "/auxiliary-systems/submissions",
    status_code=status.HTTP_201_CREATED,
)
def create_auxiliary_systems_submission(
    payload: AuxiliarySubmissionCreate,
    request: Request,
    response: Response,
) -> dict[str, Any]:
    result = create_auxiliary_submission(settings_from_request(request), payload)
    response.status_code = result.status_code
    return result.payload


@router.get("/auxiliary-systems/submissions")
def list_auxiliary_systems_submissions(
    request: Request,
    sync_status: str | None = None,
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    validate_sync_status(sync_status)

    return list_auxiliary_submission_payloads(
        settings_from_request(request),
        sync_status=sync_status,
        limit=limit,
    )


@router.post(
    "/auxiliary-systems/sync/retry",
    response_model=SyncRetryResponse,
)
def retry_auxiliary_systems_sync(request: Request) -> dict[str, Any]:
    return retry_unsynced_auxiliary_submissions(settings_from_request(request))
