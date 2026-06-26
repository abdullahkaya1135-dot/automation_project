from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ...services.text_normalization import optional_collapsed_whitespace_text
from ..process_entries.models import Entry
from ..serialization import timestamp as _timestamp
from .models import MachineBreakdown


def serialize_breakdown(breakdown: MachineBreakdown) -> dict[str, Any]:
    return {
        "id": breakdown.id,
        "client_request_id": breakdown.client_request_id,
        "client_recorded_at": _timestamp(breakdown.client_recorded_at),
        "record_date": breakdown.record_date,
        "machine_id": breakdown.machine_id,
        "machine_code": breakdown.machine.machine_code if breakdown.machine else None,
        "entry_id": breakdown.entry_id,
        "amount_control_shift_id": breakdown.amount_control_shift_id,
        "job_order": breakdown.job_order,
        "shift": breakdown.shift,
        "produced_product": breakdown.produced_product,
        "reason": breakdown.stop_reason,
        "stop_reason": breakdown.stop_reason,
        "duration_minutes": breakdown.duration_minutes,
        "stopped_at": _timestamp(breakdown.stopped_at),
        "resumed_at": _timestamp(breakdown.resumed_at),
        "created_at": _timestamp(breakdown.created_at),
        "updated_at": _timestamp(breakdown.updated_at),
    }


def breakdown_context_options(
    session: Session,
    record_date: str,
) -> list[dict[str, Any]]:
    entries = session.scalars(
        select(Entry).where(Entry.process_date == record_date)
    ).all()
    representatives: dict[
        tuple[str, str, str | None],
        tuple[tuple[Any, int], Entry],
    ] = {}

    for entry in entries:
        machine_code = optional_collapsed_whitespace_text(
            entry.machine_code
        ) or optional_collapsed_whitespace_text(entry.col_f)
        job_order = optional_collapsed_whitespace_text(entry.col_h)
        if machine_code is None or job_order is None:
            continue

        produced_product = optional_collapsed_whitespace_text(entry.col_g)
        key = (machine_code, job_order, produced_product)
        sort_key = (
            entry.submitted_at or entry.created_at or datetime.min,
            int(entry.id or 0),
        )
        existing = representatives.get(key)
        if existing is None or sort_key > existing[0]:
            representatives[key] = (sort_key, entry)

    options = [
        {
            "machine_code": machine_code,
            "job_order": job_order,
            "produced_product": produced_product,
            "entry_id": entry.id,
            "submitted_at": _timestamp(entry.submitted_at),
        }
        for (
            machine_code,
            job_order,
            produced_product,
        ), (_sort_key, entry) in representatives.items()
    ]
    return sorted(options, key=_breakdown_context_sort_key)


def _breakdown_context_sort_key(option: dict[str, Any]) -> tuple[Any, ...]:
    return (
        _machine_code_sort_key(option["machine_code"]),
        _text_sort_key(option["job_order"]),
        _text_sort_key(option["produced_product"]),
        int(option["entry_id"] or 0),
    )


def _machine_code_sort_key(value: str) -> tuple[int, int | str, str]:
    text = value.strip()
    if text.isdigit():
        return (0, int(text), text)
    return (1, text.casefold(), text)


def _text_sort_key(value: str | None) -> tuple[int, str, str]:
    if value is None:
        return (0, "", "")
    return (1, value.casefold(), value)
