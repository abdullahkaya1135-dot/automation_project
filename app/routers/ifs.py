from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from ..domain.request_settings import settings_from_request
from ..modules.auth.service import require_api_auth
from ..modules.ifs.errors import IFSClientError, IFSConfigurationError
from ..modules.ifs.use_cases import (
    operation_hm02_materials_payload,
    pet_ongoing_operations_payload,
    u1_hm02_stock_payload,
    u1_return_candidates_payload,
    used_hm02_materials_payload,
)
from ..modules.production_planning.errors import ProductionPlanningError

router = APIRouter(prefix="/api/ifs", dependencies=[Depends(require_api_auth)])


def _ifs_http_exception(
    exc: IFSConfigurationError | IFSClientError | ProductionPlanningError,
) -> HTTPException:
    if isinstance(exc, IFSClientError):
        return HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        )
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=str(exc),
    )


@router.get("/u1-hm02-stock")
async def ifs_u1_hm02_stock(request: Request) -> dict[str, Any]:
    settings = settings_from_request(request)
    try:
        return await u1_hm02_stock_payload(settings)
    except (IFSConfigurationError, IFSClientError) as exc:
        raise _ifs_http_exception(exc) from exc


@router.get("/pet-ongoing-operations")
async def ifs_pet_ongoing_operations(request: Request) -> dict[str, Any]:
    settings = settings_from_request(request)
    try:
        return await pet_ongoing_operations_payload(settings)
    except (IFSConfigurationError, IFSClientError) as exc:
        raise _ifs_http_exception(exc) from exc


@router.get("/operation-hm02-materials")
async def ifs_operation_hm02_materials(
    request: Request,
    order_no: str = Query(..., min_length=1),
    operation_no: int = Query(...),
    release_no: str = Query("*", min_length=1),
    sequence_no: str = Query("*", min_length=1),
) -> dict[str, Any]:
    settings = settings_from_request(request)
    try:
        return await operation_hm02_materials_payload(
            settings,
            order_no=order_no,
            release_no=release_no,
            sequence_no=sequence_no,
            operation_no=operation_no,
        )
    except (IFSConfigurationError, IFSClientError) as exc:
        raise _ifs_http_exception(exc) from exc


@router.get("/used-hm02-materials")
async def ifs_used_hm02_materials(request: Request) -> dict[str, Any]:
    settings = settings_from_request(request)
    try:
        return await used_hm02_materials_payload(settings)
    except (IFSConfigurationError, IFSClientError) as exc:
        raise _ifs_http_exception(exc) from exc


@router.get("/u1-return-candidates")
async def ifs_u1_return_candidates(request: Request) -> dict[str, Any]:
    settings = settings_from_request(request)
    try:
        return await u1_return_candidates_payload(settings)
    except (IFSConfigurationError, ProductionPlanningError, IFSClientError) as exc:
        raise _ifs_http_exception(exc) from exc
