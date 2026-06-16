from typing import Any

from ...config import Settings
from ...database import create_session
from ...domain import shifts
from ..auxiliary_systems.sync_service import latest_auxiliary_sync_error
from ..auxiliary_systems.workbook_service import (
    check_auxiliary_systems_reachable,
)
from ..ifs.operations import fetch_pet_ongoing_operations
from ..process_entry.workbook_io import check_excel_reachable
from ..shop_orders.source import ifs_shop_order_source_payload
from ..sync.process_entry_sync import latest_sync_error
from ..sync.serializers import serialize_tour_context
from ..tour_context.repository import latest_tour_context
from .field_definitions import field_definitions_payload


def unavailable_shop_order_payload(source: str, error: Exception) -> dict[str, Any]:
    return {
        "available": False,
        "source": source,
        "last_error": str(error),
        "operation_count": 0,
        "order_count": 0,
        "resource_count": 0,
        "options": [],
    }


async def shop_order_payload(settings: Settings) -> dict[str, Any]:
    try:
        rows = await fetch_pet_ongoing_operations(settings)
        return ifs_shop_order_source_payload(rows)
    except Exception as exc:
        return unavailable_shop_order_payload("ifs", exc)


async def bootstrap_payload(settings: Settings) -> dict[str, Any]:
    excel = check_excel_reachable(settings)
    auxiliary_systems = check_auxiliary_systems_reachable(settings)
    payload: dict[str, Any] = {
        "excel": {
            "available": excel.available,
            "last_error": excel.error or None,
        },
        "auxiliary_systems": {
            "form_available": auxiliary_systems.form_available,
            "target_available": auxiliary_systems.target_available,
            "form_error": auxiliary_systems.form_error or None,
            "target_error": auxiliary_systems.target_error or None,
        },
        "shop_order_source": await shop_order_payload(settings),
        "field_definitions": field_definitions_payload(),
        "current_tour_timing": shifts.automatic_tour_timing(settings),
        "current_auxiliary_date": shifts.recorded_date(
            shifts.request_datetime(settings).date()
        ),
    }

    with create_session(settings) as session:
        payload["latest_tour_context"] = serialize_tour_context(
            latest_tour_context(session)
        )
        payload["last_sync_error"] = latest_sync_error(session)
        payload["last_auxiliary_sync_error"] = latest_auxiliary_sync_error(session)
    return payload


def tour_context_defaults(settings: Settings) -> dict[str, str]:
    return shifts.automatic_tour_timing(settings)
