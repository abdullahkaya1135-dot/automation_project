from collections.abc import Mapping
from typing import Any

from openpyxl.workbook.workbook import Workbook
from openpyxl.worksheet.worksheet import Worksheet

from ...config import Settings
from .fields import AUXILIARY_COLUMN_COUNT, AUXILIARY_HEADER_ROW
from .row_builder import auxiliary_row_matches_expected, build_auxiliary_rows
from .workbook_io import (
    detect_auxiliary_last_value_row,
    open_auxiliary_target_sheet,
    validate_auxiliary_headers,
)


def find_matching_auxiliary_block(
    settings: Settings,
    payload: Mapping[str, Any] | object,
    recorded_date: Any,
) -> tuple[int, int] | None:
    workbook: Workbook | None = None
    try:
        workbook, worksheet = open_auxiliary_target_sheet(settings)
        validate_auxiliary_headers(worksheet)
        last_value_row = detect_auxiliary_last_value_row(worksheet)
        expected_rows = build_auxiliary_rows(payload, recorded_date)
        return find_matching_auxiliary_block_in_worksheet(
            worksheet,
            expected_rows,
            last_value_row,
            used_start_rows=set(),
        )
    finally:
        if workbook is not None:
            workbook.close()


def find_matching_auxiliary_block_in_worksheet(
    worksheet: Worksheet,
    expected_rows: list[list[Any]],
    last_value_row: int,
    used_start_rows: set[int],
) -> tuple[int, int] | None:
    expected_count = len(expected_rows)
    if last_value_row < AUXILIARY_HEADER_ROW + expected_count:
        return None

    max_start_row = last_value_row - expected_count + 1
    for start_row in range(AUXILIARY_HEADER_ROW + 1, max_start_row + 1):
        if start_row in used_start_rows:
            continue
        if auxiliary_block_matches_expected(worksheet, start_row, expected_rows):
            return start_row, start_row + expected_count - 1
    return None


def auxiliary_block_matches_expected(
    worksheet: Worksheet,
    start_row: int,
    expected_rows: list[list[Any]],
) -> bool:
    for row_offset, expected_values in enumerate(expected_rows):
        existing_values = next(
            worksheet.iter_rows(
                min_row=start_row + row_offset,
                max_row=start_row + row_offset,
                max_col=AUXILIARY_COLUMN_COUNT,
                values_only=True,
            )
        )
        if not auxiliary_row_matches_expected(existing_values, expected_values):
            return False
    return True


__all__ = [
    "auxiliary_block_matches_expected",
    "find_matching_auxiliary_block",
    "find_matching_auxiliary_block_in_worksheet",
]
