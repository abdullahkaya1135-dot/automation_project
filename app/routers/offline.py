from typing import Any

from fastapi import APIRouter, Depends, Request

from ..domain.request_settings import settings_from_request
from ..modules.auth.service import require_api_auth
from ..modules.offline.service import bulk_sync_offline_records as bulk_sync_service
from ..schemas import (
    OfflineBulkSyncRequest,
    OfflineBulkSyncResponse,
)

router = APIRouter(prefix="/api", dependencies=[Depends(require_api_auth)])


@router.post(
    "/offline/bulk-sync",
    response_model=OfflineBulkSyncResponse,
)
def bulk_sync_offline_records(
    payload: OfflineBulkSyncRequest,
    request: Request,
) -> dict[str, Any]:
    settings = settings_from_request(request)
    return bulk_sync_service(settings, payload)
