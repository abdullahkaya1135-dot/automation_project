from __future__ import annotations

import asyncio
import json
import re
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from datetime import date as Date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ...core.config import Settings
from ...core.database import create_session
from ...domain import shifts
from ...features.cycle_reports.service import (
    _lookup_optimum_cycle,
    _read_cycle_table,
    normalize_machine_group,
    parse_part_description,
)
from ...features.process_entries.normalization import (
    normalize_machine_code,
    normalize_process_date,
)
from ...integrations.ifs.client import fetch_shop_order_operation_actual_rows
from ..serialization import timestamp as _timestamp
from .models import (
    AmountControlShift,
    Entry,
    Machine,
    MachineBreakdown,
    ProductionLossIfsActual,
    ProductionLossReport,
    ProductionLossReportRow,
)

SHIFT_FIELD_BY_LABEL = {
    "24.00-08.00": "shift_2400_0800_quantity",
    "08.00-16.00": "shift_0800_1600_quantity",
    "16.00-24.00": "shift_1600_2400_quantity",
}
REPORT_HEADERS = (
    "Date",
    "Machine Name",
    "Machine Code",
    "Job Order",
    "Product",
    "Gr",
    "24.00-08.00",
    "08.00-16.00",
    "16.00-24.00",
    "Daily Total",
    "Active Cavities",
    "Cycle Time (s)",
    "Net Machine Time (min)",
    "Gross Elapsed (min)",
    "Optimum Net Qty",
    "Production Loss Net",
    "Optimum Gross Qty",
    "Production Loss Gross",
    "Break Loss Qty",
    "Local Breakdown (min)",
    "Warnings",
)
DATETIME_FIELDS_START = (
    "ActualStartDate",
    "ActualStartTime",
    "ActualStart",
    "OpStartDate",
    "OpStartTime",
    "StartDate",
    "StartTime",
    "StartedAt",
    "ProductionStartTime",
)
DATETIME_FIELDS_FINISH = (
    "ActualFinishDate",
    "ActualFinishTime",
    "ActualFinish",
    "OpFinishDate",
    "OpFinishTime",
    "FinishDate",
    "FinishTime",
    "StopDate",
    "StopTime",
    "StoppedAt",
    "ProductionFinishTime",
)
NET_MACHINE_DURATION_FIELDS = (
    "NetMachineMinutes",
    "MachineMinutes",
    "RunTimeMinutes",
    "ProductionMinutes",
    "NetMachineHours",
    "MachineHours",
    "RunTimeHours",
    "ProductionHours",
    "NetMachineSeconds",
    "MachineSeconds",
    "RunTimeSeconds",
    "ProductionSeconds",
)
COMPLETED_QTY_FIELDS = (
    "CompletedQty",
    "QtyComplete",
    "QtyCompleted",
    "ReportedQty",
    "QtyReported",
)
SCRAP_QTY_FIELDS = ("ScrapQty", "QtyScrapped", "ScrappedQty")
GRAM_PATTERN = re.compile(r"(\d+(?:[,.]\d+)?)\s*GR\b", re.IGNORECASE)


class ProductionLossReportError(RuntimeError):
    """Raised when a production-loss report cannot be created."""


@dataclass
class ShiftAggregate:
    record_date: str
    machine_id: int
    machine_code: str
    job_order: str
    shift_quantities: dict[str, int] = field(
        default_factory=lambda: {shift: 0 for shift in shifts.SHIFT_OPTIONS}
    )
    local_breakdown_minutes: int = 0
    product_hint: str | None = None

    @property
    def daily_total_quantity(self) -> int:
        return sum(self.shift_quantities.values())


@dataclass(frozen=True)
class ProcessMeta:
    product: str | None
    active_cavities: Decimal | None
    submitted_at: datetime | None
    entry_id: int


