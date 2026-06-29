from __future__ import annotations

import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ...core.config import Settings
from ...features.process_entries.normalization import normalize_machine_code
from ...integrations.ifs.client import fetch_pet_ongoing_operations
from ...services.text_normalization import (
    optional_collapsed_whitespace_text as _optional_text,
)
from ..production_planning import service as _production_planning_service
from ..production_planning.service import resolve_planning_workbook

DEFAULT_REMAINING_PACKAGES_THRESHOLD = Decimal("3")
SHIFT_MANAGER_EXCLUDED_MACHINE_CODES = frozenset({"PKT"})
_SHIFT_MANAGER_EXCLUDED_MACHINE_CODE_LOOKUP = frozenset(
    code.casefold() for code in SHIFT_MANAGER_EXCLUDED_MACHINE_CODES
)
STATUS_NEXT_FOUND = "next_found"
STATUS_MACHINE_NOT_IN_PLAN = "machine_not_in_plan"
STATUS_CURRENT_ORDER_NOT_IN_PLAN = "current_order_not_in_plan"
STATUS_NO_NEXT_JOB = "no_next_job"
STATUS_INVALID_REMAINING_QTY = "invalid_remaining_qty"

_NUMERIC_IDENTIFIER_PATTERN = re.compile(r"\d+[,.]0+")
_PLANNING_MISSING_STATUSES = frozenset(
    {
        STATUS_MACHINE_NOT_IN_PLAN,
        STATUS_CURRENT_ORDER_NOT_IN_PLAN,
        STATUS_NO_NEXT_JOB,
    }
)

_CURRENT_PRODUCT_NO_FIELDS = (
    "PartNo",
    "part_no",
    "current_product_no",
    "product_no",
)
_CURRENT_PRODUCT_DESCRIPTION_FIELDS = (
    "PartNoDesc",
    "part_description",
    "current_product_description",
    "product_description",
    "Description",
    "description",
)
_PLANNING_MACHINE_FIELDS = (
    "machine_code",
    "MachineCode",
    "machine_no",
    "MachineNo",
    "machine",
    "Machine",
    "section_machine_code",
    "PreferredResourceId",
)
_PLANNING_ORDER_FIELDS = (
    "order_no",
    "OrderNo",
    "job_order",
    "JobOrder",
    "shop_order_no",
    "ShopOrderNo",
    "current_order_no",
)
_PLANNING_PRODUCT_FIELDS = (
    "product_no",
    "ProductNo",
    "part_no",
    "PartNo",
    "product_code",
    "ProductCode",
)
_PLANNING_MOLD_FIELDS = (
    "mold",
    "Mold",
    "mold_no",
    "MoldNo",
    "mold_code",
    "MoldCode",
    "kalip",
    "Kalip",
)
_PLANNING_SHEET_FIELDS = ("sheet_name", "SheetName", "planning_sheet_name")
_PLANNING_ROW_NUMBER_FIELDS = (
    "row_number",
    "RowNumber",
    "planning_row_number",
    "PlanningRowNumber",
)


class ShiftManagerServiceError(RuntimeError):
    """Raised when Shift Manager service data cannot be prepared."""


if hasattr(_production_planning_service, "read_machine_planning_rows"):
    read_machine_planning_rows = _production_planning_service.read_machine_planning_rows
else:

    def read_machine_planning_rows(_path: str | Path) -> list[Any]:
        raise ShiftManagerServiceError(
            "Production planning parser read_machine_planning_rows is not available."
        )


@dataclass(frozen=True)
class NormalizedOperation:
    machine_code: str | None
    current_order_no: str | None
    current_product_no: str | None
    current_product_description: str | None
    remaining_quantity: Decimal | None
    package_pallet_size: Decimal | None
    remaining_packages: Decimal | None


@dataclass(frozen=True)
class PlanningJob:
    machine_code: str
    order_no: str
    product_no: str | None
    mold: str | None
    sheet_name: str | None
    row_number: int | None


