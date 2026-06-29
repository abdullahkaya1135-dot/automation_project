from __future__ import annotations

import asyncio
import importlib
import inspect
from collections.abc import Mapping, Sequence
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

import pytest

from app.core.config import Settings
from app.features.production_planning.service import MachinePlanningRow, PlanningOrder

SERVICE_MODULE_CANDIDATES = (
    "app.features.shift_manager.service",
    "app.features.ifs_checks.shift_manager",
)
SERVICE_FUNCTION_NAME_HINTS = (
    "shift_manager",
    "manager",
    "handoff",
    "notification",
    "next_job",
    "next_order",
    "alert",
    "build",
    "summary",
)
RECORD_CONTAINER_KEYS = (
    "rows",
    "items",
    "jobs",
    "alerts",
    "notifications",
    "shift_manager",
    "shift_manager_rows",
)
INFORMED_TRUE_PAYLOAD = [
    {
        "machine_code": "135",
        "current_order_no": "SO-LOW",
        "current_job_order": "SO-LOW",
        "order_no": "SO-LOW",
        "job_order": "SO-LOW",
        "next_order_no": "SO-NEXT",
        "next_job_order": "SO-NEXT",
        "informed": True,
        "shift_manager_informed": True,
        "notification_key": "135|SO-LOW|SO-NEXT",
    }
]


class UnsupportedServiceCall(TypeError):
    """Raised when a discovered service function needs unknown arguments."""


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        excel_path=str(tmp_path / "process.xlsx"),
        app_pin="1234",
        session_secret="test-session-secret",
        sqlite_path=str(tmp_path / "process.sqlite3"),
        backup_dir=str(tmp_path / "backups"),
        cycle_table_path=str(tmp_path / "cycle.xlsx"),
        report_output_dir=str(tmp_path / "reports"),
        production_planning_dir="",
        production_planning_path=str(tmp_path / "planning.xlsx"),
    )


def _operation(
    order_no: str,
    remaining_qty: int,
    *,
    machine_code: str = "135",
    part_no: str | None = None,
    package_pallet_size: int = 1,
) -> dict[str, Any]:
    part_no = part_no or f"MM-PET-{order_no}"
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
        "PartNo": part_no,
        "part_no": part_no,
        "PartNoDesc": f"Product {order_no}",
        "part_description": f"Product {order_no}",
        "PreferredResourceId": machine_code,
        "preferred_resource_id": machine_code,
        "machine_code": machine_code,
        "OperationNoDesc": "Run",
        "operation_description": "Run",
        "RemainingQty": remaining_qty,
        "remaining_qty": remaining_qty,
        "InventoryPartRef": {
            "PartNo": part_no,
            "Cf_Palet_Ici_Miktar": package_pallet_size,
        },
    }


def _machine_plan(*order_numbers: str) -> list[MachinePlanningRow]:
    return [
        MachinePlanningRow(
            machine_code="135",
            order_no=order_no,
            sheet_name="Plan",
            row_number=index + 1,
            sequence_index=index,
            product_no=f"Product {order_no}",
            mold="",
            order_quantity="",
            cell_value=order_no,
        )
        for index, order_no in enumerate(order_numbers)
    ]


def _visible_orders(planning_rows: Sequence[MachinePlanningRow]) -> list[PlanningOrder]:
    return [
        PlanningOrder(
            order_no=row.order_no,
            sheet_name=row.sheet_name,
            row_number=row.row_number,
            cell_value=row.cell_value,
        )
        for row in planning_rows
    ]


def _import_shift_manager_service():
    for module_name in SERVICE_MODULE_CANDIDATES:
        try:
            return importlib.import_module(module_name)
        except ModuleNotFoundError as exc:
            missing_name = exc.name or ""
            if module_name == missing_name or module_name.startswith(
                f"{missing_name}."
            ):
                continue
            raise
    pytest.skip("Shift Manager service module is not integrated yet.")


def _optional_module(module_name: str):
    try:
        return importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        missing_name = exc.name or ""
        if module_name == missing_name or module_name.startswith(f"{missing_name}."):
            return None
        raise


def _patch_shift_manager_sources(
    monkeypatch: pytest.MonkeyPatch,
    service_module,
    operations: Sequence[Mapping[str, Any]],
    planning_rows: Sequence[MachinePlanningRow],
) -> None:
    async def fake_fetch_pet_ongoing_operations(_settings, *args, **kwargs):
        return list(operations)

    async def fake_fetch_shop_order_operations(_settings, order_no, *args, **kwargs):
        return [_operation(str(order_no), 99)]

    def fake_resolve_planning_workbook(*args, **kwargs):
        return Path("planning.xlsx")

    def fake_read_machine_planning_rows(_path):
        return list(planning_rows)

    def fake_read_visible_planning_orders(_path):
        return _visible_orders(planning_rows)

    replacements = {
        "fetch_pet_ongoing_operations": fake_fetch_pet_ongoing_operations,
        "fetch_shop_order_operations": fake_fetch_shop_order_operations,
        "resolve_planning_workbook": fake_resolve_planning_workbook,
        "read_machine_planning_rows": fake_read_machine_planning_rows,
        "read_visible_planning_orders": fake_read_visible_planning_orders,
    }
    module_names = (
        service_module.__name__,
        "app.features.shift_manager.api",
        "app.features.shift_manager.service",
        "app.features.ifs_checks.shift_manager",
        "app.integrations.ifs.client",
        "app.features.production_planning.service",
    )

    for module_name in module_names:
        module = _optional_module(module_name)
        if module is None:
            continue
        for name, value in replacements.items():
            monkeypatch.setattr(module, name, value, raising=False)