@dataclass
class IfsActual:
    job_order: str
    machine_code: str | None = None
    release_no: str | None = None
    sequence_no: str | None = None
    operation_no: int | None = None
    work_center_no: str | None = None
    part_no: str | None = None
    part_description: str | None = None
    actual_start_at: datetime | None = None
    actual_finish_at: datetime | None = None
    net_machine_minutes: Decimal | None = None
    completed_quantity: Decimal | None = None
    scrap_quantity: Decimal | None = None
    raw_rows: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class ProductionLossReportResult:
    report_id: int
    date_from: str
    date_to: str
    output_path: Path
    row_count: int
    warning_count: int
    generated_at: datetime
    rows: list[dict[str, Any]]
    source_summary: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.report_id,
            "date_from": self.date_from,
            "date_to": self.date_to,
            "output_path": str(self.output_path),
            "row_count": self.row_count,
            "warning_count": self.warning_count,
            "generated_at": _timestamp(self.generated_at),
            "source_summary": self.source_summary,
            "rows": self.rows,
        }


def create_production_loss_report(
    settings: Settings,
    *,
    date_from: str,
    date_to: str,
    refresh_ifs: bool = True,
) -> ProductionLossReportResult:
    start_date, end_date = _date_range(date_from, date_to)
    aggregates = _read_shift_aggregates(settings, start_date, end_date)
    if not aggregates:
        raise ProductionLossReportError(
            "Secilen tarih araliginda miktar kontrol kaydi bulunamadi."
        )

    order_numbers = sorted({aggregate.job_order for aggregate in aggregates})
    process_meta = _read_process_metadata(settings, start_date, end_date)
    ifs_actuals, ifs_summary = _load_ifs_actuals(
        settings,
        order_numbers,
        refresh_ifs=refresh_ifs,
    )
    cycle_entries = _read_cycle_table(settings)
    row_models = _build_report_rows(
        aggregates,
        process_meta,
        ifs_actuals,
        cycle_entries,
    )

    generated_at = datetime.now(UTC).replace(tzinfo=None)
    warning_count = sum(1 for row in row_models if _clean_text(row.warnings))
    source_summary = {
        **ifs_summary,
        "amount_control_group_count": len(aggregates),
        "process_match_count": sum(
            1
            for aggregate in aggregates
            if (aggregate.record_date, aggregate.machine_code, aggregate.job_order)
            in process_meta
        ),
    }

    session = create_session(settings)
    try:
        report = ProductionLossReport(
            date_from=start_date.isoformat(),
            date_to=end_date.isoformat(),
            generated_at=generated_at,
            row_count=len(row_models),
            warning_count=warning_count,
            source_summary_json=json.dumps(source_summary, ensure_ascii=False),
        )
        session.add(report)
        session.flush()
        for row_model in row_models:
            row_model.report_id = report.id
            report.rows.append(row_model)

        output_path = _report_output_path(settings, report.id, start_date, end_date)
        _write_workbook(output_path, row_models)
        report.output_path = str(output_path)
        session.commit()
        payload_rows = [serialize_production_loss_row(row) for row in row_models]
        return ProductionLossReportResult(
            report_id=report.id,
            date_from=report.date_from,
            date_to=report.date_to,
            output_path=output_path,
            row_count=report.row_count,
            warning_count=report.warning_count,
            generated_at=report.generated_at,
            rows=payload_rows,
            source_summary=source_summary,
        )
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def list_production_loss_reports(
    settings: Settings,
    *,
    limit: int = 20,
) -> list[dict[str, Any]]:
    with create_session(settings) as session:
        reports = session.scalars(
            select(ProductionLossReport)
            .order_by(
                ProductionLossReport.generated_at.desc(),
                ProductionLossReport.id.desc(),
            )
            .limit(limit)
        ).all()
        return [serialize_production_loss_report(report) for report in reports]


def get_production_loss_report(
    settings: Settings,
    report_id: int,
) -> dict[str, Any] | None:
    with create_session(settings) as session:
        report = session.scalars(
            select(ProductionLossReport)
            .options(selectinload(ProductionLossReport.rows))
            .where(ProductionLossReport.id == report_id)
        ).first()
        if report is None:
            return None
        return serialize_production_loss_report(report, include_rows=True)


