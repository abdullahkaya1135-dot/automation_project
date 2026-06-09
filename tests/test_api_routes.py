from collections.abc import Generator
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook, load_workbook

from app.config import Settings
from app.database import create_session
from app.main import create_app
from app.models import Entry


HEADERS = [
    "Date",
    "Ambient Temp",
    "Production Engineer",
    "Shift Chief",
    "Shift",
    "Machine",
    "Product",
    "Work Order",
    "Raw Material",
    "Total Cavity Count",
    "Active Cavity Count",
    "Cycle Time",
    "Cooling Time",
    "Injection Time",
    "Blow Time",
    "Conditioner Temp",
    "Dryer Temp",
    "Injection Pressure",
    "Injection Speed",
    "Holding Time",
    "Holding Speed",
    "Holding Pressure",
    "Clamp Force",
    "Oven Temperatures",
    "Mold Temperatures",
]
ISTANBUL_TIMEZONE = timezone(timedelta(hours=3), "Europe/Istanbul")
DEFAULT_REQUEST_TIME = datetime(2026, 6, 8, 9, 15, tzinfo=ISTANBUL_TIMEZONE)


def _create_workbook(path: Path) -> None:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "PROSES 2026"
    worksheet.append(HEADERS)
    workbook.save(path)
    workbook.close()


def _create_shop_order_source(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "value": [
                    {
                        "OrderNo": "WO-1",
                        "ResourceId": "M-01",
                        "WorkCenterNo": "SP25",
                        "PartDescription": "PET0001-01 400ML SEFFAF 28MM YIVLI 6GR",
                    },
                    {
                        "OrderNo": "WO-2",
                        "ResourceId": "M-02",
                        "WorkCenterNo": "SP25",
                        "PartDescription": "PET0002-01 400ML SEFFAF 28MM YIVLI 8GR",
                    },
                    {
                        "OrderNo": "WO-1",
                        "ResourceId": "M-01",
                        "WorkCenterNo": "SP25",
                        "PartDescription": "PET0001-01 400ML SEFFAF 28MM YIVLI 6GR",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )


def _create_cycle_table(path: Path) -> None:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Sayfa1"
    worksheet.append(
        [
            "YENİ MAKİNA NO - New Machine Code",
            "MAKİNA ADI Machine Name",
            "AĞIZ ÇAP  Neck Diameter",
            "GR",
            "PREFORM MOLD CODE",
            "PREFORM KALIBI ÜRETİM YILI PRODUCTION DATE",
            "ESTIMATED CYCLE TIME",
            "BPH",
        ]
    )
    worksheet.append(["M-01", "SP25", 28, 6, None, None, 12, None])
    workbook.save(path)
    workbook.close()


def _freeze_request_time(monkeypatch, value: datetime = DEFAULT_REQUEST_TIME) -> None:
    monkeypatch.setattr("app.main._request_datetime", lambda _settings: value)


@pytest.fixture
def client(monkeypatch, tmp_path) -> Generator[TestClient]:
    workbook_path = tmp_path / "process.xlsx"
    source_path = tmp_path / "html_to_parse.txt"
    cycle_table_path = tmp_path / "cycle.xlsx"
    _create_workbook(workbook_path)
    _create_shop_order_source(source_path)
    _create_cycle_table(cycle_table_path)
    _freeze_request_time(monkeypatch)
    monkeypatch.setenv("EXCEL_PATH", str(workbook_path))
    monkeypatch.setenv("APP_PIN", "1234")
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "process_entries.sqlite3"))
    monkeypatch.setenv("BACKUP_DIR", str(tmp_path / "backups"))
    monkeypatch.setenv("SHOP_ORDER_SOURCE_PATH", str(source_path))
    monkeypatch.setenv("CYCLE_TABLE_PATH", str(cycle_table_path))
    monkeypatch.setenv("REPORT_OUTPUT_DIR", str(tmp_path / "reports"))

    with TestClient(create_app()) as test_client:
        login_response = test_client.post("/api/login", json={"pin": "1234"})
        assert login_response.status_code == 200
        yield test_client


def _tour_context(client: TestClient) -> int:
    response = client.post(
        "/api/tour-context",
        json={
            "ambient_temp": "24,5",
            "production_engineer": "Engineer",
            "shift_chief": "Selman",
        },
    )

    assert response.status_code == 201
    return response.json()["id"]