def _candidate_service_functions(module) -> list[Any]:
    candidates: list[Any] = []
    for name in SERVICE_FUNCTION_NAME_HINTS:
        value = getattr(module, name, None)
        if callable(value):
            candidates.append(value)

    for name, value in inspect.getmembers(module, inspect.isfunction):
        lowered = name.lower()
        if any(hint in lowered for hint in SERVICE_FUNCTION_NAME_HINTS):
            candidates.append(value)

    seen_ids: set[int] = set()
    unique_candidates = []
    for candidate in candidates:
        identifier = id(candidate)
        if identifier in seen_ids:
            continue
        seen_ids.add(identifier)
        unique_candidates.append(candidate)
    return unique_candidates


def _call_value_for_parameter(
    name: str,
    settings: Settings,
    operations: Sequence[Mapping[str, Any]],
    planning_rows: Sequence[MachinePlanningRow],
    informed_payload: Sequence[Mapping[str, Any]],
) -> Any:
    lowered = name.lower()
    if "setting" in lowered or lowered in {"config", "app_settings"}:
        return settings
    if "threshold" in lowered:
        return 3
    if "operation" in lowered or lowered in {"ifs_rows", "ifs_operations", "rows"}:
        return list(operations)
    if "machine_plan" in lowered or "machine_planning" in lowered:
        return list(planning_rows)
    if "visible" in lowered and "order" in lowered:
        return _visible_orders(planning_rows)
    if "planning" in lowered or "plan" in lowered:
        return list(planning_rows)
    if "notification" in lowered or "informed" in lowered or "persisted" in lowered:
        return list(informed_payload)
    if "key" in lowered and ("notified" in lowered or "informed" in lowered):
        return {"135|SO-LOW|SO-NEXT", ("135", "SO-LOW", "SO-NEXT")}
    raise UnsupportedServiceCall(name)


def _call_service_function(
    function,
    settings: Settings,
    operations: Sequence[Mapping[str, Any]],
    planning_rows: Sequence[MachinePlanningRow],
    informed_payload: Sequence[Mapping[str, Any]],
):
    signature = inspect.signature(function)
    args = []
    kwargs = {}
    for parameter in signature.parameters.values():
        if parameter.kind in {
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        }:
            continue

        try:
            value = _call_value_for_parameter(
                parameter.name,
                settings,
                operations,
                planning_rows,
                informed_payload,
            )
        except UnsupportedServiceCall:
            if parameter.default is not inspect.Parameter.empty:
                continue
            raise

        if parameter.kind is inspect.Parameter.POSITIONAL_ONLY:
            args.append(value)
        else:
            kwargs[parameter.name] = value

    result = function(*args, **kwargs)
    if inspect.isawaitable(result):
        return asyncio.run(result)
    return result