def serialize_production_loss_report(
    report: ProductionLossReport,
    *,
    include_rows: bool = False,
) -> dict[str, Any]:
    payload = {
        "id": report.id,
        "date_from": report.date_from,
        "date_to": report.date_to,
        "generated_at": _timestamp(report.generated_at),
        "output_path": report.output_path,
        "row_count": report.row_count,
        "warning_count": report.warning_count,
        "source_summary": _json_object(report.source_summary_json),
    }
    if include_rows:
        payload["rows"] = [
            serialize_production_loss_row(row)
            for row in sorted(
                report.rows,
                key=lambda item: (
                    item.record_date,
                    _natural_machine_key(item.machine_code),
                    item.job_order,
                    item.id,
                ),
            )
        ]
    return payload


def serialize_production_loss_row(row: ProductionLossReportRow) -> dict[str, Any]:
    return {
        "id": row.id,
        "record_date": row.record_date,
        "machine_id": row.machine_id,
        "machine_code": row.machine_code,
        "machine_name": row.machine_name,
        "job_order": row.job_order,
        "product_no": row.product_no,
        "product_description": row.product_description,
        "gram": row.gram,
        "active_cavities": row.active_cavities,
        "cycle_time_seconds": row.cycle_time_seconds,
        "shift_2400_0800_quantity": row.shift_2400_0800_quantity,
        "shift_0800_1600_quantity": row.shift_0800_1600_quantity,
        "shift_1600_2400_quantity": row.shift_1600_2400_quantity,
        "daily_total_quantity": row.daily_total_quantity,
        "net_machine_minutes": row.net_machine_minutes,
        "gross_elapsed_minutes": row.gross_elapsed_minutes,
        "gross_start_at": _timestamp(row.gross_start_at),
        "gross_finish_at": _timestamp(row.gross_finish_at),
        "optimum_net_quantity": row.optimum_net_quantity,
        "production_loss_net": row.production_loss_net,
        "optimum_gross_quantity": row.optimum_gross_quantity,
        "production_loss_gross": row.production_loss_gross,
        "break_loss_quantity": row.break_loss_quantity,
        "local_breakdown_minutes": row.local_breakdown_minutes,
        "warnings": row.warnings,
    }


def normalize_ifs_actual_rows(rows: Sequence[Mapping[str, Any]]) -> list[IfsActual]:
    by_key: dict[tuple[str, str | None], IfsActual] = {}
    for row in rows:
        order_no = _first_text(row, ("OrderNo", "order_no", "ShopOrderNo"))
        if not order_no:
            continue
        machine_code = normalize_machine_code(
            _first_text(
                row,
                (
                    "PreferredResourceId",
                    "preferred_resource_id",
                    "ResourceId",
                    "Machine",
                    "machine",
                ),
            )
        )
        key = (order_no, machine_code)
        actual = by_key.setdefault(
            key,
            IfsActual(job_order=order_no, machine_code=machine_code),
        )
        _merge_ifs_actual(actual, row)
    return list(by_key.values())


