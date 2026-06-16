import json
import shutil
from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook, load_workbook
from openpyxl.workbook.workbook import Workbook as OpenpyxlWorkbook

from app.config import Settings
from app.database import commit_session, create_session
from app.domain.entry_fields import ENTRY_FORM_FIELD_NAMES, ENTRY_PAYLOAD_SCHEMA_VERSION
from app.domain.entry_payloads import MULTI_VALUE_REPEAT_FIELDS
from app.main import create_app
from app.models import SYNC_STATUS_PENDING_EXCEL, AuxiliarySystemsSubmission, Entry
from app.modules.auxiliary_systems.workbook_service import (
    AUXILIARY_CHECK_FIELD_NAMES,
    AUXILIARY_FIELD_NAMES,
    AUXILIARY_MEASUREMENT_FIELD_NAMES,
)

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
AUXILIARY_HEADERS = [
    "TARİH",
    "MAKİNE ",
    "ÇIKIŞ FREKANSI (HZ)",
    "SET DEĞERİ (BAR)",
    "GERİ BESLEME (BAR)",
    "ISI SET DEĞERİ ©",
    "GİRİŞ ISISI ©",
    "ÇIKIŞ ISISI ©",
    "KOMP BASINÇ DEĞERİ (BAR)",
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


def _ifs_operations() -> list[dict[str, object]]:
    return [
        {
            "OrderNo": "WO-1",
            "PreferredResourceId": "M-01",
            "WorkCenterNo": "SP25",
            "PartNoDesc": "PET0001-01 400ML SEFFAF 28MM YIVLI 6GR",
        },
        {
            "OrderNo": "WO-2",
            "PreferredResourceId": "M-02",
            "WorkCenterNo": "SP25",
            "PartNoDesc": "PET0002-01 400ML SEFFAF 28MM YIVLI 8GR",
        },
        {
            "OrderNo": "WO-1",
            "PreferredResourceId": "M-01",
            "WorkCenterNo": "SP25",
            "PartNoDesc": "PET0001-01 400ML SEFFAF 28MM YIVLI 6GR",
        },
    ]


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


def _create_auxiliary_workbook(path: Path) -> None:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "YARDIMCI TESİSLER TAKİP"
    worksheet.append(AUXILIARY_HEADERS)
    workbook.save(path)
    workbook.close()


def _create_auxiliary_form(path: Path) -> None:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "FORM"
    worksheet["A1"] = "YARDIMCI TESİSLER KONTROL FORMU"
    workbook.save(path)
    workbook.close()


def _freeze_request_time(monkeypatch, value: datetime = DEFAULT_REQUEST_TIME) -> None:
    monkeypatch.setattr("app.domain.shifts.request_datetime", lambda _settings: value)


@pytest.fixture
def client(monkeypatch, tmp_path) -> Generator[TestClient]:
    workbook_path = tmp_path / "process.xlsx"
    cycle_table_path = tmp_path / "cycle.xlsx"
    auxiliary_target_path = tmp_path / "auxiliary.xlsx"
    auxiliary_form_path = tmp_path / "auxiliary_form.xlsx"
    _create_workbook(workbook_path)
    _create_cycle_table(cycle_table_path)
    _create_auxiliary_workbook(auxiliary_target_path)
    _create_auxiliary_form(auxiliary_form_path)
    _freeze_request_time(monkeypatch)

    async def fake_fetch_pet_ongoing_operations(_settings):
        return _ifs_operations()

    monkeypatch.setattr(
        "app.modules.bootstrap.service.fetch_pet_ongoing_operations",
        fake_fetch_pet_ongoing_operations,
    )
    monkeypatch.setattr(
        "app.modules.reports.cycle_report_service.fetch_pet_ongoing_operations",
        fake_fetch_pet_ongoing_operations,
    )
    monkeypatch.setenv("EXCEL_PATH", str(workbook_path))
    monkeypatch.setenv("APP_PIN", "1234")
    monkeypatch.setenv("SESSION_SECRET", "test-session-secret")
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "process_entries.sqlite3"))
    monkeypatch.setenv("BACKUP_DIR", str(tmp_path / "backups"))
    monkeypatch.setenv("CYCLE_TABLE_PATH", str(cycle_table_path))
    monkeypatch.setenv("REPORT_OUTPUT_DIR", str(tmp_path / "reports"))
    monkeypatch.setenv("AUXILIARY_SYSTEMS_FORM_PATH", str(auxiliary_form_path))
    monkeypatch.setenv("AUXILIARY_SYSTEMS_TARGET_PATH", str(auxiliary_target_path))
    monkeypatch.setenv("AUXILIARY_SYSTEMS_SHEET_NAME", "YARDIMCI TESİSLER TAKİP")

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
            "payload_schema_version": 2,
            "payload": {
                "col_f": "101",
                "col_g": "Product 101",
                "col_h": "WO-1",
                "col_i": "HM-02-01",
                "col_j": "16",
                "col_k": "12",
                "col_l": "12,5",
                "col_r": "99x2",
                "col_x": "270x3,276x2,275",
                "col_y": "30x2,40",
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
    assert payload["entry"]["payload"]["col_f"] == "101"
    assert payload["entry"]["payload"]["col_h"] == "WO-1"
    assert payload["entry"]["payload"]["col_r"] is None
    assert payload["entry"]["payload"]["col_x"] == "270-270-270-276-276-275"
    assert payload["entry"]["payload"]["col_y"] == "30-30-40"

    workbook = load_workbook(tmp_path / "process.xlsx")
    worksheet = workbook["PROSES 2026"]
    assert worksheet.cell(row=2, column=1).value == "08.06.2026"
    assert worksheet.cell(row=2, column=2).value == 24.5
    assert worksheet.cell(row=2, column=5).value == "08.00-16.00"
    assert worksheet.cell(row=2, column=6).value == "101"
    assert worksheet.cell(row=2, column=7).value == "Product 101"
    assert worksheet.cell(row=2, column=8).value == "WO-1"
    assert worksheet.cell(row=2, column=9).value == "HM-02-01"
    assert worksheet.cell(row=2, column=10).value == 16
    assert worksheet.cell(row=2, column=11).value == 12
    assert worksheet.cell(row=2, column=12).value == 12.5
    assert worksheet.cell(row=2, column=18).value is None
    assert worksheet.cell(row=2, column=24).value == "270-270-270-276-276-275"
    assert worksheet.cell(row=2, column=25).value == "30-30-40"
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


def test_entry_submit_is_idempotent_for_client_request_id(client, tmp_path):
    context_id = _tour_context(client)
    request_body = {
        "client_request_id": "entry-client-request-1",
        "client_recorded_at": "2026-06-08T09:20:00+03:00",
        "tour_context_id": context_id,
        "payload": {
            "col_f": "M-01",
            "col_g": "WO-1",
            "col_h": "16",
        },
    }

    first_response = client.post("/api/entries", json=request_body)
    replay_response = client.post("/api/entries", json=request_body)

    assert first_response.status_code == 201
    assert replay_response.status_code == 200
    first_payload = first_response.json()
    replay_payload = replay_response.json()
    assert replay_payload["idempotent_replay"] is True
    assert replay_payload["entry"]["id"] == first_payload["entry"]["id"]
    assert replay_payload["entry"]["client_request_id"] == "entry-client-request-1"

    workbook = load_workbook(tmp_path / "process.xlsx")
    worksheet = workbook["PROSES 2026"]
    assert worksheet.cell(row=2, column=6).value == "M-01"
    assert worksheet.cell(row=3, column=6).value is None
    workbook.close()

    settings = Settings(
        excel_path=str(tmp_path / "process.xlsx"),
        app_pin="1234",
        sqlite_path=str(tmp_path / "process_entries.sqlite3"),
        backup_dir=str(tmp_path / "backups"),
    )
    with create_session(settings) as session:
        assert session.query(Entry).count() == 1


def test_second_section_entry_blanks_first_section_only_columns(client, tmp_path):
    context_id = _tour_context(client)

    response = client.post(
        "/api/entries",
        json={
            "tour_context_id": context_id,
            "payload_schema_version": 2,
            "payload": {
                "col_f": "203",
                "col_g": "Product 203",
                "col_h": "WO-203",
                "col_i": "HM-02-203",
                "col_j": "16",
                "col_o": "6",
                "col_p": "45",
                "col_q": "180",
                "col_r": "70x2,69",
                "col_s": "49x2",
                "col_t": "1,5",
                "col_u": "25",
                "col_v": "30",
                "col_w": "125",
                "col_x": "230-195",
            },
        },
    )

    assert response.status_code == 201
    entry_payload = response.json()["entry"]["payload"]
    assert entry_payload["col_o"] is None
    assert entry_payload["col_p"] is None
    assert entry_payload["col_q"] is None
    assert entry_payload["col_r"] == "70-70-69"
    assert entry_payload["col_s"] == "49-49"

    workbook = load_workbook(tmp_path / "process.xlsx")
    worksheet = workbook["PROSES 2026"]
    assert worksheet.cell(row=2, column=6).value == "203"
    assert worksheet.cell(row=2, column=15).value is None
    assert worksheet.cell(row=2, column=16).value is None
    assert worksheet.cell(row=2, column=17).value is None
    assert worksheet.cell(row=2, column=18).value == "70-70-69"
    assert worksheet.cell(row=2, column=19).value == "49-49"
    assert worksheet.cell(row=2, column=20).value == 1.5
    assert worksheet.cell(row=2, column=23).value == 125
    assert worksheet.cell(row=2, column=24).value == "230-195"
    workbook.close()


def test_legacy_entry_payload_is_canonicalized_before_excel_append(client, tmp_path):
    context_id = _tour_context(client)

    response = client.post(
        "/api/entries",
        json={
            "tour_context_id": context_id,
            "payload": {
                "col_f": "101",
                "col_g": "WO-LEGACY",
                "col_h": "16",
                "col_i": "12",
                "col_j": "12,5",
                "col_p": "270x2",
                "col_q": "30x2",
            },
        },
    )

    assert response.status_code == 201
    entry_payload = response.json()["entry"]["payload"]
    assert entry_payload["col_g"] is None
    assert entry_payload["col_h"] == "WO-LEGACY"
    assert entry_payload["col_j"] == "16"
    assert entry_payload["col_k"] == "12"
    assert entry_payload["col_l"] == "12,5"
    assert entry_payload["col_x"] == "270-270"
    assert entry_payload["col_y"] == "30-30"

    workbook = load_workbook(tmp_path / "process.xlsx")
    worksheet = workbook["PROSES 2026"]
    assert worksheet.cell(row=2, column=7).value is None
    assert worksheet.cell(row=2, column=8).value == "WO-LEGACY"
    assert worksheet.cell(row=2, column=10).value == 16
    assert worksheet.cell(row=2, column=11).value == 12
    assert worksheet.cell(row=2, column=12).value == 12.5
    assert worksheet.cell(row=2, column=24).value == "270-270"
    assert worksheet.cell(row=2, column=25).value == "30-30"
    workbook.close()


def test_auxiliary_systems_submission_saves_locally_and_appends_block(
    client,
    tmp_path,
):
    response = client.post(
        "/api/auxiliary-systems/submissions",
        json={
            "recorded_date": "2026-06-08",
            "payload": {
                "tower_frequency": "50",
                "tower_set_pressure": "3,6",
                "tower_feedback_pressure": "3.5",
                "termokar_chiller_1_temp_set": "12",
                "termokar_chiller_1_inlet_temp": "13,9",
                "termokar_chiller_1_outlet_temp": "12.3",
                "compressor_high_708_pressure": "31,4",
                "compressor_low_716_pressure": "11.4",
                "oil_cooling_water_tank_checked": True,
            },
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["saved_locally"] is True
    assert payload["synced_to_excel"] is True
    assert payload["submission"]["sync_status"] == "synced"
    assert payload["submission"]["excel_start_row"] == 2
    assert payload["submission"]["excel_end_row"] == 16
    assert payload["submission"]["payload"]["oil_cooling_water_tank_checked"] is True

    workbook = load_workbook(tmp_path / "auxiliary.xlsx")
    worksheet = workbook["YARDIMCI TESİSLER TAKİP"]
    assert worksheet.cell(row=2, column=1).value == "08.06.2026"
    assert worksheet.cell(row=2, column=2).value == "1- ELEKTROMOTOR (KULE)"
    assert worksheet.cell(row=2, column=3).value == 50
    assert worksheet.cell(row=2, column=4).value == 3.6
    assert worksheet.cell(row=2, column=5).value == 3.5
    assert worksheet.cell(row=4, column=6).value == 12
    assert worksheet.cell(row=4, column=7).value == 13.9
    assert worksheet.cell(row=4, column=8).value == 12.3
    assert worksheet.cell(row=8, column=9).value == 31.4
    assert worksheet.cell(row=16, column=9).value == 11.4
    workbook.close()

    submissions_response = client.get("/api/auxiliary-systems/submissions")
    assert submissions_response.status_code == 200
    assert len(submissions_response.json()["submissions"]) == 1


def test_auxiliary_submission_is_idempotent_for_client_request_id(client, tmp_path):
    request_body = {
        "client_request_id": "auxiliary-client-request-1",
        "client_recorded_at": "2026-06-08T09:25:00+03:00",
        "recorded_date": "2026-06-08",
        "payload": {
            "tower_frequency": "50",
            "tower_set_pressure": "3,6",
            "tower_feedback_pressure": "3.5",
        },
    }

    first_response = client.post(
        "/api/auxiliary-systems/submissions",
        json=request_body,
    )
    replay_response = client.post(
        "/api/auxiliary-systems/submissions",
        json=request_body,
    )

    assert first_response.status_code == 201
    assert replay_response.status_code == 200
    first_payload = first_response.json()
    replay_payload = replay_response.json()
    assert replay_payload["idempotent_replay"] is True
    assert replay_payload["submission"]["id"] == first_payload["submission"]["id"]
    assert (
        replay_payload["submission"]["client_request_id"]
        == "auxiliary-client-request-1"
    )

    workbook = load_workbook(tmp_path / "auxiliary.xlsx")
    worksheet = workbook["YARDIMCI TESİSLER TAKİP"]
    assert worksheet.cell(row=2, column=2).value == "1- ELEKTROMOTOR (KULE)"
    assert worksheet.cell(row=17, column=2).value is None
    workbook.close()

    settings = Settings(
        excel_path=str(tmp_path / "process.xlsx"),
        app_pin="1234",
        sqlite_path=str(tmp_path / "process_entries.sqlite3"),
        backup_dir=str(tmp_path / "backups"),
    )
    with create_session(settings) as session:
        assert session.query(AuxiliarySystemsSubmission).count() == 1


def test_auxiliary_retry_uses_batch_workbook_write(client, monkeypatch, tmp_path):
    settings = Settings(
        excel_path=str(tmp_path / "process.xlsx"),
        app_pin="1234",
        sqlite_path=str(tmp_path / "process_entries.sqlite3"),
        backup_dir=str(tmp_path / "backups"),
    )
    with create_session(settings) as session:
        for index in range(3):
            session.add(
                AuxiliarySystemsSubmission(
                    recorded_date=f"2026-06-{8 + index:02d}",
                    payload_json=json.dumps(
                        {
                            "tower_frequency": str(50 + index),
                            "tower_set_pressure": "3,6",
                            "compressor_low_716_pressure": str(11 + index),
                        }
                    ),
                    sync_status=SYNC_STATUS_PENDING_EXCEL,
                )
            )
        commit_session(session)

    load_count = 0
    save_count = 0
    backup_count = 0
    real_load_workbook = load_workbook
    real_save = OpenpyxlWorkbook.save
    real_copyfile = shutil.copyfile

    def counted_load_workbook(*args, **kwargs):
        nonlocal load_count
        load_count += 1
        return real_load_workbook(*args, **kwargs)

    def counted_save(self, filename):
        nonlocal save_count
        save_count += 1
        return real_save(self, filename)

    def counted_copyfile(source, destination):
        nonlocal backup_count
        backup_count += 1
        return real_copyfile(source, destination)

    monkeypatch.setattr(
        "app.modules.auxiliary_systems.workbook_io.load_workbook",
        counted_load_workbook,
    )
    monkeypatch.setattr(OpenpyxlWorkbook, "save", counted_save)
    monkeypatch.setattr(
        "app.modules.auxiliary_systems.workbook_io.shutil.copyfile",
        counted_copyfile,
    )

    response = client.post("/api/auxiliary-systems/sync/retry")

    assert response.status_code == 200
    payload = response.json()
    assert payload["attempted"] == 3
    assert payload["synced"] == 3
    assert payload["failed"] == 0
    assert payload["remaining"] == 0
    assert payload["stopped_on_error"] is False
    assert load_count == 1
    assert save_count == 1
    assert backup_count == 1

    workbook = load_workbook(tmp_path / "auxiliary.xlsx")
    worksheet = workbook.active
    assert worksheet.cell(row=2, column=1).value == "08.06.2026"
    assert worksheet.cell(row=17, column=1).value == "09.06.2026"
    assert worksheet.cell(row=32, column=1).value == "10.06.2026"
    assert worksheet.cell(row=46, column=9).value == 13
    workbook.close()

    with create_session(settings) as session:
        rows = (
            session.query(AuxiliarySystemsSubmission)
            .order_by(AuxiliarySystemsSubmission.id.asc())
            .all()
        )
        assert [(row.excel_start_row, row.excel_end_row) for row in rows] == [
            (2, 16),
            (17, 31),
            (32, 46),
        ]
        assert {row.sync_status for row in rows} == {"synced"}


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


def test_ifs_stock_endpoint_returns_u1_hm02_stock(client, monkeypatch):
    async def fake_fetch(_settings):
        return [
            {
                "Contract": "S01",
                "PartNo": "HM-02-A",
                "PartNoRef": {"Description": "Raw Material"},
                "LocationNo": "U1",
                "LotBatchNo": "L1",
                "AvailableQty": 12.5,
                "QtyOnhand": 15,
                "UoM": "kg",
                "ObjId": "obj-1",
            }
        ]

    monkeypatch.setattr("app.modules.ifs.use_cases.fetch_u1_hm02_stock", fake_fetch)

    response = client.get("/api/ifs/u1-hm02-stock")

    assert response.status_code == 200
    assert response.json() == {
        "stock_count": 1,
        "stock": [
            {
                "contract": "S01",
                "part_no": "HM-02-A",
                "material_name": "Raw Material",
                "location_no": "U1",
                "lot_batch_no": "L1",
                "available_qty": 12.5,
                "qty_onhand": 15,
                "uom": "kg",
                "obj_id": "obj-1",
                "configuration_id": None,
                "serial_no": None,
                "eng_chg_level": None,
                "waiv_dev_rej_no": None,
                "activity_seq": None,
                "handling_unit_id": None,
            }
        ],
    }


def test_ifs_operations_endpoint_returns_pet_ongoing_operations(client, monkeypatch):
    async def fake_fetch(_settings):
        return [
            {
                "OrderNo": "2615",
                "ReleaseNo": "*",
                "SequenceNo": "*",
                "OperationNo": 10,
                "Contract": "S01",
                "WorkCenterNo": "SP25",
                "PartNo": "MM-PET0048-12-024Y-025",
                "PartNoDesc": "Bottle",
                "PreferredResourceId": "135",
                "OperationNoDesc": "Run",
                "RemainingQty": 42,
            }
        ]

    monkeypatch.setattr(
        "app.modules.ifs.use_cases.fetch_pet_ongoing_operations",
        fake_fetch,
    )

    response = client.get("/api/ifs/pet-ongoing-operations")

    assert response.status_code == 200
    assert response.json() == {
        "operation_count": 1,
        "operations": [
            {
                "order_no": "2615",
                "release_no": "*",
                "sequence_no": "*",
                "operation_no": 10,
                "contract": "S01",
                "work_center_no": "SP25",
                "part_no": "MM-PET0048-12-024Y-025",
                "part_description": "Bottle",
                "preferred_resource_id": "135",
                "operation_description": "Run",
                "remaining_qty": 42,
            }
        ],
    }


def test_ifs_operation_materials_endpoint_returns_hm02_materials(client, monkeypatch):
    called_with: dict[str, object] = {}

    async def fake_fetch(_settings, operation):
        called_with["operation"] = operation
        return [
            {
                "OrderNo": "2615",
                "ReleaseNo": "*",
                "SequenceNo": "*",
                "LineItemNo": 2,
                "OperationNo": 10,
                "PartNo": "HM-02-01-01-525",
                "IssueToLoc": "U1",
                "QtyRequired": 25.578,
                "QtyAssigned": 0,
                "QtyIssued": 0,
                "QtyRemainingToReserve": 25.578,
                "QtyAvailable": 100.72,
                "PrintUnit": "kg",
                "SoPartNo": "MM-PET0048-12-024Y-025",
                "Cf_Tercihedilenkaynak": "135",
            }
        ]

    monkeypatch.setattr(
        "app.modules.ifs.use_cases.fetch_operation_hm02_materials",
        fake_fetch,
    )

    response = client.get(
        "/api/ifs/operation-hm02-materials",
        params={"order_no": "2615", "operation_no": 10},
    )

    assert response.status_code == 200
    assert called_with["operation"] == {
        "OrderNo": "2615",
        "ReleaseNo": "*",
        "SequenceNo": "*",
        "OperationNo": 10,
    }
    assert response.json() == {
        "material_count": 1,
        "materials": [
            {
                "order_no": "2615",
                "release_no": "*",
                "sequence_no": "*",
                "line_item_no": 2,
                "operation_no": 10,
                "part_no": "HM-02-01-01-525",
                "issue_to_location": "U1",
                "qty_required": 25.578,
                "qty_assigned": 0,
                "qty_issued": 0,
                "qty_remaining_to_reserve": 25.578,
                "qty_available": 100.72,
                "print_unit": "kg",
                "produced_part_no": "MM-PET0048-12-024Y-025",
                "machine": "135",
            }
        ],
    }


def test_ifs_used_materials_endpoint_returns_used_hm02_set(client, monkeypatch):
    async def fake_fetch(_settings):
        return {
            "operation_count": 2,
            "used_material_count": 2,
            "used_hm02_part_count": 1,
            "used_hm02_parts": ["HM-02-01-01-525"],
            "used_materials": [
                {
                    "OrderNo": "2615",
                    "ReleaseNo": "*",
                    "SequenceNo": "*",
                    "LineItemNo": 2,
                    "OperationNo": 10,
                    "PartNo": "HM-02-01-01-525",
                    "IssueToLoc": "U1",
                    "QtyRequired": 25.578,
                    "QtyAssigned": 0,
                    "QtyIssued": 0,
                    "QtyRemainingToReserve": 25.578,
                    "QtyAvailable": 100.72,
                    "PrintUnit": "kg",
                    "SoPartNo": "MM-PET0048-12-024Y-025",
                    "Cf_Tercihedilenkaynak": "135",
                },
                {
                    "OrderNo": "2616",
                    "ReleaseNo": "*",
                    "SequenceNo": "*",
                    "LineItemNo": 4,
                    "OperationNo": 20,
                    "PartNo": "HM-02-01-01-525",
                    "IssueToLoc": "U1",
                    "QtyRequired": 12,
                    "QtyAssigned": 0,
                    "QtyIssued": 0,
                    "QtyRemainingToReserve": 12,
                    "QtyAvailable": 50,
                    "PrintUnit": "kg",
                    "SoPartNo": "MM-PET0001",
                    "Cf_Tercihedilenkaynak": "136",
                },
            ],
        }

    monkeypatch.setattr(
        "app.modules.ifs.use_cases.fetch_used_hm02_materials",
        fake_fetch,
    )

    response = client.get("/api/ifs/used-hm02-materials")

    assert response.status_code == 200
    payload = response.json()
    assert payload["operation_count"] == 2
    assert payload["used_material_count"] == 2
    assert payload["used_hm02_part_count"] == 1
    assert payload["used_hm02_parts"] == ["HM-02-01-01-525"]
    assert [row["part_no"] for row in payload["used_materials"]] == [
        "HM-02-01-01-525",
        "HM-02-01-01-525",
    ]
    assert payload["used_materials"][0]["machine"] == "135"
    assert payload["used_materials"][1]["produced_part_no"] == "MM-PET0001"


def test_ifs_return_candidates_endpoint_returns_unused_u1_stock(client, monkeypatch):
    async def fake_find(_settings):
        return {
            "generated_at": "2026-06-10T14:30:00+03:00",
            "stock_count": 3,
            "operation_count": 1,
            "active_used_material_count": 1,
            "active_used_hm02_part_count": 1,
            "planning_order_count": 1,
            "planning_operation_count": 1,
            "planning_used_material_count": 1,
            "planning_used_hm02_part_count": 1,
            "used_material_count": 2,
            "used_hm02_part_count": 2,
            "return_candidate_count": 1,
            "return_candidates": [
                {
                    "Contract": "S01",
                    "PartNo": "HM-02-C",
                    "PartNoRef": {"Description": "Candidate Material"},
                    "LocationNo": "U1",
                    "LotBatchNo": "L1",
                    "AvailableQty": 12.5,
                    "QtyOnhand": 15,
                    "UoM": "kg",
                    "ObjId": "obj-1",
                },
            ],
            "used_hm02_parts": ["HM-02-A", "HM-02-B"],
            "used_materials": [
                {
                    "OrderNo": "2615",
                    "ReleaseNo": "*",
                    "SequenceNo": "*",
                    "LineItemNo": 2,
                    "OperationNo": 10,
                    "PartNo": "HM-02-A",
                    "IssueToLoc": "U1",
                    "QtyRequired": 25.578,
                    "QtyAssigned": 0,
                    "QtyIssued": 0,
                    "QtyRemainingToReserve": 25.578,
                    "QtyAvailable": 100.72,
                    "PrintUnit": "kg",
                    "SoPartNo": "MM-PET0048-12-024Y-025",
                    "Cf_Tercihedilenkaynak": "135",
                },
                {
                    "OrderNo": "2579",
                    "ReleaseNo": "*",
                    "SequenceNo": "*",
                    "LineItemNo": 3,
                    "OperationNo": 20,
                    "PartNo": "HM-02-B",
                    "IssueToLoc": "U1",
                    "QtyRequired": 10,
                    "QtyAssigned": 0,
                    "QtyIssued": 0,
                    "QtyRemainingToReserve": 10,
                    "QtyAvailable": 40,
                    "PrintUnit": "kg",
                    "SoPartNo": "MM-PET0002",
                    "Cf_Tercihedilenkaynak": "172",
                }
            ],
        }

    monkeypatch.setattr(
        "app.modules.ifs.use_cases.find_u1_return_candidates",
        fake_find,
    )

    response = client.get("/api/ifs/u1-return-candidates")

    assert response.status_code == 200
    payload = response.json()
    assert payload["generated_at"] == "2026-06-10T14:30:00+03:00"
    assert payload["stock_count"] == 3
    assert payload["operation_count"] == 1
    assert payload["active_used_material_count"] == 1
    assert payload["active_used_hm02_part_count"] == 1
    assert payload["planning_order_count"] == 1
    assert payload["planning_operation_count"] == 1
    assert payload["planning_used_material_count"] == 1
    assert payload["planning_used_hm02_part_count"] == 1
    assert payload["used_material_count"] == 2
    assert payload["used_hm02_part_count"] == 2
    assert payload["return_candidate_count"] == 1
    assert payload["used_hm02_parts"] == ["HM-02-A", "HM-02-B"]
    assert [row["lot_batch_no"] for row in payload["return_candidates"]] == [
        "L1",
    ]
    assert [row["part_no"] for row in payload["return_candidates"]] == [
        "HM-02-C",
    ]
    assert [row["material_name"] for row in payload["return_candidates"]] == [
        "Candidate Material",
    ]
    assert all("obj_id" not in row for row in payload["return_candidates"])
    assert payload["used_materials"][0]["part_no"] == "HM-02-A"
    assert payload["used_materials"][0]["machine"] == "135"
    assert payload["used_materials"][1]["part_no"] == "HM-02-B"


def test_bootstrap_and_health_endpoints_report_current_state(client):
    bootstrap_response = client.get("/api/bootstrap")
    assert bootstrap_response.status_code == 200
    bootstrap_payload = bootstrap_response.json()
    assert bootstrap_payload["excel"]["available"] is True
    assert bootstrap_payload["auxiliary_systems"]["form_available"] is True
    assert bootstrap_payload["auxiliary_systems"]["target_available"] is True
    assert bootstrap_payload["shop_order_source"]["available"] is True
    assert bootstrap_payload["shop_order_source"]["operation_count"] == 2
    assert bootstrap_payload["shop_order_source"]["order_count"] == 2
    assert bootstrap_payload["shop_order_source"]["resource_count"] == 2
    assert bootstrap_payload["shop_order_source"]["options"] == [
        {
            "order_no": "WO-1",
            "resource_id": "M-01",
            "release_no": "*",
            "sequence_no": "*",
            "operation_no": None,
            "part_no": "",
            "part_description": "PET0001-01 400ML SEFFAF 28MM YIVLI 6GR",
        },
        {
            "order_no": "WO-2",
            "resource_id": "M-02",
            "release_no": "*",
            "sequence_no": "*",
            "operation_no": None,
            "part_no": "",
            "part_description": "PET0002-01 400ML SEFFAF 28MM YIVLI 8GR",
        },
    ]
    assert bootstrap_payload["current_tour_timing"]["date"] == "08.06.2026"
    assert bootstrap_payload["current_tour_timing"]["shift"] == "08.00-16.00"
    assert bootstrap_payload["current_auxiliary_date"] == "08.06.2026"
    assert bootstrap_payload["field_definitions"] == {
        "process_entry": {
            "payload_schema_version": ENTRY_PAYLOAD_SCHEMA_VERSION,
            "payload_fields": list(ENTRY_FORM_FIELD_NAMES),
            "temperature_repeat_fields": [
                field_name
                for field_name in ENTRY_FORM_FIELD_NAMES
                if field_name in MULTI_VALUE_REPEAT_FIELDS
            ],
        },
        "auxiliary": {
            "payload_fields": list(AUXILIARY_FIELD_NAMES),
            "measurement_fields": list(AUXILIARY_MEASUREMENT_FIELD_NAMES),
            "check_fields": list(AUXILIARY_CHECK_FIELD_NAMES),
        },
    }
    assert bootstrap_payload["latest_tour_context"] is None
    assert bootstrap_payload["last_sync_error"] is None
    assert bootstrap_payload["last_auxiliary_sync_error"] is None

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
    assert health_payload["auxiliary_systems"]["form_ok"] is True
    assert health_payload["auxiliary_systems"]["target_ok"] is True
    assert health_payload["excel_write_lock"]["locked"] is False
    assert health_payload["excel_write_lock"]["waiting"] == 0


def test_field_definitions_endpoint_matches_backend_constants(client):
    response = client.get("/api/field-definitions")

    assert response.status_code == 200
    assert response.json() == {
        "process_entry": {
            "payload_schema_version": ENTRY_PAYLOAD_SCHEMA_VERSION,
            "payload_fields": list(ENTRY_FORM_FIELD_NAMES),
            "temperature_repeat_fields": [
                field_name
                for field_name in ENTRY_FORM_FIELD_NAMES
                if field_name in MULTI_VALUE_REPEAT_FIELDS
            ],
        },
        "auxiliary": {
            "payload_fields": list(AUXILIARY_FIELD_NAMES),
            "measurement_fields": list(AUXILIARY_MEASUREMENT_FIELD_NAMES),
            "check_fields": list(AUXILIARY_CHECK_FIELD_NAMES),
        },
    }


def test_static_shell_references_current_shared_section_assets(client):
    page_response = client.get("/")
    service_worker_response = client.get("/service-worker.js")

    assert page_response.status_code == 200
    assert service_worker_response.status_code == 200
    assert 'type="module" src="/static/js/app.js?v=20260615-shop-orders"' in (
        page_response.text
    )
    assert "/static/css/app.css?v=20260615-css" in page_response.text
    assert "process-offline-shell-v9" in service_worker_response.text
    assert "api.js?v=20260612-refactor" in service_worker_response.text
    assert "app.js?v=20260615-shop-orders" in service_worker_response.text
    assert "modules/bootstrap.js?v=20260612-refactor" in service_worker_response.text
    assert "modules/field-definitions.js?v=20260615-fields" in (
        service_worker_response.text
    )
    assert "modules/pages/operator.js?v=20260615-shop-orders" in (
        service_worker_response.text
    )
    assert "modules/pages/utility.js?v=20260615-pages" in service_worker_response.text
    assert "modules/pages/supervisor.js?v=20260615-pages" in (
        service_worker_response.text
    )
    assert "modules/pages/planning.js?v=20260615-pages" in service_worker_response.text
    assert "modules/offline.js?v=20260612-refactor" not in service_worker_response.text
    assert "modules/shop-orders.js?v=20260615-shop-orders" not in (
        service_worker_response.text
    )
    assert "modules/offline/outbox-sync.js?v=20260616-offline-split" in (
        service_worker_response.text
    )
    assert "modules/shop-orders/dropdowns.js?v=20260615-shop-orders" in (
        service_worker_response.text
    )
    assert "modules/shop-orders/materials.js?v=20260615-shop-orders" in (
        service_worker_response.text
    )
    assert "modules/shop-orders/machine-section.js?v=20260615-shop-orders" in (
        service_worker_response.text
    )
    assert "modules/shop-orders/normalization.js?v=20260615-shop-orders" in (
        service_worker_response.text
    )
    assert "modules/shop-orders/state.js?v=20260615-shop-orders" in (
        service_worker_response.text
    )
    assert "modules/shop-orders/status.js?v=20260615-shop-orders" in (
        service_worker_response.text
    )
    assert "modules/render/process-entries.js?v=20260615-render" in (
        service_worker_response.text
    )
    assert "modules/render/auxiliary-submissions.js?v=20260615-render" in (
        service_worker_response.text
    )
    assert "modules/pages/planning-ifs-return.js?v=20260616-planning-ifs" in (
        service_worker_response.text
    )
    assert "modules/render/ifs-return.js?v=20260615-render" in (
        service_worker_response.text
    )
    assert "modules/ifs-return.js?v=20260612-refactor" not in (
        service_worker_response.text
    )
    assert "modules/render/shared.js?v=20260615-render" in (
        service_worker_response.text
    )
    assert "modules/render.js?v=20260612-refactor" not in (
        service_worker_response.text
    )
    assert "app.css?v=20260615-css" in service_worker_response.text
    assert "css/tokens.css?v=20260615-css" in service_worker_response.text
    assert "css/base.css?v=20260615-css" in service_worker_response.text
    assert "css/layout.css?v=20260615-css" in service_worker_response.text
    assert "css/components/nav.css?v=20260615-css" in service_worker_response.text
    assert "css/components/forms.css?v=20260615-css" in service_worker_response.text
    assert "css/components/buttons.css?v=20260615-css" in service_worker_response.text
    assert "css/components/status.css?v=20260615-css" in service_worker_response.text
    assert "css/components/lists.css?v=20260615-css" in service_worker_response.text
    assert "css/components/tables.css?v=20260615-css" in service_worker_response.text
    assert "css/pages/login.css?v=20260615-css" in service_worker_response.text
    assert "css/pages/planning.css?v=20260615-css" in service_worker_response.text
    assert "css/print.css?v=20260615-css" in service_worker_response.text
    assert "css/responsive.css?v=20260615-css" in service_worker_response.text


def test_bootstrap_can_load_shop_orders_from_ifs(client, monkeypatch):
    async def fake_fetch(_settings):
        return [
            {
                "OrderNo": "2615",
                "PreferredResourceId": "135",
                "WorkCenterNo": "SP25",
                "PartNoDesc": "Bottle",
            },
            {
                "OrderNo": "2616",
                "PreferredResourceId": "136",
                "WorkCenterNo": "SP26",
                "PartNoDesc": "Bottle 2",
            },
        ]

    monkeypatch.setattr(
        "app.modules.bootstrap.service.fetch_pet_ongoing_operations",
        fake_fetch,
    )

    response = client.get("/api/bootstrap")

    assert response.status_code == 200
    source = response.json()["shop_order_source"]
    assert source["available"] is True
    assert source["source"] == "ifs-token"
    assert source["operation_count"] == 2
    assert source["order_count"] == 2
    assert source["resource_count"] == 2
    assert source["options"] == [
        {
            "order_no": "2615",
            "resource_id": "135",
            "release_no": "*",
            "sequence_no": "*",
            "operation_no": None,
            "part_no": "",
            "part_description": "Bottle",
        },
        {
            "order_no": "2616",
            "resource_id": "136",
            "release_no": "*",
            "sequence_no": "*",
            "operation_no": None,
            "part_no": "",
            "part_description": "Bottle 2",
        },
    ]


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


def test_tour_context_uses_client_recorded_at_for_offline_shift(
    client,
    monkeypatch,
):
    _freeze_request_time(
        monkeypatch,
        datetime(2026, 6, 8, 16, 5, tzinfo=ISTANBUL_TIMEZONE),
    )

    response = client.post(
        "/api/tour-context",
        json={
            "client_request_id": "tour-client-request-1",
            "client_recorded_at": "2026-06-08T15:55:00+03:00",
            "ambient_temp": "24,5",
            "production_engineer": "Engineer",
            "shift_chief": "Selman",
        },
    )

    assert response.status_code == 201
    context = response.json()["tour_context"]
    assert context["client_request_id"] == "tour-client-request-1"
    assert context["date"] == "08.06.2026"
    assert context["shift"] == "08.00-16.00"


def test_tour_context_is_idempotent_for_client_request_id(client):
    request_body = {
        "client_request_id": "tour-client-request-2",
        "client_recorded_at": "2026-06-08T09:30:00+03:00",
        "ambient_temp": "24,5",
        "production_engineer": "Engineer",
        "shift_chief": "Selman",
    }

    first_response = client.post("/api/tour-context", json=request_body)
    replay_response = client.post("/api/tour-context", json=request_body)

    assert first_response.status_code == 201
    assert replay_response.status_code == 200
    first_payload = first_response.json()
    replay_payload = replay_response.json()
    assert replay_payload["idempotent_replay"] is True
    assert replay_payload["id"] == first_payload["id"]
    assert (
        replay_payload["tour_context"]["client_request_id"]
        == "tour-client-request-2"
    )


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
    from app.domain.shifts import shift_for_request_time

    assert shift_for_request_time(request_time) == expected_shift


def test_entry_submit_remains_pending_until_retry(monkeypatch, tmp_path):
    workbook_path = tmp_path / "process.xlsx"
    _freeze_request_time(monkeypatch)
    monkeypatch.setenv("EXCEL_PATH", str(workbook_path))
    monkeypatch.setenv("APP_PIN", "1234")
    monkeypatch.setenv("SESSION_SECRET", "test-session-secret")
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "process_entries.sqlite3"))
    monkeypatch.setenv("BACKUP_DIR", str(tmp_path / "backups"))

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


def test_retry_pending_entries_uses_batch_workbook_write(
    client,
    monkeypatch,
    tmp_path,
):
    context_id = _tour_context(client)
    settings = Settings(
        excel_path=str(tmp_path / "process.xlsx"),
        app_pin="1234",
        sqlite_path=str(tmp_path / "process_entries.sqlite3"),
        backup_dir=str(tmp_path / "backups"),
    )
    with create_session(settings) as session:
        for index in range(25):
            session.add(
                Entry(
                    tour_context_id=context_id,
                    sync_status=SYNC_STATUS_PENDING_EXCEL,
                    col_a="08.06.2026",
                    col_b="24,5",
                    col_c="Engineer",
                    col_d="Selman",
                    col_e="08.00-16.00",
                    col_f=f"M-{index + 1:02d}",
                    col_h=f"WO-{index + 1:02d}",
                )
            )
        commit_session(session)

    load_count = 0
    save_count = 0
    backup_count = 0
    real_load_workbook = load_workbook
    real_save = OpenpyxlWorkbook.save
    real_copyfile = shutil.copyfile

    def counted_load_workbook(*args, **kwargs):
        nonlocal load_count
        load_count += 1
        return real_load_workbook(*args, **kwargs)

    def counted_save(self, filename):
        nonlocal save_count
        save_count += 1
        return real_save(self, filename)

    def counted_copyfile(source, destination):
        nonlocal backup_count
        backup_count += 1
        return real_copyfile(source, destination)

    monkeypatch.setattr(
        "app.modules.process_entry.workbook_io.load_workbook",
        counted_load_workbook,
    )
    monkeypatch.setattr(OpenpyxlWorkbook, "save", counted_save)
    monkeypatch.setattr(
        "app.modules.process_entry.workbook_io.shutil.copyfile",
        counted_copyfile,
    )

    response = client.post("/api/sync/retry")

    assert response.status_code == 200
    payload = response.json()
    assert payload["attempted"] == 25
    assert payload["synced"] == 25
    assert payload["failed"] == 0
    assert payload["remaining"] == 0
    assert payload["stopped_on_error"] is False
    assert load_count == 1
    assert save_count == 1
    assert backup_count == 1

    workbook = load_workbook(tmp_path / "process.xlsx")
    worksheet = workbook["PROSES 2026"]
    assert [worksheet.cell(row=row, column=6).value for row in range(2, 27)] == [
        f"M-{index + 1:02d}" for index in range(25)
    ]
    workbook.close()

    with create_session(settings) as session:
        rows = session.query(Entry).order_by(Entry.id.asc()).all()
        assert [row.excel_row_number for row in rows] == list(range(2, 27))
        assert {row.sync_status for row in rows} == {"synced"}


def test_bulk_offline_sync_saves_entries_with_one_excel_write(
    client,
    monkeypatch,
    tmp_path,
):
    tour_client_id = "bulk-tour-1"
    records = [
        {
            "type": "tour_context",
            "client_request_id": tour_client_id,
            "client_recorded_at": "2026-06-08T09:20:00+03:00",
            "body": {
                "client_request_id": tour_client_id,
                "client_recorded_at": "2026-06-08T09:20:00+03:00",
                "ambient_temp": "24,5",
                "production_engineer": "Engineer",
                "shift_chief": "Selman",
            },
        }
    ]
    for index in range(25):
        entry_client_id = f"bulk-entry-{index + 1:02d}"
        records.append(
            {
                "type": "entry",
                "client_request_id": entry_client_id,
                "depends_on_client_request_id": tour_client_id,
                "client_recorded_at": "2026-06-08T09:25:00+03:00",
                "body": {
                    "client_request_id": entry_client_id,
                    "client_recorded_at": "2026-06-08T09:25:00+03:00",
                    "payload_schema_version": 2,
                    "payload": {
                        "col_f": f"M-{index + 1:02d}",
                        "col_h": f"WO-{index + 1:02d}",
                    },
                },
            }
        )

    load_count = 0
    save_count = 0
    backup_count = 0
    real_load_workbook = load_workbook
    real_save = OpenpyxlWorkbook.save
    real_copyfile = shutil.copyfile

    def counted_load_workbook(*args, **kwargs):
        nonlocal load_count
        load_count += 1
        return real_load_workbook(*args, **kwargs)

    def counted_save(self, filename):
        nonlocal save_count
        save_count += 1
        return real_save(self, filename)

    def counted_copyfile(source, destination):
        nonlocal backup_count
        backup_count += 1
        return real_copyfile(source, destination)

    monkeypatch.setattr(
        "app.modules.process_entry.workbook_io.load_workbook",
        counted_load_workbook,
    )
    monkeypatch.setattr(OpenpyxlWorkbook, "save", counted_save)
    monkeypatch.setattr(
        "app.modules.process_entry.workbook_io.shutil.copyfile",
        counted_copyfile,
    )

    first_response = client.post(
        "/api/offline/bulk-sync",
        json={"records": records, "sync_excel": True},
    )
    replay_response = client.post(
        "/api/offline/bulk-sync",
        json={"records": records, "sync_excel": True},
    )

    assert first_response.status_code == 200
    assert replay_response.status_code == 200
    first_payload = first_response.json()
    replay_payload = replay_response.json()
    assert first_payload["saved_count"] == 26
    assert first_payload["synced_count"] == 25
    assert first_payload["failed_count"] == 0
    assert first_payload["excel_pending"] is False
    assert load_count == 1
    assert save_count == 1
    assert backup_count == 1
    assert all(record["idempotent_replay"] for record in replay_payload["records"])

    workbook = load_workbook(tmp_path / "process.xlsx")
    worksheet = workbook["PROSES 2026"]
    assert [worksheet.cell(row=row, column=6).value for row in range(2, 27)] == [
        f"M-{index + 1:02d}" for index in range(25)
    ]
    assert worksheet.cell(row=27, column=6).value is None
    workbook.close()

    settings = Settings(
        excel_path=str(tmp_path / "process.xlsx"),
        app_pin="1234",
        sqlite_path=str(tmp_path / "process_entries.sqlite3"),
        backup_dir=str(tmp_path / "backups"),
    )
    with create_session(settings) as session:
        assert session.query(Entry).count() == 25
        assert session.query(Entry).filter(Entry.sync_status == "synced").count() == 25
        assert {entry.tour_context_id for entry in session.query(Entry).all()} == {
            first_payload["records"][0]["server_id"]
        }


def test_bulk_offline_sync_excel_unavailable_keeps_sqlite_records(
    monkeypatch,
    tmp_path,
):
    workbook_path = tmp_path / "missing.xlsx"
    _freeze_request_time(monkeypatch)
    monkeypatch.setenv("EXCEL_PATH", str(workbook_path))
    monkeypatch.setenv("APP_PIN", "1234")
    monkeypatch.setenv("SESSION_SECRET", "test-session-secret")
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "process_entries.sqlite3"))
    monkeypatch.setenv("BACKUP_DIR", str(tmp_path / "backups"))

    records = [
        {
            "type": "tour_context",
            "client_request_id": "bulk-missing-tour",
            "body": {
                "client_request_id": "bulk-missing-tour",
                "ambient_temp": "24,5",
                "production_engineer": "Engineer",
                "shift_chief": "Selman",
            },
        },
        {
            "type": "entry",
            "client_request_id": "bulk-missing-entry",
            "depends_on_client_request_id": "bulk-missing-tour",
                "body": {
                    "client_request_id": "bulk-missing-entry",
                    "payload_schema_version": 2,
                    "payload": {
                        "col_f": "M-01",
                        "col_h": "WO-1",
                },
            },
        },
    ]

    with TestClient(create_app()) as test_client:
        login_response = test_client.post("/api/login", json={"pin": "1234"})
        assert login_response.status_code == 200
        response = test_client.post(
            "/api/offline/bulk-sync",
            json={"records": records, "sync_excel": True},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["saved_count"] == 2
    assert payload["synced_count"] == 0
    assert payload["failed_count"] == 1
    assert payload["excel_pending"] is True
    assert "bulunamad" in payload["excel_error"]

    settings = Settings(
        excel_path=str(workbook_path),
        app_pin="1234",
        sqlite_path=str(tmp_path / "process_entries.sqlite3"),
        backup_dir=str(tmp_path / "backups"),
    )
    with create_session(settings) as session:
        entry = session.query(Entry).one()
        assert entry.sync_status == "pending_excel"
        assert entry.excel_row_number is None
        assert entry.last_error == payload["excel_error"]