async def build_shift_manager_payload(
    settings: Settings,
    *,
    threshold: Any = DEFAULT_REMAINING_PACKAGES_THRESHOLD,
    informed_state: Any = None,
    client: Any = None,
    access_token: str | None = None,
) -> dict[str, Any]:
    """Build near-complete active-operation rows with the next planned job."""

    threshold_number = _required_decimal(threshold, "threshold")
    fetch_kwargs: dict[str, Any] = {}
    if client is not None:
        fetch_kwargs["client"] = client
    if access_token is not None:
        fetch_kwargs["access_token"] = access_token

    operations = await fetch_pet_ongoing_operations(
        settings,
        include_inventory_part_pack_size=True,
        **fetch_kwargs,
    )
    included_operations = _included_operations(operations)
    planning_path = resolve_planning_workbook(
        settings.production_planning_dir,
        settings.production_planning_path,
    )
    planning_rows = read_machine_planning_rows(planning_path)

    rows, near_complete_count = _shift_manager_rows(
        included_operations,
        planning_rows,
        threshold=threshold_number,
        informed_state=informed_state,
    )
    status_counts = Counter(row["status"] for row in rows)

    return {
        "summary": {
            "generated_at": _generated_at(settings),
            "threshold": _number_payload(threshold_number),
            "active_operation_count": len(included_operations),
            "active_machine_count": _active_machine_count(included_operations),
            "near_complete_count": near_complete_count,
            "next_job_found_count": status_counts.get(STATUS_NEXT_FOUND, 0),
            "missing_plan_count": sum(
                status_counts.get(status, 0) for status in _PLANNING_MISSING_STATUSES
            ),
            "planning_source_path": str(planning_path),
            "planning_source_name": Path(planning_path).name,
            "row_count": len(rows),
            "status_counts": dict(status_counts),
        },
        "rows": rows,
    }