def _build_report_rows(
    aggregates: list[ShiftAggregate],
    process_meta: dict[tuple[str, str, str], ProcessMeta],
    ifs_actuals: dict[tuple[str, str | None], IfsActual],
    cycle_entries: Any,
) -> list[ProductionLossReportRow]:
    by_order = _ifs_actuals_by_order(ifs_actuals.values())
    report_rows: list[ProductionLossReportRow] = []

    for aggregate in aggregates:
        warnings: list[str] = []
        process = process_meta.get(
            (aggregate.record_date, aggregate.machine_code, aggregate.job_order)
        )
        actual = _matching_ifs_actual(aggregate, ifs_actuals, by_order)
        if actual is None:
            warnings.append("IFS actual timing not found")

        product_description = (
            actual.part_description
            if actual and actual.part_description
            else process.product
            if process and process.product
            else aggregate.product_hint
        )
        gram = _gram_from_product_description(product_description or "")
        neck, parsed_gram = parse_part_description(product_description or "")
        if gram is None and parsed_gram is not None:
            gram = parsed_gram

        machine_name = actual.work_center_no if actual else None
        cycle_time, cycle_warning = _cycle_time_for_row(
            cycle_entries,
            machine_group=machine_name,
            machine_code=aggregate.machine_code,
            neck=neck,
            gram=parsed_gram or gram,
        )
        if cycle_warning:
            warnings.append(cycle_warning)

        active_cavities = process.active_cavities if process else None
        if active_cavities is None:
            warnings.append("Active cavity count not found")

        net_minutes = actual.net_machine_minutes if actual else None
        gross_minutes = (
            _minutes_between(actual.actual_start_at, actual.actual_finish_at)
            if actual
            else None
        )
        if actual is not None and actual.actual_start_at is None:
            warnings.append("IFS actual start not found")
        if actual is not None and actual.actual_finish_at is None:
            warnings.append("IFS actual finish not found")
        if net_minutes is None:
            warnings.append("IFS net machine time not found")

        optimum_net = _optimum_quantity(net_minutes, cycle_time, active_cavities)
        optimum_gross = _optimum_quantity(gross_minutes, cycle_time, active_cavities)
        actual_quantity = Decimal(aggregate.daily_total_quantity)
        loss_net = (
            optimum_net - actual_quantity if optimum_net is not None else None
        )
        loss_gross = (
            optimum_gross - actual_quantity if optimum_gross is not None else None
        )
        break_loss = (
            loss_gross - loss_net
            if loss_gross is not None and loss_net is not None
            else None
        )

        report_rows.append(
            ProductionLossReportRow(
                report_id=0,
                record_date=aggregate.record_date,
                machine_id=aggregate.machine_id,
                machine_code=aggregate.machine_code,
                machine_name=machine_name,
                job_order=aggregate.job_order,
                product_no=actual.part_no if actual else None,
                product_description=product_description,
                gram=_decimal_text(gram),
                active_cavities=_decimal_text(active_cavities),
                cycle_time_seconds=_decimal_text(cycle_time),
                shift_2400_0800_quantity=aggregate.shift_quantities["24.00-08.00"],
                shift_0800_1600_quantity=aggregate.shift_quantities["08.00-16.00"],
                shift_1600_2400_quantity=aggregate.shift_quantities["16.00-24.00"],
                daily_total_quantity=aggregate.daily_total_quantity,
                net_machine_minutes=_decimal_text(net_minutes),
                gross_elapsed_minutes=_decimal_text(gross_minutes),
                gross_start_at=actual.actual_start_at if actual else None,
                gross_finish_at=actual.actual_finish_at if actual else None,
                optimum_net_quantity=_decimal_text(optimum_net),
                production_loss_net=_decimal_text(loss_net),
                optimum_gross_quantity=_decimal_text(optimum_gross),
                production_loss_gross=_decimal_text(loss_gross),
                break_loss_quantity=_decimal_text(break_loss),
                local_breakdown_minutes=aggregate.local_breakdown_minutes,
                warnings="; ".join(dict.fromkeys(warnings)) or None,
            )
        )

    return sorted(
        report_rows,
        key=lambda row: (
            row.record_date,
            _natural_machine_key(row.machine_code),
            row.job_order,
        ),
    )


def _read_shift_aggregates(
    settings: Settings,
    start_date: Date,
    end_date: Date,
) -> list[ShiftAggregate]:
    aggregates: dict[tuple[str, str, str], ShiftAggregate] = {}
    with create_session(settings) as session:
        rows = session.scalars(
            select(AmountControlShift)
            .options(
                selectinload(AmountControlShift.machine),
                selectinload(AmountControlShift.machine_breakdowns).selectinload(
                    MachineBreakdown.machine
                ),
            )
            .join(AmountControlShift.machine)
            .where(AmountControlShift.record_date >= start_date.isoformat())
            .where(AmountControlShift.record_date <= end_date.isoformat())
            .order_by(
                AmountControlShift.record_date.asc(),
                Machine.machine_code.asc(),
                AmountControlShift.job_order.asc(),
                AmountControlShift.shift.asc(),
            )
        ).all()

    for amount_shift in rows:
        machine_code = normalize_machine_code(amount_shift.machine.machine_code)
        if machine_code is None:
            continue
        job_order = _identifier(amount_shift.job_order)
        if not job_order:
            continue
        key = (amount_shift.record_date, machine_code, job_order)
        aggregate = aggregates.setdefault(
            key,
            ShiftAggregate(
                record_date=amount_shift.record_date,
                machine_id=amount_shift.machine_id,
                machine_code=machine_code,
                job_order=job_order,
            ),
        )
        if amount_shift.shift in aggregate.shift_quantities:
            aggregate.shift_quantities[amount_shift.shift] += amount_shift.produced_quantity
        aggregate.local_breakdown_minutes += sum(
            breakdown.duration_minutes
            for breakdown in amount_shift.machine_breakdowns
            if breakdown.duration_minutes
        )
        if aggregate.product_hint is None:
            aggregate.product_hint = _first_breakdown_product(
                amount_shift.machine_breakdowns
            )

    return sorted(
        aggregates.values(),
        key=lambda item: (
            item.record_date,
            _natural_machine_key(item.machine_code),
            item.job_order,
        ),
    )


