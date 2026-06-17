from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from ..auth import require_api_auth
from ..domain.request_settings import settings_from_request
from ..integrations.ifs_client import (
    IFSClientError,
    IFSConfigurationError,
    fetch_operation_hm02_materials,
    fetch_pet_ongoing_operations,
    fetch_u1_hm02_stock,
    fetch_used_hm02_materials,
    find_u1_return_candidates,
    serialize_material_row,
    serialize_operation_row,
    serialize_stock_row,
)
from ..services.production_planning import ProductionPlanningError

router = APIRouter(prefix="/api/ifs", dependencies=[Depends(require_api_auth)])


def _serialize_return_candidate_row(row: dict[str, Any]) -> dict[str, Any]:
    payload = serialize_stock_row(row)
    payload.pop("obj_id", None)
    return payload


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
        rows = await fetch_u1_hm02_stock(settings)
    except (IFSConfigurationError, IFSClientError) as exc:
        raise _ifs_http_exception(exc) from exc

    return {
        "stock_count": len(rows),
        "stock": [serialize_stock_row(row) for row in rows],
    }


@router.get("/pet-ongoing-operations")
async def ifs_pet_ongoing_operations(request: Request) -> dict[str, Any]:
    settings = settings_from_request(request)
    try:
        rows = await fetch_pet_ongoing_operations(settings)
    except (IFSConfigurationError, IFSClientError) as exc:
        raise _ifs_http_exception(exc) from exc

    return {
        "operation_count": len(rows),
        "operations": [serialize_operation_row(row) for row in rows],
    }


@router.get("/operation-hm02-materials")
async def ifs_operation_hm02_materials(
    request: Request,
    order_no: str = Query(..., min_length=1),
    operation_no: int = Query(...),
    release_no: str = Query("*", min_length=1),
    sequence_no: str = Query("*", min_length=1),
) -> dict[str, Any]:
    settings = settings_from_request(request)
    operation = {
        "OrderNo": order_no,
        "ReleaseNo": release_no,
        "SequenceNo": sequence_no,
        "OperationNo": operation_no,
    }
    try:
        rows = await fetch_operation_hm02_materials(settings, operation)
    except (IFSConfigurationError, IFSClientError) as exc:
        raise _ifs_http_exception(exc) from exc

    return {
        "material_count": len(rows),
        "materials": [serialize_material_row(row) for row in rows],
    }


@router.get("/used-hm02-materials")
async def ifs_used_hm02_materials(request: Request) -> dict[str, Any]:
    settings = settings_from_request(request)
    try:
        summary = await fetch_used_hm02_materials(settings)
    except (IFSConfigurationError, IFSClientError) as exc:
        raise _ifs_http_exception(exc) from exc

    return {
        "operation_count": summary["operation_count"],
        "used_material_count": summary["used_material_count"],
        "used_part_count": summary.get(
            "used_part_count",
            summary["used_hm02_part_count"],
        ),
        "used_parts": summary.get("used_parts", summary["used_hm02_parts"]),
        "used_hm02_part_count": summary["used_hm02_part_count"],
        "used_hm02_parts": summary["used_hm02_parts"],
        "used_materials": [
            serialize_material_row(row) for row in summary["used_materials"]
        ],
    }


@router.get("/u1-return-candidates")
async def ifs_u1_return_candidates(request: Request) -> dict[str, Any]:
    settings = settings_from_request(request)
    try:
        summary = await find_u1_return_candidates(settings)
    except (IFSConfigurationError, ProductionPlanningError, IFSClientError) as exc:
        raise _ifs_http_exception(exc) from exc

    return {
        "generated_at": summary["generated_at"],
        "planning_source_path": summary.get("planning_source_path"),
        "planning_source_name": summary.get("planning_source_name"),
        "stock_count": summary["stock_count"],
        "operation_count": summary["operation_count"],
        "active_used_material_count": summary["active_used_material_count"],
        "active_used_part_count": summary.get(
            "active_used_part_count",
            summary["active_used_hm02_part_count"],
        ),
        "active_used_hm02_part_count": summary["active_used_hm02_part_count"],
        "planning_order_count": summary["planning_order_count"],
        "planning_operation_count": summary["planning_operation_count"],
        "planning_used_material_count": summary["planning_used_material_count"],
        "planning_used_part_count": summary.get(
            "planning_used_part_count",
            summary["planning_used_hm02_part_count"],
        ),
        "planning_used_hm02_part_count": summary["planning_used_hm02_part_count"],
        "used_material_count": summary["used_material_count"],
        "used_part_count": summary.get(
            "used_part_count",
            summary["used_hm02_part_count"],
        ),
        "used_hm02_part_count": summary["used_hm02_part_count"],
        "return_candidate_count": summary["return_candidate_count"],
        "return_candidates": [
            _serialize_return_candidate_row(row)
            for row in summary["return_candidates"]
        ],
        "used_parts": summary.get("used_parts", summary["used_hm02_parts"]),
        "used_hm02_parts": summary["used_hm02_parts"],
        "used_materials": [
            serialize_material_row(row) for row in summary["used_materials"]
        ],
    }
