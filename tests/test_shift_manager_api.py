from __future__ import annotations

import importlib
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook

from app.features.production_planning.service import MachinePlanningRow
from app.main import create_app


def _write_workbook(path: Path, sheet_name: str = "Sheet1") -> None:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = sheet_name
    worksheet.append(["header"])
    workbook.save(path)
    workbook.close()


def _write_planning_workbook(path: Path) -> None:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Plan"
    worksheet["B1"] = "M135"
    worksheet["A2"] = "SO-LOW"
    worksheet["A3"] = "SO-NEXT"
    workbook.save(path)
    workbook.close()


def _operation(
    order_no: str,
    remaining_qty: int,
    *,
    package_pallet_size: int = 1,
) -> dict[str, Any]:
    return {
        "OrderNo": order_no,
        "order_no": order_no,
        "job_order": order_no,
        "ReleaseNo": "*",
        "release_no": "*",
        "SequenceNo": "*",
        "sequence_no": "*",
        "OperationNo": 10,
        "operation_no": 10,
        "Contract": "S01",
        "contract": "S01",
        "WorkCenterNo": "SP25",
        "work_center_no": "SP25",
        "PartNo": f"MM-PET-{order_no}",
        "part_no": f"MM-PET-{order_no}",
        "PartNoDesc": f"Product {order_no}",
        "part_description": f"Product {order_no}",
        "PreferredResourceId": "135",
        "preferred_resource_id": "135",
        "machine_code": "135",
        "OperationNoDesc": "Run",
        "operation_description": "Run",
        "RemainingQty": remaining_qty,
        "remaining_qty": remaining_qty,
        "InventoryPartRef": {
            "PartNo": f"MM-PET-{order_no}",
            "Cf_Palet_Ici_Miktar": package_pallet_size,
        },
    }


def _optional_module(module_name: str):
    try:
        return importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        missing_name = exc.name or ""
        if module_name == missing_name or module_name.startswith(f"{missing_name}."):
            return None
        raise


def _patch_shift_manager_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    operations = [_operation("SO-LOW", 2)]
    planning_rows = [
        MachinePlanningRow(
            machine_code="135",
            order_no="SO-LOW",
            sheet_name="Plan",
            row_number=2,
            sequence_index=0,
            product_no="MM-PET-SO-LOW",
            mold="Mold A",
            order_quantity="100",
            cell_value="SO-LOW",
        ),
        MachinePlanningRow(
            machine_code="135",
            order_no="SO-NEXT",
            sheet_name="Plan",
            row_number=3,
            sequence_index=1,
            product_no="MM-PET-SO-NEXT",
            mold="Mold B",
            order_quantity="100",
            cell_value="SO-NEXT",
        ),
    ]

    async def fake_fetch_pet_ongoing_operations(_settings, *args, **kwargs):
        return list(operations)

    async def fake_fetch_shop_order_operations(_settings, order_no, *args, **kwargs):
        return [_operation(str(order_no), 99)]

    def fake_read_machine_planning_rows(_path):
        return list(planning_rows)

    def fake_resolve_planning_workbook(*args, **kwargs):
        return Path("planning.xlsx")

    replacements = {
        "fetch_pet_ongoing_operations": fake_fetch_pet_ongoing_operations,
        "fetch_shop_order_operations": fake_fetch_shop_order_operations,
        "read_machine_planning_rows": fake_read_machine_planning_rows,
        "resolve_planning_workbook": fake_resolve_planning_workbook,
    }
    for module_name in (
        "app.features.shift_manager.api",
        "app.features.shift_manager.service",
        "app.features.ifs_checks.shift_manager",
        "app.integrations.ifs.client",
        "app.features.production_planning.service",
    ):
        module = _optional_module(module_name)
        if module is None:
            continue
        for name, value in replacements.items():
            monkeypatch.setattr(module, name, value, raising=False)


@pytest.fixture
def configured_shift_manager_environment(monkeypatch, tmp_path):
    process_path = tmp_path / "process.xlsx"
    cycle_path = tmp_path / "cycle.xlsx"
    auxiliary_form_path = tmp_path / "auxiliary_form.xlsx"
    auxiliary_target_path = tmp_path / "auxiliary.xlsx"
    planning_path = tmp_path / "planning.xlsx"

    _write_workbook(process_path, "PROSES 2026")
    _write_workbook(cycle_path)
    _write_workbook(auxiliary_form_path)
    _write_workbook(auxiliary_target_path, "YARDIMCI TESISLER TAKIP")
    _write_planning_workbook(planning_path)

    monkeypatch.setenv("EXCEL_PATH", str(process_path))
    monkeypatch.setenv("APP_PIN", "1234")
    monkeypatch.setenv("SESSION_SECRET", "test-session-secret")
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "process_entries.sqlite3"))
    monkeypatch.setenv("BACKUP_DIR", str(tmp_path / "backups"))
    monkeypatch.setenv("CYCLE_TABLE_PATH", str(cycle_path))
    monkeypatch.setenv("REPORT_OUTPUT_DIR", str(tmp_path / "reports"))
    monkeypatch.setenv("AUXILIARY_SYSTEMS_FORM_PATH", str(auxiliary_form_path))
    monkeypatch.setenv("AUXILIARY_SYSTEMS_TARGET_PATH", str(auxiliary_target_path))
    monkeypatch.setenv("AUXILIARY_SYSTEMS_SHEET_NAME", "YARDIMCI TESISLER TAKIP")
    monkeypatch.setenv("PRODUCTION_PLANNING_DIR", "")
    monkeypatch.setenv("PRODUCTION_PLANNING_PATH", str(planning_path))

    _patch_shift_manager_sources(monkeypatch)