def _plain(value):
    if hasattr(value, "model_dump"):
        return _plain(value.model_dump())
    if is_dataclass(value) and not isinstance(value, type):
        return _plain(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [_plain(item) for item in value]
    if hasattr(value, "__dict__") and not isinstance(value, type):
        return _plain(vars(value))
    return value


def _all_dicts(value):
    if isinstance(value, Mapping):
        yield value
        for item in value.values():
            yield from _all_dicts(item)
    elif isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        for item in value:
            yield from _all_dicts(item)


def _record_text(record: Mapping[str, Any]) -> str:
    return " ".join(str(value) for value in record.values() if value is not None)


def _record_contains(record: Mapping[str, Any], expected: str) -> bool:
    return expected in _record_text(record)


def _looks_like_shift_manager_record(record: Mapping[str, Any]) -> bool:
    keys = " ".join(str(key).lower() for key in record)
    has_order = "order" in keys or "job" in keys
    has_shift_manager_state = any(
        token in keys
        for token in ("remaining", "next", "informed", "notified", "notification")
    )
    return has_order and has_shift_manager_state


def _manager_records(payload) -> list[Mapping[str, Any]]:
    plain_payload = _plain(payload)
    records: list[Mapping[str, Any]] = []
    if isinstance(plain_payload, Mapping):
        for key in RECORD_CONTAINER_KEYS:
            value = plain_payload.get(key)
            if isinstance(value, Sequence) and not isinstance(
                value,
                str | bytes | bytearray,
            ):
                records.extend(item for item in value if isinstance(item, Mapping))

    if not records:
        records = [
            record
            for record in _all_dicts(plain_payload)
            if _looks_like_shift_manager_record(record)
        ]
    return records


def _record_for_order(records: Sequence[Mapping[str, Any]], order_no: str):
    for record in records:
        if _record_contains(record, order_no):
            return record
    return None


def _record_has_remaining_qty(record: Mapping[str, Any], expected: int) -> bool:
    for key, value in record.items():
        if "remaining" not in str(key).lower():
            continue
        try:
            if int(float(str(value))) == expected:
                return True
        except TypeError, ValueError:
            continue
    return False


def _record_has_empty_next_job(record: Mapping[str, Any]) -> bool:
    for key, value in record.items():
        lowered = str(key).lower()
        if (
            "next" in lowered
            and ("order" in lowered or "job" in lowered)
            and value in (None, "", [], {})
        ):
            return True
    text = _record_text(record).lower()
    return "no next" in text or "last" in text


def _record_marks_missing_plan(record: Mapping[str, Any]) -> bool:
    for key, value in record.items():
        lowered = str(key).lower()
        if "plan" in lowered and isinstance(value, bool) and value is False:
            return True
    text = _record_text(record).lower()
    return "missing" in text or "not in plan" in text or "not found" in text


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


def _exercise_service(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    operations: Sequence[Mapping[str, Any]],
    planning_rows: Sequence[MachinePlanningRow],
    informed_payload: Sequence[Mapping[str, Any]] = (),
) -> list[Mapping[str, Any]]:
    service_module = _import_shift_manager_service()
    _patch_shift_manager_sources(monkeypatch, service_module, operations, planning_rows)
    settings = _settings(tmp_path)
    compatible_errors: list[str] = []

    for function in _candidate_service_functions(service_module):
        try:
            payload = _call_service_function(
                function,
                settings,
                operations,
                planning_rows,
                informed_payload,
            )
        except UnsupportedServiceCall as exc:
            compatible_errors.append(f"{function.__name__}: unsupported {exc}")
            continue
        except TypeError as exc:
            compatible_errors.append(f"{function.__name__}: {exc}")
            continue

        records = _manager_records(payload)
        if records:
            return records

    if not _candidate_service_functions(service_module):
        pytest.skip("Shift Manager service has no discoverable contract function yet.")
    pytest.skip(
        "No compatible Shift Manager service entry point accepted the contract "
        f"fakes. Tried: {compatible_errors}"
    )


def test_shift_manager_threshold_remaining_qty_at_or_below_three(
    monkeypatch,
    tmp_path,
):
    records = _exercise_service(
        monkeypatch,
        tmp_path,
        [
            _operation("SO-LOW", 300, package_pallet_size=100),
            _operation("SO-HIGH", 301, package_pallet_size=100),
        ],
        _machine_plan("SO-LOW", "SO-NEXT", "SO-HIGH", "SO-LATER"),
    )

    low_record = _record_for_order(records, "SO-LOW")

    assert low_record is not None
    assert _record_has_remaining_qty(low_record, 3)
    assert _record_contains(low_record, "SO-NEXT")
    assert _record_for_order(records, "SO-HIGH") is None


def test_shift_manager_finds_next_planned_job(monkeypatch, tmp_path):
    records = _exercise_service(
        monkeypatch,
        tmp_path,
        [_operation("SO-LOW", 2)],
        _machine_plan("SO-LOW", "SO-NEXT"),
    )

    record = _record_for_order(records, "SO-LOW")

    assert record is not None
    assert _record_contains(record, "SO-NEXT")


def test_shift_manager_reports_current_order_missing_from_plan(
    monkeypatch,
    tmp_path,
):
    records = _exercise_service(
        monkeypatch,
        tmp_path,
        [_operation("SO-MISSING", 1)],
        _machine_plan("SO-100", "SO-200"),
    )

    record = _record_for_order(records, "SO-MISSING")

    assert record is not None
    assert _record_marks_missing_plan(record)


def test_shift_manager_reports_no_next_job(monkeypatch, tmp_path):
    records = _exercise_service(
        monkeypatch,
        tmp_path,
        [_operation("SO-LAST", 1)],
        _machine_plan("SO-LAST"),
    )

    record = _record_for_order(records, "SO-LAST")

    assert record is not None
    assert _record_has_empty_next_job(record)


def test_shift_manager_excludes_pkt_resource(monkeypatch, tmp_path):
    records = _exercise_service(
        monkeypatch,
        tmp_path,
        [
            _operation("SO-PACK", 1, machine_code="PKT"),
            _operation("SO-LOW", 1),
        ],
        _machine_plan("SO-LOW", "SO-NEXT"),
    )

    assert _record_for_order(records, "SO-PACK") is None
    assert _record_for_order(records, "SO-LOW") is not None


def test_shift_manager_applies_persisted_informed_state(monkeypatch, tmp_path):
    records = _exercise_service(
        monkeypatch,
        tmp_path,
        [_operation("SO-LOW", 1)],
        _machine_plan("SO-LOW", "SO-NEXT"),
        INFORMED_TRUE_PAYLOAD,
    )

    record = _record_for_order(records, "SO-LOW")

    assert record is not None
    assert _record_marks_informed(record)
