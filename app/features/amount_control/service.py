from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..serialization import timestamp as _timestamp
from .models import AmountControlShift, Machine, MachineBreakdown


def machine_options(session: Session) -> list[dict[str, Any]]:
    machines = session.scalars(
        select(Machine).order_by(
            Machine.hall_number,
            Machine.display_order,
            Machine.machine_code,
        )
    ).all()
    return [
        {
            "id": machine.id,
            "machine_code": machine.machine_code,
            "hall_number": machine.hall_number,
            "hall_name": machine.hall_name,
            "display_order": machine.display_order,
        }
        for machine in machines
    ]


def serialize_machine_breakdown(
    breakdown: MachineBreakdown,
) -> dict[str, Any]:
    return {
        "id": breakdown.id,
        "machine_id": breakdown.machine_id,
        "machine_code": breakdown.machine.machine_code if breakdown.machine else None,
        "entry_id": breakdown.entry_id,
        "amount_control_shift_id": breakdown.amount_control_shift_id,
        "produced_product": breakdown.produced_product,
        "stop_reason": breakdown.stop_reason,
        "duration_minutes": breakdown.duration_minutes,
        "stopped_at": _timestamp(breakdown.stopped_at),
        "resumed_at": _timestamp(breakdown.resumed_at),
        "created_at": _timestamp(breakdown.created_at),
        "updated_at": _timestamp(breakdown.updated_at),
    }


def serialize_amount_control_shift(
    amount_shift: AmountControlShift,
) -> dict[str, Any]:
    return {
        "id": amount_shift.id,
        "client_request_id": amount_shift.client_request_id,
        "client_recorded_at": _timestamp(amount_shift.client_recorded_at),
        "record_date": amount_shift.record_date,
        "machine_id": amount_shift.machine_id,
        "machine_code": amount_shift.machine.machine_code,
        "job_order": amount_shift.job_order,
        "shift": amount_shift.shift,
        "worker_names": amount_shift.worker_names,
        "produced_quantity": amount_shift.produced_quantity,
        "breakdowns": [
            serialize_machine_breakdown(breakdown)
            for breakdown in amount_shift.machine_breakdowns
        ],
        "created_at": _timestamp(amount_shift.created_at),
        "updated_at": _timestamp(amount_shift.updated_at),
    }
