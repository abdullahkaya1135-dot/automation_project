from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import func, select

from ...core.config import Settings
from ...core.database import create_session
from ...features.process_entries.normalization import (
    normalize_machine_code,
    normalize_process_date,
)
from ...models import Entry, Machine
from ...services.text_normalization import (
    optional_collapsed_whitespace_text as _optional_text,
)
from ..serialization import timestamp as _timestamp

RESPONSIBLE_HALL_NUMBERS = (1, 2, 3, 4)
_NUMERIC_IDENTIFIER_PATTERN = re.compile(r"\d+[,.]0+")


@dataclass(frozen=True)
class MissingProductionStartRow:
    machine_code: str
    hall_number: int
    hall_name: str
    display_order: int
    latest_work_order: str | None
    latest_product: str | None
    latest_cycle_time: str | None
    latest_submitted_at: datetime | None
    entry_count: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "machine_code": self.machine_code,
            "hall_number": self.hall_number,
            "hall_name": self.hall_name,
            "latest_work_order": self.latest_work_order,
            "latest_product": self.latest_product,
            "latest_cycle_time": self.latest_cycle_time,
            "latest_submitted_at": _timestamp(self.latest_submitted_at),
            "entry_count": self.entry_count,
        }


@dataclass(frozen=True)
class MissingProductionStartSummary:
    process_date: str
    hall_numbers: tuple[int, ...]
    working_machine_count: int
    active_ifs_machine_count: int
    missing_count: int
    machines: list[MissingProductionStartRow]
    active_ifs_combination_count: int
    process_combination_count: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "process_date": self.process_date,
            "hall_numbers": list(self.hall_numbers),
            "working_machine_count": self.working_machine_count,
            "active_ifs_machine_count": self.active_ifs_machine_count,
            "active_ifs_combination_count": self.active_ifs_combination_count,
            "process_combination_count": self.process_combination_count,
            "missing_count": self.missing_count,
            "machines": [row.as_dict() for row in self.machines],
        }


@dataclass(frozen=True)
class MachineProductionStatus:
    machine_code: str
    hall_number: int
    hall_name: str
    display_order: int
    is_active: bool
    status_text: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "machine_code": self.machine_code,
            "hall_number": self.hall_number,
            "hall_name": self.hall_name,
            "is_active": self.is_active,
            "status": self.status_text,
        }


@dataclass(frozen=True)
class HallProductionStatus:
    hall_number: int
    hall_name: str
    machines: list[MachineProductionStatus]

    def as_dict(self) -> dict[str, Any]:
        return {
            "hall_number": self.hall_number,
            "hall_name": self.hall_name,
            "machines": [machine.as_dict() for machine in self.machines],
        }


@dataclass(frozen=True)
class WhatsappStatusMessage:
    hall_numbers: tuple[int, ...]
    active_ifs_machine_count: int
    machine_count: int
    halls: list[HallProductionStatus]
    message: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "hall_numbers": list(self.hall_numbers),
            "active_ifs_machine_count": self.active_ifs_machine_count,
            "machine_count": self.machine_count,
            "halls": [hall.as_dict() for hall in self.halls],
            "message": self.message,
        }


def missing_production_starts_from_operations(
    settings: Settings,
    process_date: str,
    operations: Sequence[Mapping[str, Any]],
    *,
    hall_numbers: tuple[int, ...] = RESPONSIBLE_HALL_NUMBERS,
) -> MissingProductionStartSummary:
    normalized_date = normalize_process_date(process_date) or process_date
    active_machine_order_rows = _active_machine_order_rows(
        settings,
        operations,
        hall_numbers=hall_numbers,
    )
    active_machine_codes = _machine_codes_from_rows(active_machine_order_rows)
    process_combinations = _working_machines_by_cycle_time(
        settings,
        normalized_date,
        hall_numbers=hall_numbers,
    )
    process_combination_keys = _machine_order_keys_from_rows(process_combinations)
    missing_machines = [
        row
        for row in active_machine_order_rows
        if _machine_order_key(row.machine_code, row.latest_work_order)
        not in process_combination_keys
    ]

    return MissingProductionStartSummary(
        process_date=normalized_date,
        hall_numbers=hall_numbers,
        working_machine_count=len(process_combinations),
        active_ifs_machine_count=len(active_machine_codes),
        active_ifs_combination_count=len(active_machine_order_rows),
        process_combination_count=len(process_combinations),
        missing_count=len(missing_machines),
        machines=missing_machines,
    )


