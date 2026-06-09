from pathlib import Path

import pytest
from openpyxl import Workbook, load_workbook
from openpyxl.styles import PatternFill
from openpyxl.workbook.workbook import Workbook as OpenpyxlWorkbook

from app.config import Settings
from app.excel_service import (
    WorkbookLockedError,
    WorkbookMissingError,
    WorkbookPermissionError,
    WorkbookStructureError,
    append_entry_to_workbook,
    check_excel_reachable,
    detect_last_value_row,
    normalize_excel_value,
    validate_headers,
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


def _create_workbook(path: Path, *, last_data_row: int = 1725) -> None:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "PROSES 2026"
    worksheet.append(HEADERS)
    worksheet.cell(row=last_data_row, column=1, value="existing")
    worksheet.cell(row=1_048_506, column=25).fill = PatternFill(
        fill_type="solid",
        fgColor="FFFF00",
    )
    workbook.save(path)
    workbook.close()


def _settings(workbook_path: Path, tmp_path: Path, *, keep_count: int = 20) -> Settings:
    return Settings(
        excel_path=str(workbook_path),
        app_pin="1234",
        sqlite_path=str(tmp_path / "process_entries.sqlite3"),
        backup_dir=str(tmp_path / "backups"),
        backup_keep_count=keep_count,
    )


def _payload() -> dict[str, str]:
    return {
        f"col_{letter}": f"value-{letter}"
        for letter in "abcdefghijklmnopq"
    } | {
        "col_a": "2026-06-08",
        "col_b": "24,5",
        "col_f": "M-01",
        "col_g": "001234",
        "col_h": "16",
        "col_i": "12",
        "col_j": "12.5",
        "col_p": "180-190",
        "col_q": "",
    }


def test_detect_last_value_row_ignores_formatting_only_rows(tmp_path):
    workbook_path = tmp_path / "process.xlsx"
    _create_workbook(workbook_path)

    workbook = load_workbook(workbook_path)
    worksheet = workbook["PROSES 2026"]

    assert worksheet.max_row == 1_048_506
    assert detect_last_value_row(worksheet) == 1725

    workbook.close()


def test_validate_headers_rejects_changed_workbook_shape(tmp_path):
    workbook_path = tmp_path / "process.xlsx"
    _create_workbook(workbook_path)

    workbook = load_workbook(workbook_path)
    worksheet = workbook["PROSES 2026"]
    worksheet["F1"] = "Unexpected"

    with pytest.raises(WorkbookStructureError):
        validate_headers(worksheet)

    workbook.close()


def test_check_excel_reachable_reports_header_mismatch(tmp_path):
    workbook_path = tmp_path / "process.xlsx"
    _create_workbook(workbook_path)

    workbook = load_workbook(workbook_path)
    worksheet = workbook["PROSES 2026"]
    worksheet["G1"] = "Unexpected"
    workbook.save(workbook_path)
    workbook.close()

    status = check_excel_reachable(_settings(workbook_path, tmp_path))

    assert status.available is False
    assert "A:Y" in status.error


def test_normalize_excel_value_handles_decimal_and_range_text():
    assert normalize_excel_value("24,5", "B") == 24.5
    assert normalize_excel_value("12.5", "L") == 12.5
    assert normalize_excel_value("7", "J") == 7
    assert normalize_excel_value("180-190", "X") == "180-190"
    assert normalize_excel_value("001234", "H") == "001234"
    assert normalize_excel_value("  ", "Y") is None


def test_append_entry_to_workbook_writes_next_real_row_and_creates_backup(tmp_path):
    workbook_path = tmp_path / "process.xlsx"
    _create_workbook(workbook_path)
    settings = _settings(workbook_path, tmp_path)

    row_number = append_entry_to_workbook(settings, _payload())

    assert row_number == 1726
    backup_files = list((tmp_path / "backups").glob("process_*.xlsx"))
    assert len(backup_files) == 1

    workbook = load_workbook(workbook_path)
    worksheet = workbook["PROSES 2026"]
    header_values = [
        worksheet.cell(row=1, column=index).value for index in range(1, 26)
    ]
    row_values = [
        worksheet.cell(row=1726, column=index).value for index in range(1, 26)
    ]
    expected_row_values = [
        "2026-06-08",
        24.5,
        "value-c",
        "value-d",
        "value-e",
        "M-01",
        None,
        "001234",
        None,
        16,
        12,
        12.5,
        "value-k",
        "value-l",
        "value-m",
        "value-n",
        "value-o",
        None,
        None,
        None,
        None,
        None,
        None,
        "180-190",
        None,
    ]
    assert header_values == HEADERS
    assert row_values == expected_row_values
    workbook.close()

    backup = load_workbook(backup_files[0])
    backup_worksheet = backup["PROSES 2026"]
    assert backup_worksheet.cell(row=1726, column=1).value is None
    backup.close()


def test_append_entry_to_workbook_prunes_old_backups(tmp_path):
    workbook_path = tmp_path / "process.xlsx"
    _create_workbook(workbook_path)
    settings = _settings(workbook_path, tmp_path, keep_count=2)

    append_entry_to_workbook(settings, _payload())
    append_entry_to_workbook(settings, _payload())
    append_entry_to_workbook(settings, _payload())

    assert len(list((tmp_path / "backups").glob("process_*.xlsx"))) == 2


def test_append_entry_to_workbook_raises_typed_error_for_missing_file(tmp_path):
    settings = _settings(tmp_path / "missing.xlsx", tmp_path)

    with pytest.raises(WorkbookMissingError):
        append_entry_to_workbook(settings, _payload())


def test_append_entry_to_workbook_raises_typed_error_for_open_permission_denied(
    monkeypatch,
    tmp_path,
):
    settings = _settings(tmp_path / "process.xlsx", tmp_path)

    def raise_permission_error(*_args, **_kwargs):
        raise PermissionError("denied")

    monkeypatch.setattr("app.excel_service.load_workbook", raise_permission_error)

    with pytest.raises(WorkbookPermissionError):
        append_entry_to_workbook(settings, _payload())


def test_append_entry_to_workbook_raises_locked_error_when_save_is_denied(
    monkeypatch,
    tmp_path,
):
    workbook_path = tmp_path / "process.xlsx"
    _create_workbook(workbook_path)
    settings = _settings(workbook_path, tmp_path)

    def raise_permission_error(_workbook, _filename):
        raise PermissionError("locked")

    monkeypatch.setattr(OpenpyxlWorkbook, "save", raise_permission_error)

    with pytest.raises(WorkbookLockedError):
        append_entry_to_workbook(settings, _payload())

    assert len(list((tmp_path / "backups").glob("process_*.xlsx"))) == 1
