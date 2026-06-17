from pathlib import Path

from openpyxl import Workbook

from app.config import Settings
from app.database import create_session, init_db
from app.models import Entry
from app.services.process_excel_import import import_process_excel_to_database

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


def _write_process_workbook(path: Path) -> None:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "PROSES 2026"
    worksheet.append(HEADERS)
    worksheet.append(
        [
            "17.06.2026",
            29,
            "FEVZİ KILNÇ",
            "Selman",
            "08.00-16.00",
            "M-102",
            "Product 102",
            "WO-102",
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
        ]
    )
    worksheet.append(
        [
            "16.06.2026",
            28,
            "BARIŞ ÇETİK",
            "Serkan",
            "16.00-24.00",
            "101",
            "Product 101",
            "WO-101",
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
        ]
    )
    workbook.save(path)
    workbook.close()


def test_import_process_excel_sorts_normalizes_and_skips_duplicates(tmp_path):
    workbook_path = tmp_path / "process.xlsx"
    sqlite_path = tmp_path / "process_entries.sqlite3"
    _write_process_workbook(workbook_path)
    settings = Settings(
        excel_path=str(workbook_path),
        app_pin="1234",
        sqlite_path=str(sqlite_path),
    )
    init_db(settings)

    result = import_process_excel_to_database(settings)
    duplicate_result = import_process_excel_to_database(settings)

    assert result.scanned_rows == 2
    assert result.inserted_rows == 2
    assert result.skipped_duplicates == 0
    assert duplicate_result.inserted_rows == 0
    assert duplicate_result.skipped_duplicates == 2

    with create_session(settings) as session:
        entries = (
            session.query(Entry)
            .order_by(Entry.process_date, Entry.machine_code, Entry.production_engineer_id)
            .all()
        )

    assert [(entry.process_date, entry.machine_code, entry.col_c) for entry in entries] == [
        ("2026-06-16", "101", "Barış Çetik"),
        ("2026-06-17", "102", "Fevzi Kılınç"),
    ]
    assert all(entry.production_engineer_id is not None for entry in entries)