def test_entry_submit_saves_locally_and_appends_to_excel(client, tmp_path):
    context_id = _tour_context(client)

    response = client.post(
        "/api/entries",
        json={
            "tour_context_id": context_id,
            "payload": {
                "col_f": "M-01",
                "col_g": "WO-1",
                "col_h": "16",
                "col_i": "12",
                "col_j": "12,5",
            },
            "status": "ok",
            "notes": "note",
            "mold_info": "mold",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["saved_locally"] is True
    assert payload["synced_to_excel"] is True
    assert payload["entry"]["sync_status"] == "synced"
    assert payload["entry"]["excel_row_number"] == 2
    assert payload["entry"]["payload"]["col_a"] == "08.06.2026"
    assert payload["entry"]["payload"]["col_e"] == "08.00-16.00"
    assert payload["entry"]["payload"]["col_f"] == "M-01"

    workbook = load_workbook(tmp_path / "process.xlsx")
    worksheet = workbook["PROSES 2026"]
    assert worksheet.cell(row=2, column=1).value == "08.06.2026"
    assert worksheet.cell(row=2, column=2).value == 24.5
    assert worksheet.cell(row=2, column=5).value == "08.00-16.00"
    assert worksheet.cell(row=2, column=6).value == "M-01"
    assert worksheet.cell(row=2, column=7).value is None
    assert worksheet.cell(row=2, column=8).value == "WO-1"
    assert worksheet.cell(row=2, column=9).value is None
    assert worksheet.cell(row=2, column=10).value == 16
    assert worksheet.cell(row=2, column=11).value == 12
    assert worksheet.cell(row=2, column=12).value == 12.5
    workbook.close()

    entries_response = client.get("/api/entries")
    assert entries_response.status_code == 200
    assert len(entries_response.json()["entries"]) == 1

    settings = Settings(
        excel_path=str(tmp_path / "process.xlsx"),
        app_pin="1234",
        sqlite_path=str(tmp_path / "process_entries.sqlite3"),
        backup_dir=str(tmp_path / "backups"),
    )
    with create_session(settings) as session:
        entry = session.query(Entry).one()
        assert entry.sync_status == "synced"
        assert entry.excel_row_number == 2
        assert entry.last_error is None
        assert entry.synced_at is not None


def test_cycle_report_endpoint_creates_today_report(client):
    context_id = _tour_context(client)
    entry_response = client.post(
        "/api/entries",
        json={
            "tour_context_id": context_id,
            "payload": {
                "col_f": "M-01",
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
    assert output_path.exists()
    workbook = load_workbook(output_path)
    worksheet = workbook["Çevrim Kontrol"]
    assert [cell.value for cell in worksheet[2]] == [
        "SP25",
        "M-01",
        28,
        6,
        16,
        12,
        12.5,
        12,
        "Uygun",
    ]
    workbook.close()


def test_bootstrap_and_health_endpoints_report_current_state(client):
    bootstrap_response = client.get("/api/bootstrap")
    assert bootstrap_response.status_code == 200
    bootstrap_payload = bootstrap_response.json()
    assert bootstrap_payload["excel"]["available"] is True
    assert bootstrap_payload["shop_order_source"]["available"] is True
    assert bootstrap_payload["shop_order_source"]["operation_count"] == 2
    assert bootstrap_payload["shop_order_source"]["order_count"] == 2
    assert bootstrap_payload["shop_order_source"]["resource_count"] == 2
    assert bootstrap_payload["shop_order_source"]["options"] == [
        {"order_no": "WO-1", "resource_id": "M-01"},
        {"order_no": "WO-2", "resource_id": "M-02"},
    ]
    assert bootstrap_payload["current_tour_timing"]["date"] == "08.06.2026"
    assert bootstrap_payload["current_tour_timing"]["shift"] == "08.00-16.00"
    assert bootstrap_payload["latest_tour_context"] is None
    assert bootstrap_payload["last_sync_error"] is None

    context_id = _tour_context(client)
    refreshed_bootstrap_response = client.get("/api/bootstrap")
    assert refreshed_bootstrap_response.status_code == 200
    assert refreshed_bootstrap_response.json()["latest_tour_context"]["id"] == context_id

    health_response = client.get("/health")
    assert health_response.status_code == 200
    health_payload = health_response.json()
    assert health_payload["status"] == "ok"
    assert health_payload["sqlite"]["ok"] is True
    assert health_payload["excel"]["ok"] is True


def test_tour_context_uses_request_time_for_date_and_shift(client, monkeypatch):
    _freeze_request_time(
        monkeypatch,
        datetime(2026, 6, 9, 2, 30, tzinfo=ISTANBUL_TIMEZONE),
    )

    response = client.post(
        "/api/tour-context",
        json={
            "date": "1999-01-01",
            "ambient_temp": "24,5",
            "production_engineer": "Engineer",
            "shift_chief": "Selman",
            "shift": "16.00-24.00",
        },
    )

    assert response.status_code == 201
    context = response.json()["tour_context"]
    assert context["date"] == "09.06.2026"
    assert context["shift"] == "24.00-08.00"


def test_tour_context_rejects_unknown_shift_chief(client):
    response = client.post(
        "/api/tour-context",
        json={
            "ambient_temp": "24,5",
            "production_engineer": "Engineer",
            "shift_chief": "Chief",
        },
    )

    assert response.status_code == 422
    assert "Selman, Serkan, Hakan" in response.json()["detail"]


@pytest.mark.parametrize(
    ("request_time", "expected_shift"),
    [
        (datetime(2026, 6, 8, 7, 59, tzinfo=ISTANBUL_TIMEZONE), "24.00-08.00"),
        (datetime(2026, 6, 8, 8, 0, tzinfo=ISTANBUL_TIMEZONE), "08.00-16.00"),
        (datetime(2026, 6, 8, 15, 59, tzinfo=ISTANBUL_TIMEZONE), "08.00-16.00"),
        (datetime(2026, 6, 8, 16, 0, tzinfo=ISTANBUL_TIMEZONE), "16.00-24.00"),
    ],
)
def test_shift_boundaries(request_time, expected_shift):
    from app.main import _shift_for_request_time

    assert _shift_for_request_time(request_time) == expected_shift


def test_entry_submit_remains_pending_until_retry(monkeypatch, tmp_path):
    workbook_path = tmp_path / "process.xlsx"
    source_path = tmp_path / "html_to_parse.txt"
    _create_shop_order_source(source_path)
    _freeze_request_time(monkeypatch)
    monkeypatch.setenv("EXCEL_PATH", str(workbook_path))
    monkeypatch.setenv("APP_PIN", "1234")
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "process_entries.sqlite3"))
    monkeypatch.setenv("BACKUP_DIR", str(tmp_path / "backups"))
    monkeypatch.setenv("SHOP_ORDER_SOURCE_PATH", str(source_path))

    with TestClient(create_app()) as client:
        login_response = client.post("/api/login", json={"pin": "1234"})
        assert login_response.status_code == 200
        context_id = _tour_context(client)

        pending_response = client.post(
            "/api/entries",
            json={
                "tour_context_id": context_id,
                "payload": {
                    "col_f": "M-01",
                    "col_g": "WO-1",
                },
            },
        )

        assert pending_response.status_code == 201
        pending_payload = pending_response.json()
        assert pending_payload["synced_to_excel"] is False
        assert pending_payload["entry"]["sync_status"] == "pending_excel"
        assert "Çalışma kitabı bulunamadı" in pending_payload["entry"]["last_error"]

        pending_entries_response = client.get(
            "/api/entries",
            params={"sync_status": "pending_excel"},
        )
        assert pending_entries_response.status_code == 200
        pending_entries = pending_entries_response.json()["entries"]
        assert len(pending_entries) == 1
        assert pending_entries[0]["sync_status"] == "pending_excel"
        assert pending_entries[0]["excel_row_number"] is None

        _create_workbook(workbook_path)
        retry_response = client.post("/api/sync/retry")

    assert retry_response.status_code == 200
    retry_payload = retry_response.json()
    assert retry_payload["attempted"] == 1
    assert retry_payload["synced"] == 1
    assert retry_payload["remaining"] == 0

    workbook = load_workbook(workbook_path)
    worksheet = workbook["PROSES 2026"]
    assert worksheet.cell(row=2, column=6).value == "M-01"
    assert worksheet.cell(row=2, column=8).value == "WO-1"
    workbook.close()

    settings = Settings(
        excel_path=str(workbook_path),
        app_pin="1234",
        sqlite_path=str(tmp_path / "process_entries.sqlite3"),
        backup_dir=str(tmp_path / "backups"),
    )
    with create_session(settings) as session:
        entry = session.query(Entry).one()
        assert entry.sync_status == "synced"
        assert entry.excel_row_number == 2
        assert entry.last_error is None
        assert entry.synced_at is not None
