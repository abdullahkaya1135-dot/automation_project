from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status

from ..auth import require_api_auth
from ..domain import shifts
from ..domain.request_settings import settings_from_request
from ..services.cycle_report_service import (
    CycleReportError,
    NoTodayRowsError,
    create_cycle_report,
)

router = APIRouter(prefix="/api", dependencies=[Depends(require_api_auth)])


@router.post("/cycle-report/today")
def create_today_cycle_report(request: Request) -> dict[str, Any]:
    settings = settings_from_request(request)
    report_date = shifts.request_datetime(settings).date()
    try:
        return create_cycle_report(settings, report_date).as_dict()
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
