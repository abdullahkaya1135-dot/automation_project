from collections.abc import Iterable, Mapping
from typing import Any

from openpyxl.workbook.workbook import Workbook
from openpyxl.worksheet.worksheet import Worksheet

from ...config import Settings
from .excel_mapper import build_excel_row
from .excel_schema import EXCEL_COLUMN_COUNT, HEADER_ROW
from .workbook_io import (
    detect_last_value_row,
    open_workbook_sheet,
    validate_headers,
)


def normalized_existing_excel_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return value


def excel_values_match(existing: Any, expected: Any) -> bool:
    return normalized_existing_excel_value(existing) == expected


def row_matches_expected(
    existing_values: tuple[Any, ...],
    expected_values: list[Any],
) -> bool:
    return all(
        excel_values_match(existing, expected)
        for existing, expected in zip(existing_values, expected_values, strict=True)
    )


def find_matching_entry_row(
    settings: Settings,
    payload: Mapping[str, Any] | object,
) -> int | None:
    workbook: Workbook | None = None
    try:
        workbook, worksheet = open_workbook_sheet(settings)
        validate_headers(worksheet)
        last_value_row = detect_last_value_row(worksheet)
        expected_values = build_excel_row(payload)
        return find_matching_entry_row_in_worksheet(
            worksheet,
            expected_values,
            last_value_row,
        )
    finally:
        if workbook is not None:
            workbook.close()


def find_matching_entry_row_in_worksheet(
    worksheet: Worksheet,
    expected_values: list[Any],
    last_value_row: int,
) -> int | None:
    if last_value_row <= HEADER_ROW:
        return None

    for row_number, values in existing_process_rows(worksheet, last_value_row):
        if row_matches_expected(values, expected_values):
            return row_number
    return None


def match_existing_entry_rows_in_worksheet(
    worksheet: Worksheet,
    expected_rows: list[list[Any]],
    last_value_row: int,
    pending_indexes: Iterable[int],
) -> dict[int, int]:
    pending = set(pending_indexes)
    if not pending or last_value_row <= HEADER_ROW:
        return {}

    matched_rows: dict[int, int] = {}
    for row_number, values in existing_process_rows(worksheet, last_value_row):
        for index in tuple(pending):
            if row_matches_expected(values, expected_rows[index]):
                matched_rows[index] = row_number
                pending.remove(index)
                break
        if not pending:
            break
    return matched_rows


def existing_process_rows(
    worksheet: Worksheet,
    last_value_row: int,
) -> Iterable[tuple[int, tuple[Any, ...]]]:
    return enumerate(
        worksheet.iter_rows(
            min_row=HEADER_ROW + 1,
            max_row=last_value_row,
            max_col=EXCEL_COLUMN_COUNT,
            values_only=True,
        ),
        start=HEADER_ROW + 1,
    )


__all__ = [
    "excel_values_match",
    "existing_process_rows",
    "find_matching_entry_row",
    "find_matching_entry_row_in_worksheet",
    "match_existing_entry_rows_in_worksheet",
    "normalized_existing_excel_value",
    "row_matches_expected",
]