def _read_process_metadata(
    settings: Settings,
    start_date: Date,
    end_date: Date,
) -> dict[tuple[str, str, str], ProcessMeta]:
    metadata: dict[tuple[str, str, str], ProcessMeta] = {}
    sort_keys: dict[tuple[str, str, str], tuple[datetime, int]] = {}
    with create_session(settings) as session:
        entries = session.scalars(
            select(Entry)
            .where(Entry.process_date >= start_date.isoformat())
            .where(Entry.process_date <= end_date.isoformat())
            .order_by(Entry.process_date.asc(), Entry.machine_code.asc(), Entry.id.asc())
        ).all()

    for entry in entries:
        process_date = normalize_process_date(entry.process_date or entry.col_a)
        machine_code = normalize_machine_code(entry.machine_code or entry.col_f)
        job_order = _identifier(entry.col_h)
        if not process_date or not machine_code or not job_order:
            continue
        key = (process_date, machine_code, job_order)
        submitted_at = entry.submitted_at or entry.created_at
        sort_key = (submitted_at or datetime.min, int(entry.id or 0))
        if sort_key <= sort_keys.get(key, (datetime.min, 0)):
            continue
        sort_keys[key] = sort_key
        metadata[key] = ProcessMeta(
            product=_optional_text(entry.col_g),
            active_cavities=_decimal(entry.col_k),
            submitted_at=submitted_at,
            entry_id=entry.id,
        )
    return metadata


def _load_ifs_actuals(
    settings: Settings,
    order_numbers: Sequence[str],
    *,
    refresh_ifs: bool,
) -> tuple[dict[tuple[str, str | None], IfsActual], dict[str, Any]]:
    summary: dict[str, Any] = {
        "ifs_refreshed": False,
        "ifs_error": None,
        "ifs_actual_count": 0,
        "ifs_cached_count": 0,
    }
    if refresh_ifs:
        try:
            rows = asyncio.run(
                fetch_shop_order_operation_actual_rows(settings, order_numbers)
            )
            actuals = normalize_ifs_actual_rows(rows)
            _cache_ifs_actuals(settings, actuals)
            summary["ifs_refreshed"] = True
            summary["ifs_actual_count"] = len(actuals)
        except Exception as exc:
            summary["ifs_error"] = str(exc) or exc.__class__.__name__

    cached_actuals = _read_cached_ifs_actuals(settings, order_numbers)
    summary["ifs_cached_count"] = len(cached_actuals)
    return {
        (actual.job_order, actual.machine_code): actual
        for actual in cached_actuals
    }, summary


