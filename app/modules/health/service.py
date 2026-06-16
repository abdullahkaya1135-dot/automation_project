from typing import Any

from ...config import Settings
from ...database import create_session, sqlite_health
from ...shared.excel_write_lock import excel_write_lock_status
from ..auxiliary_systems.sync_service import latest_auxiliary_sync_error
from ..auxiliary_systems.workbook_service import (
    check_auxiliary_systems_reachable,
)
from ..process_entry.workbook_io import check_excel_reachable
from ..sync.process_entry_sync import latest_sync_error


def health_payload(settings: Settings) -> dict[str, Any]:
    sqlite = sqlite_health(settings)
    excel = check_excel_reachable(settings)
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
            and excel.available
            and auxiliary_systems.target_available
            else "degraded"
        ),
        "sqlite": sqlite,
        "excel": {
            "ok": excel.available,
            "error": excel.error or None,
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
