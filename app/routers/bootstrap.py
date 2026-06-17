from typing import Any

from fastapi import APIRouter, Depends, Request

from ..auth import require_api_auth
from ..database import create_session
from ..domain import shifts
from ..domain.request_settings import settings_from_request
from ..integrations.ifs_client import fetch_pet_ongoing_operations
from ..services.amount_control_service import machine_options
from ..services.auxiliary_systems_service import check_auxiliary_systems_reachable
from ..services.auxiliary_systems_sync_service import latest_auxiliary_sync_error
from ..services.process_records import production_engineer_options
from ..services.shop_order_source import ifs_shop_order_source_payload
from ..services.sync_service import (
    latest_sync_error,
    latest_tour_context,
    serialize_tour_context,
)

router = APIRouter(prefix="/api", dependencies=[Depends(require_api_auth)])


def _unavailable_shop_order_payload(source: str, error: Exception) -> dict[str, Any]:
    return {
        "available": False,
        "source": source,
        "last_error": str(error),
        "operation_count": 0,
        "order_count": 0,
        "resource_count": 0,
        "options": [],
    }


async def _shop_order_payload(settings) -> dict[str, Any]:
    try:
        rows = await fetch_pet_ongoing_operations(settings)
        return ifs_shop_order_source_payload(rows)
    except Exception as exc:
        return _unavailable_shop_order_payload("ifs", exc)


async def _bootstrap_payload(settings) -> dict[str, Any]:
    auxiliary_systems = check_auxiliary_systems_reachable(settings)
    return {
        "excel": {
            "available": True,
            "database_backed": True,
            "last_error": None,
        },
        "auxiliary_systems": {
            "form_available": auxiliary_systems.form_available,
            "target_available": auxiliary_systems.target_available,
            "form_error": auxiliary_systems.form_error or None,
            "target_error": auxiliary_systems.target_error or None,
        },
        "shop_order_source": await _shop_order_payload(settings),
    }


@router.get("/bootstrap")
async def bootstrap(request: Request) -> dict[str, Any]:
    settings = settings_from_request(request)
    payload = await _bootstrap_payload(settings)
    payload["current_tour_timing"] = shifts.automatic_tour_timing(settings)
    payload["current_auxiliary_date"] = shifts.recorded_date(
        shifts.request_datetime(settings).date()
    )
    with create_session(settings) as session:
        payload["machines"] = machine_options(session)
        payload["production_engineers"] = production_engineer_options(session)
        payload["latest_tour_context"] = serialize_tour_context(
            latest_tour_context(session)
        )
        payload["last_sync_error"] = latest_sync_error(session)
        payload["last_auxiliary_sync_error"] = latest_auxiliary_sync_error(session)
    return payload


@router.get("/tour-context/defaults")
def tour_context_defaults(request: Request) -> dict[str, str]:
    return shifts.automatic_tour_timing(settings_from_request(request))
