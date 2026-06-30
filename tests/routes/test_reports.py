import json
from pathlib import Path

from openpyxl import load_workbook

from app.core.database import create_session
from app.models import (
    AmountControlShift,
    Entry,
    Machine,
    ProductionLossReport,
    ProductionLossReportRow,
)
from tests.routes.helpers import _tour_context


def test_cycle_report_endpoint_creates_today_report(client, monkeypatch):
    async def fake_fetch_pet_ongoing_operations(_settings):
        return [
            {
                "OrderNo": "WO-1",
                "PreferredResourceId": "101",
                "WorkCenterNo": "SP25",
                "PartNoDesc": "PET0001-01 400ML SEFFAF 28MM YIVLI 6GR",
            }
        ]

    monkeypatch.setattr(
        "app.features.cycle_reports.service.fetch_pet_ongoing_operations",
        fake_fetch_pet_ongoing_operations,
    )
    context_id = _tour_context(client)
    entry_response = client.post(
        "/api/entries",
        json={
            "tour_context_id": context_id,
            "payload": {
                "col_f": "101",
                "col_g": "WO-1",
                "col_h": "16",
                "col_i": "12",
                "col_j": "12,5",
            },
        },
    )
    assert entry_response.status_code == 201

    response = client.post("/api/cycle-report/today")

    assert response.status_code == 200
    payload = response.json()
    assert payload["row_count"] == 1
    assert payload["matched_count"] == 1
    assert payload["warning_count"] == 0
    assert payload["date"] == "2026-06-08"

    output_path = Path(payload["output_path"])
    assert output_path.name == "08.06.2026 Cycle Report.xlsx"
    assert output_path.exists()
    workbook = load_workbook(output_path)
    worksheet = workbook["Çevrim Kontrol"]
    assert [cell.value for cell in worksheet[2]] == [
        "SP25",
        "101",
        28,
        6,
        16,
        12,
        12.5,
        12,
        "Uygun",
        "Uygun",
    ]
    workbook.close()


