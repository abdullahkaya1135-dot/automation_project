from datetime import date
from pathlib import Path

import pytest
from openpyxl import Workbook, load_workbook

from app.config import Settings
from app.modules.reports.cycle_report_service import (
    NoTodayRowsError,
    create_cycle_report,
    normalize_machine_group,
    parse_part_description,
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
REPORT_HEADERS = [
    "Makine Adı",
    "Makine No.",
    "Ağız",
    "Gramaj",
    "Toplam Göz",
    "Çalışan Göz",
    "Gerçekleşen Çevrim Süresi",
    "Optimum Çevrim Süresi",
    "Kontrol Durumu",
]


def _create_process_workbook(path: Path, rows: list[list[object]]) -> None:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "PROSES 2026"
    worksheet.append(HEADERS)
    for row in rows:
        worksheet.append(row)
    workbook.save(path)
    workbook.close()


def _process_row(
    day: str,
    machine_no: object,
    work_order: object,
    total_cavity: object,
    active_cavity: object,
    cycle_time: object,
) -> list[object]:
    row: list[object] = [None] * 25
    row[0] = day
    row[5] = machine_no
    row[7] = work_order
    row[9] = total_cavity
    row[10] = active_cavity
    row[11] = cycle_time
    return row


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
    worksheet.append([174, "DPH70", 28, 35, None, None, "14", None])
    worksheet.append([None, None, None, 40, None, None, "16", None])
    worksheet.merge_cells("A2:A3")
    worksheet.merge_cells("B2:B3")
    worksheet.merge_cells("C2:C3")
    worksheet.append([161, "PF 6/2", 28, 45, None, None, "24", None])
    worksheet.append([162, "PF 6/2", 28, 45, None, None, "21", None])
    workbook.save(path)
    workbook.close()


def _ifs_operations() -> list[dict[str, object]]:
    return [
        {
            "OrderNo": "2668",
            "PreferredResourceId": "175",
            "WorkCenterNo": "70DPH",
            "PartNoDesc": "PET0207-01 750ML SEFFAF SEFFAF 28MM YIVLI 35GR",
        },
        {
            "OrderNo": "PF-ORDER",
            "PreferredResourceId": "162",
            "WorkCenterNo": "PF-6",
            "PartNoDesc": "PET0001-01 400ML SEFFAF 28MM YIVLI 45GR",
        },
    ]


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        excel_path=str(tmp_path / "process.xlsx"),
        app_pin="1234",
        sqlite_path=str(tmp_path / "process_entries.sqlite3"),
        backup_dir=str(tmp_path / "backups"),
        cycle_table_path=str(tmp_path / "cycle.xlsx"),
        report_output_dir=str(tmp_path / "reports"),
    )


def test_parse_part_description_extracts_neck_and_gram_values():
    assert parse_part_description(
        "ENJ0057-01 KAPAK SEFFAF SARI 44MM CAKMA 6GR"
    ) == (44, 6)
    assert parse_part_description(
        "IBM0008-01 66ML OPAK BEYAZ 18MM CAKMA 9,5GR (SEA)"
    ) == (18, pytest.approx(9.5))


def test_normalize_machine_group_aliases():
    assert normalize_machine_group("70DPH") == "DPH70"
    assert normalize_machine_group("50MB2") == "50MB"
    assert normalize_machine_group("PF-6") == "PF62"
    assert normalize_machine_group("PF-8") == "PF84"
    assert normalize_machine_group("12M1") == "12M"


def test_create_cycle_report_matches_sources_and_uses_machine_tiebreaker(
    tmp_path,
    monkeypatch,
):
    async def fake_fetch_pet_ongoing_operations(_settings):
        return _ifs_operations()

    monkeypatch.setattr(
        "app.modules.reports.cycle_report_service.fetch_pet_ongoing_operations",
        fake_fetch_pet_ongoing_operations,
    )
    _create_process_workbook(
        tmp_path / "process.xlsx",
        [
            _process_row("09.06.2026", 175, 2668, 3, 2, 213),
            _process_row("09.06.2026", 162, "PF-ORDER", 6, 6, "23,1"),
        ],
    )
    _create_cycle_table(tmp_path / "cycle.xlsx")

    result = create_cycle_report(_settings(tmp_path), date(2026, 6, 9))

    assert result.row_count == 2
    assert result.matched_count == 2
    assert result.warning_count == 0
    assert result.output_path.exists()

    workbook = load_workbook(result.output_path)
    worksheet = workbook["Çevrim Kontrol"]
    assert [cell.value for cell in worksheet[1]] == REPORT_HEADERS
    assert [cell.value for cell in worksheet[2]] == [
        "70DPH",
        "175",
        28,
        35,
        3,
        2,
        213,
        14,
        "Kontrol Edilecek",
    ]
    assert [cell.value for cell in worksheet[3]] == [
        "PF-6",
        "162",
        28,
        45,
        6,
        6,
        23.1,
        21,
        "Uygun",
    ]
    workbook.close()


def test_create_cycle_report_rejects_no_today_rows_without_output(tmp_path):
    _create_process_workbook(
        tmp_path / "process.xlsx",
        [_process_row("08.06.2026", 175, 2668, 3, 2, 213)],
    )
    _create_cycle_table(tmp_path / "cycle.xlsx")

    with pytest.raises(NoTodayRowsError):
        create_cycle_report(_settings(tmp_path), date(2026, 6, 9))

    assert not (tmp_path / "reports").exists()
