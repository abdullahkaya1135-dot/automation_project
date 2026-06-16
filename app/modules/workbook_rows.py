from openpyxl.worksheet.worksheet import Worksheet

from ..shared.workbook_utils import has_meaningful_value


def detect_last_value_row_in_columns(worksheet: Worksheet, max_column: int) -> int:
    cells = getattr(worksheet, "_cells", None)
    if cells is None:
        last_row = 0
        for row_index, row in enumerate(
            worksheet.iter_rows(
                min_row=1,
                max_col=max_column,
                values_only=True,
            ),
            start=1,
        ):
            if any(has_meaningful_value(value) for value in row):
                last_row = row_index
        return last_row

    if not cells:
        return 0

    last_row = 0
    for (row_index, column_index), cell in cells.items():
        if column_index > max_column:
            continue
        if has_meaningful_value(cell.value):
            last_row = max(last_row, row_index)
    return last_row
