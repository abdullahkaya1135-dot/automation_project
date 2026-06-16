from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status

from ..domain.request_settings import settings_from_request
from ..modules.auth.service import require_api_auth
from ..modules.reports.cycle_report_service import (
    CycleReportError,
    NoTodayRowsError,
)
from ..modules.reports.use_cases import create_today_cycle_report_payload

router = APIRouter(prefix="/api", dependencies=[Depends(require_api_auth)])


@router.post("/cycle-report/today")
def create_today_cycle_report(request: Request) -> dict[str, Any]:
    settings = settings_from_request(request)
    try:
        return create_today_cycle_report_payload(settings)
    except NoTodayRowsError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except CycleReportError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