def test_production_loss_report_endpoint_creates_snapshot(client, monkeypatch):
    settings = client.app.state.settings
    with create_session(settings) as session:
        machine = session.query(Machine).filter_by(machine_code="101").one()
        session.add_all(
            [
                AmountControlShift(
                    record_date="2026-06-08",
                    machine=machine,
                    job_order="WO-1",
                    shift="08.00-16.00",
                    worker_names="Operator One",
                    produced_quantity=100,
                ),
                Entry(
                    col_a="08.06.2026",
                    col_f="101",
                    col_g="Fallback Product",
                    col_h="WO-1",
                    col_k="1",
                    col_l="15",
                    process_date="2026-06-08",
                    machine_code="101",
                    sync_status="synced",
                ),
                Entry(
                    col_a="08.06.2026",
                    col_f="101",
                    col_g="Second Product",
                    col_h="WO-2",
                    col_k="1",
                    col_l=None,
                    process_date="2026-06-08",
                    machine_code="101",
                    sync_status="synced",
                ),
            ]
        )
        session.commit()

    async def fake_fetch_actuals(_settings, order_numbers):
        assert order_numbers == ["WO-1", "WO-2"]
        return [
            {
                "OrderNo": "WO-1",
                "PreferredResourceId": "101",
                "WorkCenterNo": "SP25",
                "PartNoDesc": "PET 28MM 6GR",
                "ActualStartDate": "2026-06-08T08:00:00+03:00",
                "ActualFinishDate": "2026-06-08T09:00:00+03:00",
                "NetMachineMinutes": 60,
            },
            {
                "OrderNo": "WO-2",
                "PreferredResourceId": "101",
                "WorkCenterNo": "SP25",
                "PartNoDesc": "PET 28MM 6GR",
                "ActualStartDate": "2026-06-08T09:00:00+03:00",
                "ActualFinishDate": "2026-06-08T10:00:00+03:00",
                "NetMachineMinutes": 60,
            },
        ]

    monkeypatch.setattr(
        "app.features.production_loss.service.fetch_shop_order_operation_actual_rows",
        fake_fetch_actuals,
    )

    async def fake_fetch_label_stock(
        _settings,
        *,
        date_from,
        date_to,
    ):
        return []

    monkeypatch.setattr(
        "app.features.production_loss.service.fetch_production_label_stock_rows",
        fake_fetch_label_stock,
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
                "TransactionId": "TX-100",
                "TimeOfProduction": "2026-06-08T05:10:00Z",
                "QtyComplete": "100",
                "ResourceId": "101",
                "OrderNo": "WO-1",
                "PartNo": "PET-6",
            },
            {
                "TransactionId": "TX-200",
                "TimeOfProduction": "2026-06-08T06:20:00Z",
                "QtyComplete": "50",
                "ResourceId": "101",
                "OrderNo": "WO-2",
                "PartNo": "PET-6",
            },
        ]

    monkeypatch.setattr(
        "app.features.production_loss.service.fetch_shop_order_operation_history_rows",
        fake_fetch_operation_history,
    )

    async def fake_fetch_part_descriptions(_settings, part_numbers):
        assert part_numbers == ["PET-6"]
        return {"PET-6": "PET 28MM 6GR"}

    monkeypatch.setattr(
        "app.features.production_loss.service.fetch_inventory_part_descriptions",
        fake_fetch_part_descriptions,
    )

    response = client.post(
        "/api/production-loss-reports",
        json={
            "date_from": "2026-06-08",
            "date_to": "2026-06-08",
            "refresh_ifs": True,
        },
    )

    assert response.status_code == 200, response.json()
    payload = response.json()
    assert payload["row_count"] == 1
    assert payload["warning_count"] == 1
    first_row = payload["rows"][0]
    expected_first_row_values = {
        "job_order": "WO-1",
        "daily_total_quantity": 100,
        "active_cavities": "1",
        "cycle_time_seconds": "15",
        "shift_0800_1600_actual_quantity": 100,
        "shift_0800_1600_machine_minutes": "60",
        "shift_0800_1600_optimum_quantity": "240",
        "shift_0800_1600_loss_quantity": "140",
        "net_machine_minutes": "60",
        "gross_elapsed_minutes": "60",
        "optimum_net_quantity": "240",
        "production_loss_net": "140",
        "optimum_gross_quantity": "240",
        "production_loss_gross": "140",
        "break_loss_quantity": "0",
        "local_breakdown_minutes": 0,
    }
    for key, value in expected_first_row_values.items():
        assert first_row[key] == value

    source_summary = payload["source_summary"]
    expected_source_summary_values = {
        "quantity_source": "ifs-operation-history",
        "operation_history_refreshed": True,
        "operation_history_ifs_error": None,
        "operation_history_row_count": 2,
        "operation_history_event_count": 2,
        "operation_history_quantity_total": 150,
        "operation_history_parse_error_count": 0,
        "operation_history_out_of_range_count": 0,
        "operation_history_shift_group_count": 2,
        "operation_history_product_description_count": 1,
        "operation_history_product_description_error": None,
        "ifs_refreshed": True,
        "ifs_error": None,
        "ifs_actual_count": 2,
        "ifs_cached_count": 2,
        "quantity_group_count": 2,
        "process_match_count": 2,
        "realized_cycle_source": "process-entry-col-l",
        "realized_cycle_valid_count": 1,
        "realized_cycle_missing_count": 1,
        "realized_cycle_invalid_count": 0,
        "realized_cycle_skipped_count": 1,
        "realized_cycle_included_quantity_total": 100,
        "realized_cycle_skipped_quantity_total": 50,
    }
    for key, value in expected_source_summary_values.items():
        assert source_summary[key] == value
    assert (
        "gerceklesen cevrim eksik/gecersiz"
        in source_summary["realized_cycle_skip_message"]
    )
    assert len(source_summary["realized_cycle_skip_details"]) == 1
    skip_detail = source_summary["realized_cycle_skip_details"][0]
    assert skip_detail["record_date"] == "2026-06-08"
    assert skip_detail["machine_code"] == "101"
    assert skip_detail["job_order"] == "WO-2"
    assert skip_detail["entry_id"] is not None
    assert skip_detail["raw_cycle"] is None
    assert skip_detail["reason"] == "missing-cycle-time"
    assert skip_detail["message"] == "Gerceklesen cevrim eksik"
    assert Path(payload["output_path"]).exists()

    list_response = client.get("/api/production-loss-reports")
    assert list_response.status_code == 200
    assert list_response.json()["reports"][0]["id"] == payload["id"]
    assert list_response.json()["reports"][0]["source_summary"] == source_summary

    detail_response = client.get(f"/api/production-loss-reports/{payload['id']}")
    assert detail_response.status_code == 200
    detail_payload = detail_response.json()
    assert detail_payload["source_summary"] == source_summary
    for key, value in expected_first_row_values.items():
        assert detail_payload["rows"][0][key] == value

    with create_session(settings) as session:
        report = session.query(ProductionLossReport).one()
        report_rows = (
            session.query(ProductionLossReportRow)
            .order_by(ProductionLossReportRow.job_order)
            .all()
        )
        assert json.loads(report.source_summary_json) == source_summary
        assert report.warning_count == 1
        assert len(report_rows) == 1
        assert report_rows[0].cycle_time_seconds == "15"
        assert report_rows[0].optimum_net_quantity == "240"
        assert report_rows[0].production_loss_net == "140"
