from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from openpyxl.workbook.workbook import Workbook
from openpyxl.worksheet.worksheet import Worksheet

from ...config import Settings
from .excel_mapper import build_excel_row
from .excel_schema import HEADER_ROW
from .excel_values import entry_id
from .workbook_io import (
    WorkbookLockedError,
    WorkbookSaveError,
    create_workbook_backup,
    detect_last_value_row,
    open_workbook_sheet,
    validate_headers,
)
from .workbook_matching import match_existing_entry_rows_in_worksheet


@dataclass(frozen=True)
class ExcelRowResult:
    entry_id: int | None
    row_number: int


def append_entry_to_workbook_unlocked(
    settings: Settings,
    payload: Mapping[str, Any] | object,
) -> int:
    return append_entries_to_workbook_unlocked(
        settings,
        [payload],
        reuse_existing_matches=False,
    )[0].row_number


def append_entries_to_workbook_unlocked(
    settings: Settings,
    payloads: Sequence[Mapping[str, Any] | object],
    *,
    reuse_existing_matches: bool,
) -> list[ExcelRowResult]:
    workbook: Workbook | None = None
    try:
        workbook, worksheet = open_workbook_sheet(
            settings,
            read_only=False,
            data_only=False,
        )
        validate_headers(worksheet)

        last_value_row = detect_last_value_row(worksheet)
        expected_rows = [build_excel_row(payload) for payload in payloads]
        results: list[ExcelRowResult | None] = [None] * len(payloads)
        pending_indexes = set(range(len(payloads)))

        if reuse_existing_matches:
            matched_rows = match_existing_entry_rows_in_worksheet(
                worksheet,
                expected_rows,
                last_value_row,
                pending_indexes,
            )
            for index, row_number in matched_rows.items():
                results[index] = ExcelRowResult(
                    entry_id=entry_id(payloads[index]),
                    row_number=row_number,
                )
                pending_indexes.remove(index)

        if pending_indexes:
            target_row = max(HEADER_ROW, last_value_row) + 1
            create_workbook_backup(settings)
            for index in sorted(pending_indexes):
                row_number = target_row
                write_process_entry_row(worksheet, row_number, expected_rows[index])
                results[index] = ExcelRowResult(
                    entry_id=entry_id(payloads[index]),
                    row_number=row_number,
                )
                target_row += 1

            save_process_workbook(workbook, settings)

        return [result for result in results if result is not None]
    finally:
        if workbook is not None:
            workbook.close()


def write_process_entry_row(
    worksheet: Worksheet,
    row_number: int,
    values: list[Any],
) -> None:
    for column_index, value in enumerate(values, start=1):
        worksheet.cell(row=row_number, column=column_index, value=value)


def save_process_workbook(workbook: Workbook, settings: Settings) -> None:
    try:
        workbook.save(settings.excel_path)
    except PermissionError as exc:
        raise WorkbookLockedError(
            f"Çalışma kitabı kilitli olabileceği için kaydedilemedi: {settings.excel_path}"
        ) from exc
    except OSError as exc:
        raise WorkbookSaveError(
            f"Çalışma kitabı kaydedilemedi: {settings.excel_path} ({exc})"
        ) from exc


__all__ = [
    "ExcelRowResult",
    "append_entries_to_workbook_unlocked",
    "append_entry_to_workbook_unlocked",
    "save_process_workbook",
    "write_process_entry_row",
]
