from datetime import date as Date
from datetime import datetime
from pathlib import Path

from ...config import Settings
from ..ifs.operations import fetch_pet_ongoing_operations
from .cycle_builder import build_cycle_report_rows as build_cycle_report_rows
from .cycle_sources import (
    read_cycle_table,
    read_process_rows,
    read_shop_order_options,
)
from .cycle_types import (
    COMPLETE_STATUSES,
)
from .cycle_types import (
    CycleReportError as CycleReportError,
)
from .cycle_types import (
    CycleReportResult as CycleReportResult,
)
from .cycle_types import (
    CycleReportRow as CycleReportRow,
)
from .cycle_types import (
    CycleTableEntry as CycleTableEntry,
)
from .cycle_types import (
    NoTodayRowsError as NoTodayRowsError,
)
from .cycle_types import (
    ProcessCycleRow as ProcessCycleRow,
)
from .cycle_values import normalize_machine_group as normalize_machine_group
from .cycle_values import parse_part_description as parse_part_description
from .cycle_writer import write_cycle_report


def create_cycle_report(settings: Settings, report_date: Date) -> CycleReportResult:
    process_rows = read_process_rows(settings, report_date)
    if not process_rows:
        raise NoTodayRowsError(
            f"{report_date.isoformat()} tarihi için PROSES 2026 kaydı bulunamadı."
        )

    shop_orders = read_shop_order_options(
        settings,
        fetch_operations=fetch_pet_ongoing_operations,
    )
    cycle_entries = read_cycle_table(settings)
    report_rows = build_cycle_report_rows(process_rows, shop_orders, cycle_entries)

    output_dir = Path(settings.report_output_dir).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = output_dir / f"cevrim_kontrol_{timestamp}.xlsx"
    write_cycle_report(output_path, report_rows)

    warning_count = sum(
        1 for row in report_rows if row.control_status not in COMPLETE_STATUSES
    )
    matched_count = len(report_rows) - warning_count
    return CycleReportResult(
        output_path=output_path,
        row_count=len(report_rows),
        matched_count=matched_count,
        warning_count=warning_count,
        report_date=report_date,
    )


__all__ = [
    "CycleReportError",
    "CycleReportResult",
    "CycleReportRow",
    "CycleTableEntry",
    "NoTodayRowsError",
    "ProcessCycleRow",
    "build_cycle_report_rows",
    "create_cycle_report",
    "fetch_pet_ongoing_operations",
    "normalize_machine_group",
    "parse_part_description",
]