def _cache_ifs_actuals(settings: Settings, actuals: Sequence[IfsActual]) -> None:
    if not actuals:
        return
    now = datetime.now(UTC).replace(tzinfo=None)
    session = create_session(settings)
    try:
        for actual in actuals:
            existing = session.scalars(
                select(ProductionLossIfsActual)
                .where(ProductionLossIfsActual.job_order == actual.job_order)
                .where(ProductionLossIfsActual.machine_code == actual.machine_code)
            ).first()
            if existing is None:
                existing = ProductionLossIfsActual(
                    job_order=actual.job_order,
                    machine_code=actual.machine_code,
                )
                session.add(existing)
            existing.release_no = actual.release_no
            existing.sequence_no = actual.sequence_no
            existing.operation_no = actual.operation_no
            existing.work_center_no = actual.work_center_no
            existing.part_no = actual.part_no
            existing.part_description = actual.part_description
            existing.actual_start_at = actual.actual_start_at
            existing.actual_finish_at = actual.actual_finish_at
            existing.net_machine_minutes = _decimal_text(actual.net_machine_minutes)
            existing.completed_quantity = _decimal_text(actual.completed_quantity)
            existing.scrap_quantity = _decimal_text(actual.scrap_quantity)
            existing.source = "ifs-operation-actuals"
            existing.raw_json = json.dumps(actual.raw_rows, ensure_ascii=False, default=str)
            existing.source_updated_at = now
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _read_cached_ifs_actuals(
    settings: Settings,
    order_numbers: Sequence[str],
) -> list[IfsActual]:
    order_set = {str(order_no).strip() for order_no in order_numbers if str(order_no).strip()}
    if not order_set:
        return []
    with create_session(settings) as session:
        cached = session.scalars(
            select(ProductionLossIfsActual)
            .where(ProductionLossIfsActual.job_order.in_(order_set))
            .order_by(
                ProductionLossIfsActual.job_order.asc(),
                ProductionLossIfsActual.machine_code.asc(),
            )
        ).all()
        return [
            IfsActual(
                job_order=row.job_order,
                machine_code=row.machine_code,
                release_no=row.release_no,
                sequence_no=row.sequence_no,
                operation_no=row.operation_no,
                work_center_no=row.work_center_no,
                part_no=row.part_no,
                part_description=row.part_description,
                actual_start_at=row.actual_start_at,
                actual_finish_at=row.actual_finish_at,
                net_machine_minutes=_decimal(row.net_machine_minutes),
                completed_quantity=_decimal(row.completed_quantity),
                scrap_quantity=_decimal(row.scrap_quantity),
                raw_rows=_json_array(row.raw_json),
            )
            for row in cached
        ]


def _merge_ifs_actual(actual: IfsActual, row: Mapping[str, Any]) -> None:
    actual.raw_rows.append(dict(row))
    actual.release_no = actual.release_no or _first_text(row, ("ReleaseNo", "release_no"))
    actual.sequence_no = actual.sequence_no or _first_text(
        row,
        ("SequenceNo", "sequence_no"),
    )
    actual.operation_no = actual.operation_no or _int_value(
        _first_value(row, ("OperationNo", "operation_no"))
    )
    actual.work_center_no = actual.work_center_no or _first_text(
        row,
        ("WorkCenterNo", "work_center_no"),
    )
    actual.part_no = actual.part_no or _first_text(row, ("PartNo", "part_no"))
    actual.part_description = actual.part_description or _first_text(
        row,
        ("PartNoDesc", "part_description", "Description"),
    )
    actual.actual_start_at = _earliest(
        actual.actual_start_at,
        _first_datetime(row, DATETIME_FIELDS_START),
    )
    actual.actual_finish_at = _latest(
        actual.actual_finish_at,
        _first_datetime(row, DATETIME_FIELDS_FINISH),
    )
    actual.net_machine_minutes = _add_decimal(
        actual.net_machine_minutes,
        _duration_minutes(row, NET_MACHINE_DURATION_FIELDS),
    )
    actual.completed_quantity = _add_decimal(
        actual.completed_quantity,
        _first_decimal(row, COMPLETED_QTY_FIELDS),
    )
    actual.scrap_quantity = _add_decimal(
        actual.scrap_quantity,
        _first_decimal(row, SCRAP_QTY_FIELDS),
    )


def _cycle_time_for_row(
    cycle_entries: Any,
    *,
    machine_group: str | None,
    machine_code: str,
    neck: Decimal | None,
    gram: Decimal | None,
) -> tuple[Decimal | None, str | None]:
    if not machine_group:
        return None, "Machine group not found"
    if neck is None or gram is None:
        return None, "Product neck/gram not found"
    cycle, warning = _lookup_optimum_cycle(
        cycle_entries,
        machine_group=normalize_machine_group(machine_group),
        machine_no=machine_code,
        neck_diameter=neck,
        gram=gram,
    )
    return cycle, warning


