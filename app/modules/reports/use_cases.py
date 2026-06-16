from typing import Any

from ...config import Settings
from ...domain import shifts
from .cycle_report_service import create_cycle_report


def create_today_cycle_report_payload(settings: Settings) -> dict[str, Any]:
    report_date = shifts.request_datetime(settings).date()
    return create_cycle_report(settings, report_date).as_dict()
