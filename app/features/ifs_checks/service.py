from __future__ import annotations

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

RESPONSIBLE_HALL_NUMBERS = (3, 4)


@dataclass(frozen=True)
class MissingProductionStartRow:
    machine_code: str
    hall_number: int
    hall_name: str
    display_order: int
    latest_work_order: str | None
    latest_product: str | None
    latest_cycle_time: str
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

    def as_dict(self) -> dict[str, Any]:
        return {
            "process_date": self.process_date,
            "hall_numbers": list(self.hall_numbers),
            "working_machine_count": self.working_machine_count,
            "active_ifs_machine_count": self.active_ifs_machine_count,
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
    active_machine_codes = _active_machine_codes(operations)
    working_machines = _working_machines_by_cycle_time(
        settings,
        normalized_date,
        hall_numbers=hall_numbers,
    )
    missing_machines = [
        machine
        for machine in working_machines
        if normalize_machine_code(machine.machine_code) not in active_machine_codes
    ]

    return MissingProductionStartSummary(
        process_date=normalized_date,
        hall_numbers=hall_numbers,
        working_machine_count=len(working_machines),
        active_ifs_machine_count=len(active_machine_codes),
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
    latest_by_machine: dict[str, MissingProductionStartRow] = {}
    latest_sort_keys: dict[str, tuple[datetime, int]] = {}
    entry_counts: dict[str, int] = {}

    with create_session(settings) as session:
        rows = session.execute(
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

    for entry, machine in rows:
        cycle_time = _valid_cycle_time_text(entry.col_l)
        if cycle_time is None:
            continue

        machine_code = normalize_machine_code(entry.machine_code or entry.col_f)
        if machine_code is None:
            continue

        entry_counts[machine_code] = entry_counts.get(machine_code, 0) + 1
        submitted_at = entry.submitted_at or entry.created_at
        sort_key = (submitted_at or datetime.min, int(entry.id or 0))

        existing_key = latest_sort_keys.get(machine_code)
        if existing_key is not None and sort_key <= existing_key:
            continue

        latest_sort_keys[machine_code] = sort_key
        latest_by_machine[machine_code] = MissingProductionStartRow(
            machine_code=machine.machine_code,
            hall_number=machine.hall_number,
            hall_name=machine.hall_name,
            display_order=machine.display_order,
            latest_work_order=_optional_text(entry.col_h),
            latest_product=_optional_text(entry.col_g),
            latest_cycle_time=cycle_time,
            latest_submitted_at=submitted_at,
            entry_count=entry_counts[machine_code],
        )

    rows: list[MissingProductionStartRow] = []
    for machine_code, row in latest_by_machine.items():
        rows.append(
            MissingProductionStartRow(
                machine_code=row.machine_code,
                hall_number=row.hall_number,
                hall_name=row.hall_name,
                display_order=row.display_order,
                latest_work_order=row.latest_work_order,
                latest_product=row.latest_product,
                latest_cycle_time=row.latest_cycle_time,
                latest_submitted_at=row.latest_submitted_at,
                entry_count=entry_counts[machine_code],
            )
        )
    return sorted(
        rows,
        key=lambda row: (row.hall_number, row.display_order, row.machine_code),
    )


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


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).strip().split())
    return text or None


def _timestamp(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat(timespec="seconds") + "Z"
