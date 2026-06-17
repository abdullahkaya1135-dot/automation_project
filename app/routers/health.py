from typing import Any

from fastapi import APIRouter, Request

from ..database import create_session, sqlite_health
from ..domain.request_settings import settings_from_request
from ..services.auxiliary_systems_service import check_auxiliary_systems_reachable
from ..services.auxiliary_systems_sync_service import latest_auxiliary_sync_error
from ..services.excel_write_lock import excel_write_lock_status
from ..services.sync_service import latest_sync_error

router = APIRouter()


@router.get("/health")
def health(request: Request) -> dict[str, Any]:
    settings = settings_from_request(request)
    sqlite = sqlite_health(settings)
    auxiliary_systems = check_auxiliary_systems_reachable(settings)
    last_error = None
    last_auxiliary_error = None
    if sqlite["ok"]:
        with create_session(settings) as session:
            last_error = latest_sync_error(session)
            last_auxiliary_error = latest_auxiliary_sync_error(session)
    return {
        "status": (
            "ok"
            if sqlite["ok"]
            and auxiliary_systems.target_available
            else "degraded"
        ),
        "sqlite": sqlite,
        "process_data": {
            "ok": sqlite["ok"],
            "database_backed": True,
            "error": sqlite["error"] or None,
        },
        "auxiliary_systems": {
            "form_ok": auxiliary_systems.form_available,
            "target_ok": auxiliary_systems.target_available,
            "form_error": auxiliary_systems.form_error or None,
            "target_error": auxiliary_systems.target_error or None,
        },
        "excel_write_lock": excel_write_lock_status(),
        "last_sync_error": last_error,
        "last_auxiliary_sync_error": last_auxiliary_error,
    }
