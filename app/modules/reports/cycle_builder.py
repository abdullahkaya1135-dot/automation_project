from collections import defaultdict
from decimal import Decimal

from ..shop_orders.source import ShopOrderOption
from .cycle_types import (
    CYCLE_TOLERANCE_MULTIPLIER,
    STATUS_CHECK,
    STATUS_OK,
    CycleReportRow,
    CycleTableEntry,
    ProcessCycleRow,
)
from .cycle_values import (
    identifier,
    normalize_machine_group,
    parse_part_description,
)


def indexed_shop_orders(
    options: list[ShopOrderOption],
) -> dict[str, list[ShopOrderOption]]:
    by_order: dict[str, list[ShopOrderOption]] = defaultdict(list)
    for option in options:
        order_no = identifier(option.order_no)
        if order_no:
            by_order[order_no].append(option)
    return by_order


def matching_shop_order(
    row: ProcessCycleRow,
    by_order: dict[str, list[ShopOrderOption]],
) -> tuple[ShopOrderOption | None, str | None]:
    candidates = by_order.get(row.work_order, [])
    if not candidates:
        return None, "HTML eşleşmesi bulunamadı"
    if len(candidates) == 1:
        return candidates[0], None

    machine_matches = [
        candidate
        for candidate in candidates
        if identifier(candidate.resource_id) == row.machine_no
    ]
    if len(machine_matches) == 1:
        return machine_matches[0], None
    if machine_matches:
        return None, "HTML eşleşmesi belirsiz"
    return None, "HTML makine eşleşmesi bulunamadı"


def lookup_optimum_cycle(
    cycle_entries: dict[tuple[str, Decimal, Decimal], list[CycleTableEntry]],
    *,
    machine_group: str,
    machine_no: str,
    neck_diameter: Decimal,
    gram: Decimal,
) -> tuple[Decimal | None, str | None]:
    key = (normalize_machine_group(machine_group), neck_diameter, gram)
    entries = cycle_entries.get(key, [])
    if not entries:
        return None, "Optimum çevrim bulunamadı"

    cycles = {entry.estimated_cycle_time for entry in entries}
    if len(cycles) == 1:
        return next(iter(cycles)), None

    machine_matches = [
        entry
        for entry in entries
        if identifier(entry.machine_no) == identifier(machine_no)
    ]
    machine_cycles = {entry.estimated_cycle_time for entry in machine_matches}
    if len(machine_cycles) == 1:
        return next(iter(machine_cycles)), None
    return None, "Optimum çevrim belirsiz"


def build_cycle_report_rows(
    process_rows: list[ProcessCycleRow],
    shop_orders: list[ShopOrderOption],
    cycle_entries: dict[tuple[str, Decimal, Decimal], list[CycleTableEntry]],
) -> list[CycleReportRow]:
    by_order = indexed_shop_orders(shop_orders)
    report_rows: list[CycleReportRow] = []

    for process_row in process_rows:
        shop_order, status = matching_shop_order(process_row, by_order)
        machine_group = shop_order.work_center_no if shop_order else None
        neck: Decimal | None = None
        gram: Decimal | None = None
        optimum_cycle: Decimal | None = None

        if shop_order is not None:
            neck, gram = parse_part_description(shop_order.part_description)
            if neck is None or gram is None:
                status = "Ağız/Gramaj bulunamadı"

        if status is None and shop_order is not None and neck is not None and gram is not None:
            optimum_cycle, status = lookup_optimum_cycle(
                cycle_entries,
                machine_group=shop_order.work_center_no,
                machine_no=process_row.machine_no,
                neck_diameter=neck,
                gram=gram,
            )

        if status is None:
            if process_row.actual_cycle_time is None:
                status = "Gerçekleşen çevrim eksik"
            elif optimum_cycle is None:
                status = "Optimum çevrim bulunamadı"
            elif process_row.actual_cycle_time <= optimum_cycle * CYCLE_TOLERANCE_MULTIPLIER:
                status = STATUS_OK
            else:
                status = STATUS_CHECK

        report_rows.append(
            CycleReportRow(
                machine_group=machine_group,
                machine_no=process_row.machine_no,
                neck_diameter=neck,
                gram=gram,
                total_cavity_count=process_row.total_cavity_count,
                active_cavity_count=process_row.active_cavity_count,
                actual_cycle_time=process_row.actual_cycle_time,
                optimum_cycle_time=optimum_cycle,
                control_status=status,
            )
        )
    return report_rows
