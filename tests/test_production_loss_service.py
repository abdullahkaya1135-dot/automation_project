from datetime import date as Date
from datetime import datetime
from pathlib import Path

import pytest
from openpyxl import Workbook, load_workbook

from app.core.config import Settings
from app.core.database import create_session, init_db
from app.features.production_loss.service import (
    ProductionLossReportError,
    create_production_loss_report,
    get_production_loss_report,
    normalize_operation_history_rows,
)
from app.models import AmountControlShift, Entry, Machine, MachineBreakdown


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        excel_path=str(tmp_path / "process.xlsx"),
        app_pin="1234",
        sqlite_path=str(tmp_path / "process_entries.sqlite3"),
        backup_dir=str(tmp_path / "backups"),
        cycle_table_path=str(tmp_path / "cycle.xlsx"),
        report_output_dir=str(tmp_path / "reports"),
    )


def _create_cycle_table(path: Path) -> None:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Sayfa1"
    worksheet.append(
        [
            "Machine No",
            "Machine Name",
            "Neck",
            "GR",
            "Mold Code",
            "Production Date",
            "Estimated Cycle Time",
        ]
    )
    worksheet.append([174, "DPH70", 28, 35, "MOLD-A", None, 14])
    workbook.save(path)
    workbook.close()


def _seed_sources(settings: Settings) -> None:
    with create_session(settings) as session:
        machine = session.query(Machine).filter_by(machine_code="174").one()
        session.add_all(
            [
                AmountControlShift(
                    record_date="2026-06-08",
                    machine=machine,
                    job_order="WO-1",
                    shift="08.00-16.00",
                    worker_names="Operator One",
                    produced_quantity=999,
                ),
                Entry(
                    col_a="08.06.2026",
                    col_f="174",
                    col_g="Fallback Product",
                    col_h="WO-1",
                    col_k="2",
                    process_date="2026-06-08",
                    machine_code="174",
                    sync_status="synced",
                    submitted_at=datetime(2026, 6, 8, 10, 0),
                ),
            ]
        )
        session.flush()
        amount_shift = (
            session.query(AmountControlShift)
            .filter_by(machine_id=machine.id, job_order="WO-1", shift="08.00-16.00")
            .one()
        )
        session.add(
            MachineBreakdown(
                machine=machine,
                amount_control_shift=amount_shift,
                produced_product="Fallback Product",
                stop_reason="Planned stop",
                duration_minutes=30,
            )
        )
        session.commit()


def test_normalize_operation_history_rows_uses_local_time_for_date_and_shift(tmp_path):
    settings = _settings(tmp_path)
    rows = [
        {
            "TransactionId": "TX-LOCAL-1",
            "TimeOfProduction": "2026-06-07T21:30:00Z",
            "QtyComplete": "12",
            "ResourceId": "174",
            "OrderNo": "WO-1",
            "PartNo": "MM-PET-35",
        },
        {
            "TransactionId": "TX-LOCAL-2",
            "TimeOfProduction": "2026-06-08T05:00:00Z",
            "QtyComplete": "18",
            "ResourceId": "174",
            "OrderNo": "WO-1",
            "PartNo": "MM-PET-35",
        },
        {
            "TransactionId": "TX-OUTSIDE",
            "TimeOfProduction": "2026-06-08T21:30:00Z",
            "QtyComplete": "99",
            "ResourceId": "174",
            "OrderNo": "WO-1",
            "PartNo": "MM-PET-35",
        },
        {
            "TransactionId": "TX-ZERO",
            "TimeOfProduction": "2026-06-08T06:00:00Z",
            "QtyComplete": "0",
            "ResourceId": "174",
            "OrderNo": "WO-1",
            "PartNo": "MM-PET-35",
        },
    ]

    events, parse_error_count, out_of_range_count = normalize_operation_history_rows(
        settings,
        rows,
        Date(2026, 6, 8),
        Date(2026, 6, 8),
        product_descriptions={"MM-PET-35": "PET 28MM 35GR"},
    )

    assert parse_error_count == 1
    assert out_of_range_count == 1
    assert [(event.record_date, event.shift, event.quantity) for event in events] == [
        ("2026-06-08", "24.00-08.00", 12),
        ("2026-06-08", "08.00-16.00", 18),
    ]
    assert events[0].time_of_production.isoformat(timespec="minutes") == (
        "2026-06-08T00:30"
    )
    assert events[0].product_description == "PET 28MM 35GR"