def _optimum_quantity(
    minutes: Decimal | None,
    cycle_seconds: Decimal | None,
    active_cavities: Decimal | None,
) -> Decimal | None:
    if minutes is None or cycle_seconds is None or active_cavities is None:
        return None
    if cycle_seconds <= 0 or active_cavities <= 0:
        return None
    return (minutes * Decimal(60) / cycle_seconds) * active_cavities


def _write_workbook(output_path: Path, rows: Sequence[ProductionLossReportRow]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Production Loss"
    worksheet.append(REPORT_HEADERS)

    for row in rows:
        worksheet.append(
            [
                row.record_date,
                row.machine_name,
                row.machine_code,
                row.job_order,
                row.product_description,
                _excel_decimal(row.gram),
                row.shift_2400_0800_quantity,
                row.shift_0800_1600_quantity,
                row.shift_1600_2400_quantity,
                row.daily_total_quantity,
                _excel_decimal(row.active_cavities),
                _excel_decimal(row.cycle_time_seconds),
                _excel_decimal(row.net_machine_minutes),
                _excel_decimal(row.gross_elapsed_minutes),
                _excel_decimal(row.optimum_net_quantity),
                _excel_decimal(row.production_loss_net),
                _excel_decimal(row.optimum_gross_quantity),
                _excel_decimal(row.production_loss_gross),
                _excel_decimal(row.break_loss_quantity),
                row.local_breakdown_minutes,
                row.warnings,
            ]
        )

    header_fill = PatternFill("solid", fgColor="1F4E78")
    header_font = Font(bold=True, color="FFFFFF")
    border = Border(bottom=Side(style="thin", color="D9E2F3"))
    for cell in worksheet[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")

    for row_cells in worksheet.iter_rows(min_row=2, max_row=worksheet.max_row):
        for cell in row_cells:
            cell.border = border
            cell.alignment = Alignment(vertical="center")

    for column_cells in worksheet.columns:
        column_letter = column_cells[0].column_letter
        max_length = max(len(_clean_text(cell.value)) for cell in column_cells)
        worksheet.column_dimensions[column_letter].width = min(
            max(max_length + 2, 12),
            36,
        )

    worksheet.freeze_panes = "A2"
    worksheet.auto_filter.ref = worksheet.dimensions
    workbook.save(output_path)
    workbook.close()


def _report_output_path(
    settings: Settings,
    report_id: int,
    start_date: Date,
    end_date: Date,
) -> Path:
    output_dir = Path(settings.report_output_dir).expanduser()
    return (
        output_dir
        / f"{start_date.isoformat()}_{end_date.isoformat()} Production Loss {report_id}.xlsx"
    )


def _date_range(date_from: str, date_to: str) -> tuple[Date, Date]:
    start = _iso_date(date_from, "date_from")
    end = _iso_date(date_to, "date_to")
    if end < start:
        raise ProductionLossReportError("date_to date_from degerinden once olamaz.")
    return start, end


def _iso_date(value: Any, field_name: str) -> Date:
    normalized = normalize_process_date(value)
    if not normalized:
        raise ProductionLossReportError(f"{field_name} zorunludur.")
    try:
        return Date.fromisoformat(normalized)
    except ValueError as exc:
        raise ProductionLossReportError(
            f"{field_name} YYYY-MM-DD formatinda olmalidir."
        ) from exc


def _matching_ifs_actual(
    aggregate: ShiftAggregate,
    actuals: dict[tuple[str, str | None], IfsActual],
    by_order: dict[str, list[IfsActual]],
) -> IfsActual | None:
    exact = actuals.get((aggregate.job_order, aggregate.machine_code))
    if exact is not None:
        return exact
    order_actuals = by_order.get(aggregate.job_order, [])
    if len(order_actuals) == 1:
        return order_actuals[0]
    return None


def _ifs_actuals_by_order(actuals: Iterable[IfsActual]) -> dict[str, list[IfsActual]]:
    by_order: dict[str, list[IfsActual]] = defaultdict(list)
    for actual in actuals:
        by_order[actual.job_order].append(actual)
    return by_order


def _gram_from_product_description(value: str) -> Decimal | None:
    match = GRAM_PATTERN.search(value)
    if match is None:
        return None
    return _decimal(match.group(1))


def _minutes_between(
    start: datetime | None,
    finish: datetime | None,
) -> Decimal | None:
    if start is None or finish is None or finish < start:
        return None
    return Decimal(str((finish - start).total_seconds())) / Decimal(60)


def _duration_minutes(
    row: Mapping[str, Any],
    field_names: Sequence[str],
) -> Decimal | None:
    for field_name in field_names:
        value = _first_value(row, (field_name,))
        number = _decimal(value)
        if number is None:
            continue
        lowered = field_name.casefold()
        if "second" in lowered:
            return number / Decimal(60)
        if "hour" in lowered:
            return number * Decimal(60)
        return number
    return None


def _first_datetime(
    row: Mapping[str, Any],
    field_names: Sequence[str],
) -> datetime | None:
    for field_name in field_names:
        parsed = _datetime_value(_first_value(row, (field_name,)))
        if parsed is not None:
            return parsed
    return None


def _datetime_value(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif value is None:
        return None
    else:
        text = str(value).strip()
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None

    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(UTC).replace(tzinfo=None)
    return parsed


def _first_decimal(
    row: Mapping[str, Any],
    field_names: Sequence[str],
) -> Decimal | None:
    for field_name in field_names:
        number = _decimal(_first_value(row, (field_name,)))
        if number is not None:
            return number
    return None


def _first_text(row: Mapping[str, Any], field_names: Sequence[str]) -> str | None:
    for field_name in field_names:
        text = _optional_text(_first_value(row, (field_name,)))
        if text is not None:
            return text
    return None


def _first_value(row: Mapping[str, Any], field_names: Sequence[str]) -> Any:
    for field_name in field_names:
        if field_name in row:
            return row[field_name]
    return None


def _first_breakdown_product(
    breakdowns: Sequence[MachineBreakdown],
) -> str | None:
    for breakdown in breakdowns:
        product = _optional_text(breakdown.produced_product)
        if product is not None:
            return product
    return None


def _identifier(value: Any) -> str:
    text = _clean_text(value)
    if re.fullmatch(r"\d+\.0+", text):
        return text.split(".", 1)[0]
    return text


def _optional_text(value: Any) -> str | None:
    text = _clean_text(value)
    return text or None


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).strip().split())


def _decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return Decimal(str(value))
    text = _clean_text(value).replace(",", ".")
    if not text:
        return None
    try:
        number = Decimal(text)
    except InvalidOperation:
        return None
    if not number.is_finite():
        return None
    return number


def _int_value(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _add_decimal(left: Decimal | None, right: Decimal | None) -> Decimal | None:
    if right is None:
        return left
    if left is None:
        return right
    return left + right


def _earliest(left: datetime | None, right: datetime | None) -> datetime | None:
    if right is None:
        return left
    if left is None or right < left:
        return right
    return left


def _latest(left: datetime | None, right: datetime | None) -> datetime | None:
    if right is None:
        return left
    if left is None or right > left:
        return right
    return left


def _decimal_text(value: Decimal | None) -> str | None:
    if value is None:
        return None
    rounded = value.quantize(Decimal("0.01"))
    return format(rounded, "f").rstrip("0").rstrip(".") or "0"


def _excel_decimal(value: str | None) -> float | int | None:
    number = _decimal(value)
    if number is None:
        return None
    if number == number.to_integral_value():
        return int(number)
    return float(number)


def _json_object(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _json_array(value: str | None) -> list[dict[str, Any]]:
    if not value:
        return []
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    return [row for row in payload if isinstance(row, dict)]


def _natural_machine_key(value: str) -> tuple[int, str]:
    try:
        return (0, f"{int(value):08d}")
    except (TypeError, ValueError):
        return (1, str(value))
