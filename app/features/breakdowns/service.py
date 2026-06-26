from typing import Any

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