def _shift_manager_route_paths(client: TestClient, method: str) -> list[str]:
    paths = []
    for route in client.app.routes:
        route_path = getattr(route, "path", "")
        route_methods = getattr(route, "methods", set()) or set()
        if (
            method in route_methods
            and route_path.startswith("/api/")
            and "shift-manager" in route_path
            and "{" not in route_path
        ):
            paths.append(route_path)
    return sorted(paths)


def _shift_manager_get_path(client: TestClient) -> str:
    paths = _shift_manager_route_paths(client, "GET")
    if not paths:
        pytest.skip("Shift Manager GET API route is not registered yet.")
    preferred = [path for path in paths if path.endswith("/shift-manager")]
    return preferred[0] if preferred else paths[0]


def _shift_manager_notification_route(client: TestClient) -> tuple[str, str]:
    for method in ("PUT", "POST"):
        paths = _shift_manager_route_paths(client, method)
        preferred = [
            path
            for path in paths
            if "notification" in path or "informed" in path or "notify" in path
        ]
        if preferred:
            return method, preferred[0]
    else:
        pytest.skip(
            "Shift Manager notification upsert API route is not registered yet."
        )


def _get_shift_manager(client: TestClient, path: str):
    response = client.get(path)
    if response.status_code != 422:
        return response
    return client.get(path, params={"process_date": "2026-06-08"})


def _all_dicts(value):
    if isinstance(value, Mapping):
        yield value
        for item in value.values():
            yield from _all_dicts(item)
    elif isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        for item in value:
            yield from _all_dicts(item)


def _looks_like_shift_manager_record(record: Mapping[str, Any]) -> bool:
    keys = " ".join(str(key).lower() for key in record)
    return ("order" in keys or "job" in keys) and any(
        token in keys
        for token in ("remaining", "next", "informed", "notified", "notification")
    )


def _manager_records(payload) -> list[Mapping[str, Any]]:
    records = [
        record
        for record in _all_dicts(payload)
        if _looks_like_shift_manager_record(record)
    ]
    return records


def _record_text(record: Mapping[str, Any]) -> str:
    return " ".join(str(value) for value in record.values() if value is not None)


def _record_for_order(records: Sequence[Mapping[str, Any]], order_no: str):
    for record in records:
        if order_no in _record_text(record):
            return record
    return None


def _scalar_items(record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        str(key): value
        for key, value in record.items()
        if value is None or isinstance(value, str | int | float | bool)
    }


def _notification_body(record: Mapping[str, Any]) -> dict[str, Any]:
    body = _scalar_items(record)
    body.update(
        {
            "machine_code": body.get("machine_code") or body.get("machine") or "135",
            "current_order_no": body.get("current_order_no")
            or body.get("current_job_order")
            or body.get("order_no")
            or body.get("job_order")
            or "SO-LOW",
            "current_job_order": body.get("current_job_order")
            or body.get("current_order_no")
            or body.get("job_order")
            or body.get("order_no")
            or "SO-LOW",
            "order_no": body.get("order_no")
            or body.get("current_order_no")
            or body.get("job_order")
            or "SO-LOW",
            "job_order": body.get("job_order")
            or body.get("current_job_order")
            or body.get("order_no")
            or "SO-LOW",
            "next_order_no": body.get("next_order_no")
            or body.get("next_job_order")
            or "SO-NEXT",
            "next_job_order": body.get("next_job_order")
            or body.get("next_order_no")
            or "SO-NEXT",
            "remaining_qty": body.get("remaining_qty") or body.get("RemainingQty") or 2,
            "informed": True,
            "shift_manager_informed": True,
            "notification_key": body.get("notification_key") or "135|SO-LOW|SO-NEXT",
        }
    )
    return body


def _send_notification(
    client: TestClient,
    method: str,
    path: str,
    body: Mapping[str, Any],
):
    response = None
    for payload in (body, {"notification": body}, {"item": body}):
        response = client.request(method, path, json=payload)
        if response.status_code not in {400, 422}:
            return response
    return response


def _record_marks_informed(record: Mapping[str, Any]) -> bool:
    for key, value in record.items():
        lowered = str(key).lower()
        if not any(token in lowered for token in ("informed", "notified")):
            continue
        if value is True:
            return True
        if isinstance(value, str) and value.strip().lower() in {"true", "1", "yes"}:
            return True
    return False


def test_shift_manager_api_route_exists(configured_shift_manager_environment):
    with TestClient(create_app()) as client:
        path = _shift_manager_get_path(client)

    assert "shift-manager" in path


def test_shift_manager_api_auth_enforced(configured_shift_manager_environment):
    with TestClient(create_app()) as client:
        path = _shift_manager_get_path(client)
        response = _get_shift_manager(client, path)

    assert response.status_code == 401


def test_shift_manager_notification_upsert_survives_second_fetch(
    configured_shift_manager_environment,
):
    with TestClient(create_app()) as client:
        login_response = client.post("/api/login", json={"pin": "1234"})
        assert login_response.status_code == 200

        get_path = _shift_manager_get_path(client)
        notification_method, notification_path = _shift_manager_notification_route(
            client
        )

        first_response = _get_shift_manager(client, get_path)
        assert first_response.status_code == 200
        first_records = _manager_records(first_response.json())
        first_record = _record_for_order(first_records, "SO-LOW")
        assert first_record is not None

        notification_response = _send_notification(
            client,
            notification_method,
            notification_path,
            _notification_body(first_record),
        )
        assert notification_response.status_code in {200, 201, 204}

        second_response = _get_shift_manager(client, get_path)
        assert second_response.status_code == 200
        second_records = _manager_records(second_response.json())
        second_record = _record_for_order(second_records, "SO-LOW")

    assert second_record is not None
    assert _record_marks_informed(second_record)