def whatsapp_status_message_from_operations(
    settings: Settings,
    operations: Sequence[Mapping[str, Any]],
    *,
    hall_numbers: tuple[int, ...] = RESPONSIBLE_HALL_NUMBERS,
) -> WhatsappStatusMessage:
    active_machine_codes = _active_machine_codes(operations)
    machines = _responsible_machine_statuses(
        settings,
        active_machine_codes,
        hall_numbers=hall_numbers,
    )
    halls = _group_machine_statuses_by_hall(machines)
    return WhatsappStatusMessage(
        hall_numbers=hall_numbers,
        active_ifs_machine_count=len(active_machine_codes),
        machine_count=len(machines),
        halls=halls,
        message=_whatsapp_message_text(halls),
    )


def _active_machine_codes(operations: Sequence[Mapping[str, Any]]) -> set[str]:
    return {
        machine_code
        for operation in operations
        if (
            machine_code := normalize_machine_code(operation.get("PreferredResourceId"))
        )
    }


def _active_machine_order_rows(
    settings: Settings,
    operations: Sequence[Mapping[str, Any]],
    *,
    hall_numbers: tuple[int, ...],
) -> list[MissingProductionStartRow]:
    with create_session(settings) as session:
        machines = session.scalars(
            select(Machine)
            .where(Machine.hall_number.in_(hall_numbers))
            .order_by(
                Machine.hall_number.asc(),
                Machine.display_order.asc(),
                Machine.machine_code.asc(),
            )
        ).all()

    machines_by_code = {
        normalized_code: machine
        for machine in machines
        if (normalized_code := normalize_machine_code(machine.machine_code)) is not None
    }
    rows: list[MissingProductionStartRow] = []
    seen_keys: set[tuple[str, str]] = set()
    for operation in operations:
        machine_code = normalize_machine_code(operation.get("PreferredResourceId"))
        order_no = _normalize_order_no(operation.get("OrderNo"))
        if machine_code is None or order_no is None:
            continue

        machine = machines_by_code.get(machine_code)
        if machine is None:
            continue

        key = (machine_code, order_no)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        rows.append(
            MissingProductionStartRow(
                machine_code=machine.machine_code,
                hall_number=machine.hall_number,
                hall_name=machine.hall_name,
                display_order=machine.display_order,
                latest_work_order=order_no,
                latest_product=_operation_product_text(operation),
                latest_cycle_time=None,
                latest_submitted_at=None,
                entry_count=0,
            )
        )

    return sorted(
        rows,
        key=lambda row: (
            row.hall_number,
            row.display_order,
            row.machine_code,
            row.latest_work_order or "",
        ),
    )


def _machine_order_key(
    machine_code: Any,
    order_no: Any,
) -> tuple[str | None, str | None]:
    return (normalize_machine_code(machine_code), _normalize_order_no(order_no))


def _machine_order_keys_from_rows(
    rows: Sequence[MissingProductionStartRow],
) -> set[tuple[str | None, str | None]]:
    return {
        _machine_order_key(row.machine_code, row.latest_work_order)
        for row in rows
    }


def _machine_codes_from_rows(rows: Sequence[MissingProductionStartRow]) -> set[str]:
    return {
        machine_code
        for row in rows
        if (machine_code := normalize_machine_code(row.machine_code)) is not None
    }


def _operation_product_text(operation: Mapping[str, Any]) -> str | None:
    return (
        _optional_text(operation.get("PartNoDesc"))
        or _optional_text(operation.get("part_description"))
        or _optional_text(operation.get("PartNo"))
    )


def _responsible_machine_statuses(
    settings: Settings,
    active_machine_codes: set[str],
    *,
    hall_numbers: tuple[int, ...],
) -> list[MachineProductionStatus]:
    with create_session(settings) as session:
        machines = session.scalars(
            select(Machine)
            .where(Machine.hall_number.in_(hall_numbers))
            .order_by(
                Machine.hall_number.asc(),
                Machine.display_order.asc(),
                Machine.machine_code.asc(),
            )
        ).all()

    statuses: list[MachineProductionStatus] = []
    for machine in machines:
        machine_code = normalize_machine_code(machine.machine_code) or machine.machine_code
        is_active = machine_code in active_machine_codes
        statuses.append(
            MachineProductionStatus(
                machine_code=machine.machine_code,
                hall_number=machine.hall_number,
                hall_name=machine.hall_name,
                display_order=machine.display_order,
                is_active=is_active,
                status_text="Üretim" if is_active else "Kapalı",
            )
        )
    return statuses


