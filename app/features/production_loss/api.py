from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from ...core.security import require_api_auth
from ...domain.request_settings import settings_from_request
from .schemas import ProductionLossReportCreate, ProductionLossReportListResponse
from .service import (
    ProductionLossReportError,
    create_production_loss_report,
    get_production_loss_report,
    list_production_loss_reports,
)

router = APIRouter(
    prefix="/api/production-loss-reports",
    dependencies=[Depends(require_api_auth)],
)


@router.post("")
def create_report(
    payload: ProductionLossReportCreate,
    request: Request,
) -> dict[str, Any]:
    settings = settings_from_request(request)
    try:
        return create_production_loss_report(
            settings,
            date_from=payload.date_from,
            date_to=payload.date_to,
            refresh_ifs=payload.refresh_ifs,
        ).as_dict()
    except ProductionLossReportError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc


@router.get("", response_model=ProductionLossReportListResponse)
def list_reports(
    request: Request,
    limit: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    settings = settings_from_request(request)
    return {"reports": list_production_loss_reports(settings, limit=limit)}


@router.get("/{report_id}")
def get_report(
    report_id: int,
    request: Request,
) -> dict[str, Any]:
    settings = settings_from_request(request)
    report = get_production_loss_report(settings, report_id)
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Production loss report not found.",
        )
    return report
