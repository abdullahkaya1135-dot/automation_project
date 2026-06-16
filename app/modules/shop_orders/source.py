import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ShopOrderOption:
    order_no: str
    resource_id: str
    release_no: str = "*"
    sequence_no: str = "*"
    operation_no: int | None = None
    part_no: str = ""
    work_center_no: str = ""
    part_description: str = ""


def _clean_text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _clean_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _natural_key(value: str) -> tuple[tuple[int, int | str], ...]:
    parts: list[tuple[int, int | str]] = []
    for part in re.split(r"(\d+)", value):
        if not part:
            continue
        if part.isdigit():
            parts.append((0, int(part)))
        else:
            parts.append((1, part.casefold()))
    return tuple(parts)


def shop_order_options_from_ifs_operations(
    rows: list[dict[str, Any]],
) -> list[ShopOrderOption]:
    seen: set[tuple[str, str, str, str, int | None]] = set()
    options: list[ShopOrderOption] = []

    for row in rows:
        order_no = _clean_text(row.get("OrderNo"))
        resource_id = _clean_text(row.get("PreferredResourceId"))
        if not order_no or not resource_id:
            continue

        release_no = _clean_text(row.get("ReleaseNo")) or "*"
        sequence_no = _clean_text(row.get("SequenceNo")) or "*"
        operation_no = _clean_int(row.get("OperationNo"))
        key = (order_no, resource_id, release_no, sequence_no, operation_no)
        if key in seen:
            continue
        seen.add(key)
        options.append(
            ShopOrderOption(
                order_no=order_no,
                resource_id=resource_id,
                release_no=release_no,
                sequence_no=sequence_no,
                operation_no=operation_no,
                part_no=_clean_text(row.get("PartNo")),
                work_center_no=_clean_text(row.get("WorkCenterNo")),
                part_description=_clean_text(row.get("PartNoDesc")),
            )
        )

    options.sort(
        key=lambda option: (
            _natural_key(option.resource_id),
            _natural_key(option.order_no),
            _natural_key(option.release_no),
            _natural_key(option.sequence_no),
            option.operation_no if option.operation_no is not None else -1,
        )
    )
    return options


def ifs_shop_order_source_payload(rows: list[dict[str, Any]]) -> dict[str, Any]:
    options = shop_order_options_from_ifs_operations(rows)
    order_nos = sorted({option.order_no for option in options}, key=_natural_key)
    resource_ids = sorted({option.resource_id for option in options}, key=_natural_key)
    return {
        "available": bool(options),
        "source": "ifs-token",
        "last_error": None
        if options
        else "IFS operasyonlarinda OrderNo ve PreferredResourceId eslesmesi bulunamadi.",
        "operation_count": len(options),
        "order_count": len(order_nos),
        "resource_count": len(resource_ids),
        "options": [
            {
                "order_no": option.order_no,
                "resource_id": option.resource_id,
                "release_no": option.release_no,
                "sequence_no": option.sequence_no,
                "operation_no": option.operation_no,
                "part_no": option.part_no,
                "part_description": option.part_description,
            }
            for option in options
        ],
    }