def _group_machine_statuses_by_hall(
    machines: Sequence[MachineProductionStatus],
) -> list[HallProductionStatus]:
    halls: list[HallProductionStatus] = []
    for machine in machines:
        if not halls or halls[-1].hall_number != machine.hall_number:
            halls.append(
                HallProductionStatus(
                    hall_number=machine.hall_number,
                    hall_name=machine.hall_name,
                    machines=[],
                )
            )
        halls[-1].machines.append(machine)
    return halls


def _whatsapp_message_text(halls: Sequence[HallProductionStatus]) -> str:
    sections: list[str] = []
    for hall in halls:
        lines = [f"Salon {hall.hall_number}"]
        lines.extend(
            f"{machine.machine_code} {machine.status_text}"
            for machine in hall.machines
        )
        lines.extend(["", "IFS kontrolleri yapılmıştır."])
        sections.append("\n".join(lines))
    return "\n\n".join(sections)


def _working_machines_by_cycle_time(
    settings: Settings,
    process_date: str,
    *,
    hall_numbers: tuple[int, ...],
) -> list[MissingProductionStartRow]:
    latest_by_combination: dict[tuple[str, str | None], MissingProductionStartRow] = {}
    latest_sort_keys: dict[tuple[str, str | None], tuple[datetime, int]] = {}
    entry_counts: dict[tuple[str, str | None], int] = {}

    with create_session(settings) as session:
        session_rows = session.execute(
            select(Entry, Machine)
            .join(Machine, Entry.machine_code == Machine.machine_code)
            .where(Entry.process_date == process_date)
            .where(Machine.hall_number.in_(hall_numbers))
            .order_by(
                Machine.hall_number.asc(),
                Machine.display_order.asc(),
                func.coalesce(Entry.submitted_at, Entry.created_at).asc(),
                Entry.id.asc(),
            )
        ).all()

    for entry, machine in session_rows:
        cycle_time = _valid_cycle_time_text(entry.col_l)
        if cycle_time is None:
            continue

        machine_code = normalize_machine_code(entry.machine_code or entry.col_f)
        if machine_code is None:
            continue

        work_order = _normalize_order_no(entry.col_h)
        if work_order is None:
            continue
        key = (machine_code, work_order)
        entry_counts[key] = entry_counts.get(key, 0) + 1
        submitted_at = entry.submitted_at or entry.created_at
        sort_key = (submitted_at or datetime.min, int(entry.id or 0))

        existing_key = latest_sort_keys.get(key)
        if existing_key is not None and sort_key <= existing_key:
            continue

        latest_sort_keys[key] = sort_key
        latest_by_combination[key] = MissingProductionStartRow(
            machine_code=machine.machine_code,
            hall_number=machine.hall_number,
            hall_name=machine.hall_name,
            display_order=machine.display_order,
            latest_work_order=work_order,
            latest_product=_optional_text(entry.col_g),
            latest_cycle_time=cycle_time,
            latest_submitted_at=submitted_at,
            entry_count=entry_counts[key],
    )

    report_rows: list[MissingProductionStartRow] = []
    for combination_key, row in latest_by_combination.items():
        report_rows.append(
            MissingProductionStartRow(
                machine_code=row.machine_code,
                hall_number=row.hall_number,
                hall_name=row.hall_name,
                display_order=row.display_order,
                latest_work_order=row.latest_work_order,
                latest_product=row.latest_product,
                latest_cycle_time=row.latest_cycle_time,
                latest_submitted_at=row.latest_submitted_at,
                entry_count=entry_counts[combination_key],
            )
        )
    return sorted(
        report_rows,
        key=lambda row: (
            row.hall_number,
            row.display_order,
            row.machine_code,
            row.latest_work_order or "",
        ),
    )


def _normalize_order_no(value: Any) -> str | None:
    text = _optional_text(value)
    if text is None:
        return None
    if _NUMERIC_IDENTIFIER_PATTERN.fullmatch(text):
        return text.split(".", 1)[0].split(",", 1)[0]
    return text


def _valid_cycle_time_text(value: Any) -> str | None:
    text = _optional_text(value)
    if text is None:
        return None
    try:
        number = Decimal(text.replace(",", "."))
    except InvalidOperation:
        return None
    if not number.is_finite() or number <= 0:
        return None
    return text