def _included_operations(
    operations: Sequence[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    return [
        operation
        for operation in operations
        if not _excluded_machine_code(_operation_machine_code(operation))
    ]


def _excluded_machine_code(machine_code: Any) -> bool:
    text = _optional_text(machine_code)
    return text is not None and text.casefold() in (
        _SHIFT_MANAGER_EXCLUDED_MACHINE_CODE_LOOKUP
    )


def shift_manager_row_key(
    machine_code: Any,
    current_order_no: Any,
    next_order_no: Any,
) -> str:
    return "|".join(
        (
            _optional_text(machine_code) or "",
            _normalize_order_no(current_order_no) or "",
            _normalize_order_no(next_order_no) or "",
        )
    )


def _shift_manager_rows(
    operations: Sequence[Mapping[str, Any]],
    planning_rows: Sequence[Any],
    *,
    threshold: Decimal,
    informed_state: Any,
) -> tuple[list[dict[str, Any]], int]:
    jobs_by_machine = _planning_jobs_by_machine(planning_rows)
    rows: list[dict[str, Any]] = []
    near_complete_count = 0

    for operation in operations:
        normalized = _normalize_operation(operation)
        if _excluded_machine_code(normalized.machine_code):
            continue
        if normalized.remaining_packages is None:
            rows.append(
                _payload_row(
                    normalized,
                    status=STATUS_INVALID_REMAINING_QTY,
                    next_job=None,
                    planning_reference_job=None,
                    informed_state=informed_state,
                )
            )
            continue
        if normalized.remaining_packages > threshold:
            continue

        near_complete_count += 1
        status, next_job, planning_reference_job = _next_job_status(
            normalized,
            jobs_by_machine,
        )
        rows.append(
            _payload_row(
                normalized,
                status=status,
                next_job=next_job,
                planning_reference_job=planning_reference_job,
                informed_state=informed_state,
            )
        )

    return rows, near_complete_count


def _normalize_operation(row: Mapping[str, Any]) -> NormalizedOperation:
    remaining_quantity = _decimal(
        _first_row_value(row, ("RemainingQty", "remaining_qty", "remaining_quantity"))
    )
    package_pallet_size = _package_pallet_size(row)
    return NormalizedOperation(
        machine_code=_operation_machine_code(row),
        current_order_no=_normalize_order_no(row.get("OrderNo")),
        current_product_no=_first_text(row, _CURRENT_PRODUCT_NO_FIELDS),
        current_product_description=_first_text(
            row,
            _CURRENT_PRODUCT_DESCRIPTION_FIELDS,
        ),
        remaining_quantity=remaining_quantity,
        package_pallet_size=package_pallet_size,
        remaining_packages=_remaining_package_pallet_count(
            remaining_quantity,
            package_pallet_size,
        ),
    )


def _package_pallet_size(row: Mapping[str, Any]) -> Decimal | None:
    direct_value = _first_row_value(
        row,
        (
            "Cf_Palet_Ici_Miktar",
            "cf_palet_ici_miktar",
            "package_pallet_size",
            "packagePalletSize",
            "pallet_size",
            "palletSize",
            "pack_size",
            "packSize",
        ),
    )
    if direct_value is not None:
        return _decimal(direct_value)

    for nested_name in (
        "InventoryPartRef",
        "inventory_part_ref",
        "inventoryPartRef",
        "inventory_part",
        "inventoryPart",
    ):
        nested = row.get(nested_name)
        if isinstance(nested, Mapping):
            return _decimal(
                _first_row_value(
                    nested,
                    (
                        "Cf_Palet_Ici_Miktar",
                        "cf_palet_ici_miktar",
                        "package_pallet_size",
                        "pallet_size",
                    ),
                )
            )
    return None


def _operation_machine_code(row: Mapping[str, Any]) -> str | None:
    raw_value = _first_row_value(
        row,
        (
            "PreferredResourceId",
            "preferred_resource_id",
            "ResourceId",
            "resource_id",
            "MachineCode",
            "machine_code",
            "machine",
        ),
    )
    return normalize_machine_code(raw_value) or _optional_text(raw_value)


def _remaining_package_pallet_count(
    remaining_quantity: Decimal | None,
    package_pallet_size: Decimal | None,
) -> Decimal | None:
    if (
        remaining_quantity is None
        or package_pallet_size is None
        or package_pallet_size <= 0
    ):
        return None
    return remaining_quantity / package_pallet_size


def _next_job_status(
    operation: NormalizedOperation,
    jobs_by_machine: Mapping[str, list[PlanningJob]],
) -> tuple[str, PlanningJob | None, PlanningJob | None]:
    if operation.machine_code is None:
        return STATUS_MACHINE_NOT_IN_PLAN, None, None

    machine_jobs = jobs_by_machine.get(operation.machine_code)
    if not machine_jobs:
        return STATUS_MACHINE_NOT_IN_PLAN, None, None

    if operation.current_order_no is None:
        return STATUS_CURRENT_ORDER_NOT_IN_PLAN, None, None

    for index, job in enumerate(machine_jobs):
        if job.order_no != operation.current_order_no:
            continue
        for next_job in machine_jobs[index + 1 :]:
            if next_job.order_no != operation.current_order_no:
                return STATUS_NEXT_FOUND, next_job, next_job
        return STATUS_NO_NEXT_JOB, None, job

    return STATUS_CURRENT_ORDER_NOT_IN_PLAN, None, None


def _planning_jobs_by_machine(
    planning_rows: Sequence[Any],
) -> dict[str, list[PlanningJob]]:
    jobs_by_machine: dict[str, list[PlanningJob]] = {}
    for row in planning_rows:
        if not _planning_row_is_visible(row):
            continue

        machine_code = normalize_machine_code(
            _first_row_value(row, _PLANNING_MACHINE_FIELDS)
        )
        order_no = _normalize_order_no(_first_row_value(row, _PLANNING_ORDER_FIELDS))
        if machine_code is None or order_no is None:
            continue

        jobs_by_machine.setdefault(machine_code, []).append(
            PlanningJob(
                machine_code=machine_code,
                order_no=order_no,
                product_no=_optional_text(
                    _first_row_value(row, _PLANNING_PRODUCT_FIELDS)
                ),
                mold=_optional_text(_first_row_value(row, _PLANNING_MOLD_FIELDS)),
                sheet_name=_optional_text(
                    _first_row_value(row, _PLANNING_SHEET_FIELDS)
                ),
                row_number=_int_value(
                    _first_row_value(row, _PLANNING_ROW_NUMBER_FIELDS)
                ),
            )
        )
    return jobs_by_machine


def _planning_row_is_visible(row: Any) -> bool:
    visible = _bool_value(_first_row_value(row, ("visible", "is_visible", "Visible")))
    if visible is False:
        return False
    hidden = _bool_value(
        _first_row_value(row, ("hidden", "is_hidden", "Hidden", "row_hidden"))
    )
    return hidden is not True


def _active_machine_count(operations: Sequence[Mapping[str, Any]]) -> int:
    return len(
        {
            machine_code
            for operation in operations
            if (machine_code := _operation_machine_code(operation)) is not None
        }
    )


def _payload_row(
    operation: NormalizedOperation,
    *,
    status: str,
    next_job: PlanningJob | None,
    planning_reference_job: PlanningJob | None,
    informed_state: Any,
) -> dict[str, Any]:
    planning_sheet_name = (
        planning_reference_job.sheet_name
        if planning_reference_job is not None
        else None
    )
    planning_row_number = (
        planning_reference_job.row_number
        if planning_reference_job is not None
        else None
    )
    next_order_no = next_job.order_no if next_job is not None else None
    row = {
        "machine_code": operation.machine_code,
        "current_order_no": operation.current_order_no,
        "current_product_no": operation.current_product_no,
        "current_product_description": operation.current_product_description,
        "remaining_quantity": _number_payload(operation.remaining_quantity),
        "package_pallet_size": _number_payload(operation.package_pallet_size),
        "remaining_package_pallet": _number_payload(operation.remaining_packages),
        "remaining_packages": _number_payload(operation.remaining_packages),
        "remaining_package_pallet_count": _number_payload(operation.remaining_packages),
        "next_order_no": next_order_no,
        "next_product_no": next_job.product_no if next_job is not None else None,
        "next_mold": next_job.mold if next_job is not None else None,
        "planning_sheet_name": planning_sheet_name,
        "planning_row_number": planning_row_number,
        "row_number": planning_row_number,
        "planning_match_found": status == STATUS_NEXT_FOUND,
        "status": status,
    }
    row["informed"] = _is_informed(row, informed_state)
    return row


def _is_informed(
    row: Mapping[str, Any],
    informed_state: Any,
) -> bool:
    if not informed_state:
        return False
    key = shift_manager_row_key(
        row.get("machine_code"),
        row.get("current_order_no"),
        row.get("next_order_no"),
    )
    machine_code = _optional_text(row.get("machine_code"))
    current_order_no = _normalize_order_no(row.get("current_order_no"))
    next_order_no = _normalize_order_no(row.get("next_order_no"))
    if isinstance(informed_state, Mapping):
        tuple_key = (machine_code, current_order_no, next_order_no)
        return bool(
            informed_state.get(key, False) or informed_state.get(tuple_key, False)
        )
    if isinstance(informed_state, Sequence) and not isinstance(
        informed_state,
        str | bytes | bytearray,
    ):
        for item in informed_state:
            if item == key or item == (machine_code, current_order_no, next_order_no):
                return True
            if isinstance(item, Mapping) and _informed_mapping_matches_row(
                item,
                key,
                machine_code,
                current_order_no,
                next_order_no,
            ):
                return True
    return False


def _informed_mapping_matches_row(
    informed_row: Mapping[str, Any],
    key: str,
    machine_code: str | None,
    current_order_no: str | None,
    next_order_no: str | None,
) -> bool:
    notification_key = _optional_text(
        _first_row_value(informed_row, ("notification_key", "key"))
    )
    if notification_key and notification_key != key:
        return False

    informed_machine = normalize_machine_code(
        _first_row_value(informed_row, ("machine_code", "machine"))
    )
    informed_current = _normalize_order_no(
        _first_row_value(
            informed_row,
            ("current_order_no", "current_job_order", "order_no", "job_order"),
        )
    )
    informed_next = _normalize_order_no(
        _first_row_value(informed_row, ("next_order_no", "next_job_order"))
    )
    identity_matches = (
        informed_machine == machine_code
        and informed_current == current_order_no
        and informed_next == next_order_no
    )
    if notification_key != key and not identity_matches:
        return False

    return any(
        _bool_value(_first_row_value(informed_row, (field_name,))) is True
        for field_name in ("informed", "shift_manager_informed", "notified")
    )


def _normalize_order_no(value: Any) -> str | None:
    if isinstance(value, bool):
        return None
    text = _optional_text(value)
    if text is None:
        return None
    if _NUMERIC_IDENTIFIER_PATTERN.fullmatch(text):
        return text.split(".", 1)[0].split(",", 1)[0]
    return text


def _first_text(row: Mapping[str, Any], field_names: Sequence[str]) -> str | None:
    return _optional_text(_first_row_value(row, field_names))


def _first_row_value(row: Any, field_names: Sequence[str]) -> Any:
    if isinstance(row, Mapping):
        for field_name in field_names:
            if field_name in row:
                return row[field_name]

        values_by_lower_name = {
            str(field_name).casefold(): value for field_name, value in row.items()
        }
        for field_name in field_names:
            lowered = field_name.casefold()
            if lowered in values_by_lower_name:
                return values_by_lower_name[lowered]
        return None

    for field_name in field_names:
        if hasattr(row, field_name):
            return getattr(row, field_name)
    return None


def _required_decimal(value: Any, field_name: str) -> Decimal:
    number = _decimal(value)
    if number is None:
        raise ShiftManagerServiceError(f"{field_name} must be numeric.")
    return number


def _decimal(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        number = value
    elif isinstance(value, int | float):
        number = Decimal(str(value))
    else:
        text = _optional_text(value)
        if text is None:
            return None
        normalized = _normalized_decimal_text(text)
        try:
            number = Decimal(normalized)
        except InvalidOperation:
            return None

    if not number.is_finite():
        return None
    return number


def _normalized_decimal_text(value: str) -> str:
    text = value.replace(" ", "")
    if "," not in text:
        return text
    if "." not in text:
        return text.replace(",", ".")
    if text.rfind(",") > text.rfind("."):
        return text.replace(".", "").replace(",", ".")
    return text.replace(",", "")


def _number_payload(value: Decimal | None) -> int | float | None:
    if value is None:
        return None
    if value == value.to_integral_value():
        return int(value)
    return float(value)


def _int_value(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except TypeError, ValueError:
        try:
            return int(Decimal(str(value)))
        except InvalidOperation, ValueError:
            return None


def _bool_value(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    text = _optional_text(value)
    if text is None:
        return None
    lowered = text.casefold()
    if lowered in {"1", "true", "yes", "y"}:
        return True
    if lowered in {"0", "false", "no", "n"}:
        return False
    return None


def _generated_at(settings: Settings) -> str:
    try:
        tzinfo = ZoneInfo(settings.timezone)
    except ZoneInfoNotFoundError:
        tzinfo = None
    return datetime.now(tzinfo).isoformat(timespec="seconds")