def test_create_production_loss_report_calculates_net_gross_and_snapshot(
    tmp_path,
    monkeypatch,
):
    settings = _settings(tmp_path)
    _create_cycle_table(tmp_path / "cycle.xlsx")
    init_db(settings)
    _seed_sources(settings)

    async def fake_fetch_actuals(_settings, order_numbers):
        assert order_numbers == ["WO-1"]
        return [
            {
                "OrderNo": "WO-1",
                "ReleaseNo": "*",
                "SequenceNo": "*",
                "OperationNo": 10,
                "PreferredResourceId": "174",
                "WorkCenterNo": "70DPH",
                "PartNo": "PET-35",
                "ActualStartDate": "2026-06-08T08:00:00+03:00",
                "ActualFinishDate": "2026-06-08T10:00:00+03:00",
                "NetMachineMinutes": 100,
            }
        ]

    monkeypatch.setattr(
        "app.features.production_loss.service.fetch_shop_order_operation_actual_rows",
        fake_fetch_actuals,
    )

    async def fake_fetch_operation_history(
        _settings,
        *,
        date_from_utc,
        date_to_utc,
    ):
        assert date_from_utc.isoformat() == "2026-06-07T21:00:00+00:00"
        assert date_to_utc.isoformat() == "2026-06-08T21:00:00+00:00"
        return [
            {
                "TransactionId": "TX-1",
                "TimeOfProduction": "2026-06-08T05:00:00Z",
                "QtyComplete": "40",
                "ResourceId": "174",
                "OrderNo": "WO-1",
                "PartNo": "MM-PET-35",
            },
            {
                "TransactionId": "TX-2",
                "TimeOfProduction": "2026-06-08T05:30:00Z",
                "QtyComplete": "60",
                "ResourceId": "174",
                "OrderNo": "WO-1",
                "PartNo": "MM-PET-35",
            },
            {
                "TransactionId": "TX-3",
                "TimeOfProduction": "2026-06-08T13:00:00Z",
                "QtyComplete": "80",
                "ResourceId": "174",
                "OrderNo": "WO-1",
                "PartNo": "MM-PET-35",
            },
            {
                "TransactionId": "TX-4",
                "TimeOfProduction": "2026-06-08T21:00:00Z",
                "QtyComplete": "999",
                "ResourceId": "174",
                "OrderNo": "WO-1",
                "PartNo": "MM-PET-35",
            },
        ]

    monkeypatch.setattr(
        "app.features.production_loss.service.fetch_shop_order_operation_history_rows",
        fake_fetch_operation_history,
    )

    async def fake_fetch_part_descriptions(_settings, part_numbers):
        assert part_numbers == ["MM-PET-35"]
        return {"MM-PET-35": "PET 28MM 35GR"}

    monkeypatch.setattr(
        "app.features.production_loss.service.fetch_inventory_part_descriptions",
        fake_fetch_part_descriptions,
    )

    result = create_production_loss_report(
        settings,
        date_from="2026-06-08",
        date_to="2026-06-08",
    )

    assert result.row_count == 1
    assert result.warning_count == 0
    assert result.source_summary["quantity_source"] == "ifs-operation-history"
    assert result.source_summary["operation_history_event_count"] == 3
    assert result.source_summary["operation_history_shift_group_count"] == 2
    assert result.source_summary["operation_history_quantity_total"] == 180
    assert result.source_summary["operation_history_out_of_range_count"] == 1
    assert result.source_summary["operation_history_product_description_count"] == 1
    assert result.source_summary["operation_history_product_description_error"] is None
    assert result.output_path.exists()
    row = result.rows[0]
    assert row["machine_code"] == "174"
    assert row["machine_name"] == "70DPH"
    assert row["product_description"] == "PET 28MM 35GR"
    assert row["gram"] == "35"
    assert row["daily_total_quantity"] == 180
    assert row["active_cavities"] == "2"
    assert row["cycle_time_seconds"] == "14"
    assert row["net_machine_minutes"] == "90"
    assert row["gross_elapsed_minutes"] == "120"
    assert row["shift_0800_1600_actual_quantity"] == 100
    assert row["shift_0800_1600_machine_minutes"] == "90"
    assert row["shift_0800_1600_optimum_quantity"] == "771.43"
    assert row["shift_0800_1600_loss_quantity"] == "671.43"
    assert row["shift_1600_2400_actual_quantity"] == 80
    assert row["shift_1600_2400_machine_minutes"] == "0"
    assert row["shift_1600_2400_optimum_quantity"] == "0"
    assert row["shift_1600_2400_loss_quantity"] == "-80"
    assert row["optimum_net_quantity"] == "771.43"
    assert row["production_loss_net"] == "591.43"
    assert row["production_loss_gross"] == "848.57"
    assert row["break_loss_quantity"] == "257.14"
    assert row["local_breakdown_minutes"] == 30

    workbook = load_workbook(result.output_path)
    worksheet = workbook["Production Loss"]
    assert worksheet["A2"].value == "2026-06-08"
    assert worksheet["S2"].value == 180
    assert worksheet["Y2"].value == pytest.approx(591.43)
    workbook.close()

    with create_session(settings) as session:
        amount_shift = (
            session.query(AmountControlShift)
            .filter_by(job_order="WO-1", shift="08.00-16.00")
            .one()
        )
        amount_shift.produced_quantity = 1
        session.commit()

    snapshot = get_production_loss_report(settings, result.report_id)
    assert snapshot is not None
    assert snapshot["rows"][0]["daily_total_quantity"] == 180


def test_create_production_loss_report_requires_operation_history_rows(tmp_path):
    settings = _settings(tmp_path)
    _create_cycle_table(tmp_path / "cycle.xlsx")
    init_db(settings)

    with pytest.raises(
        ProductionLossReportError,
        match=(
            r"^Secilen tarih araliginda IFS operasyon gecmisi uretim kaydi "
            r"bulunamadi\.$"
        ),
    ):
        create_production_loss_report(
            settings,
            date_from="2026-06-08",
            date_to="2026-06-08",
            refresh_ifs=False,
            refresh_labels=False,
        )
