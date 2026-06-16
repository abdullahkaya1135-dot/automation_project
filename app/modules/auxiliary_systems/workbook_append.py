from collections.abc import Mapping, Sequence
from typing import Any

from openpyxl.workbook.workbook import Workbook
from openpyxl.worksheet.worksheet import Worksheet

from ...config import Settings
from ..process_entry.workbook_io import WorkbookLockedError, WorkbookSaveError
from .fields import AUXILIARY_HEADER_ROW
from .row_builder import build_auxiliary_rows
from .workbook_io import (
    copy_auxiliary_row_format,
    create_auxiliary_workbook_backup,
    detect_auxiliary_last_value_row,
    open_auxiliary_target_sheet,
    validate_auxiliary_headers,
)
from .workbook_matching import (
    find_matching_auxiliary_block as find_matching_auxiliary_block,
)
from .workbook_matching import find_matching_auxiliary_block_in_worksheet
from .workbook_types import AuxiliaryBlockResult, AuxiliaryWorkbookSubmission


def append_auxiliary_systems_unlocked(
    settings: Settings,
    payload: Mapping[str, Any] | object,
    recorded_date: Any,
) -> tuple[int, int]:
    result = append_auxiliary_submissions_unlocked(
        settings,
        [
            AuxiliaryWorkbookSubmission(
                payload=payload,
                recorded_date=recorded_date,
            )
        ],
        reuse_existing_matches=False,
    )[0]
    return result.start_row, result.end_row


def append_auxiliary_submissions_unlocked(
    settings: Settings,
    submissions: Sequence[AuxiliaryWorkbookSubmission],
    *,
    reuse_existing_matches: bool,
) -> list[AuxiliaryBlockResult]:
    workbook: Workbook | None = None
    try:
        workbook, worksheet = open_auxiliary_target_sheet(
            settings,
            read_only=False,
            data_only=False,
        )
        validate_auxiliary_headers(worksheet)

        last_value_row = detect_auxiliary_last_value_row(worksheet)
        expected_blocks = [
            build_auxiliary_rows(submission.payload, submission.recorded_date)
            for submission in submissions
        ]
        results: list[AuxiliaryBlockResult | None] = [None] * len(submissions)
        pending_indexes = set(range(len(submissions)))

        if reuse_existing_matches:
            used_start_rows: set[int] = set()
            for index in tuple(pending_indexes):
                existing_block = find_matching_auxiliary_block_in_worksheet(
                    worksheet,
                    expected_blocks[index],
                    last_value_row,
                    used_start_rows,
                )
                if existing_block is None:
                    continue
                start_row, end_row = existing_block
                used_start_rows.add(start_row)
                results[index] = AuxiliaryBlockResult(
                    submission_id=submissions[index].submission_id,
                    start_row=start_row,
                    end_row=end_row,
                )
                pending_indexes.remove(index)

        if pending_indexes:
            create_auxiliary_workbook_backup(settings)
            target_start_row = max(AUXILIARY_HEADER_ROW, last_value_row) + 1
            for index in sorted(pending_indexes):
                rows = expected_blocks[index]
                write_auxiliary_block(worksheet, target_start_row, rows)
                results[index] = AuxiliaryBlockResult(
                    submission_id=submissions[index].submission_id,
                    start_row=target_start_row,
                    end_row=target_start_row + len(rows) - 1,
                )
                target_start_row += len(rows)

            save_auxiliary_workbook(workbook, settings)

        return [result for result in results if result is not None]
    finally:
        if workbook is not None:
            workbook.close()


def write_auxiliary_block(
    worksheet: Worksheet,
    target_start_row: int,
    rows: list[list[Any]],
) -> None:
    template_start_row = target_start_row - len(rows)
    for row_offset, row_values in enumerate(rows):
        target_row = target_start_row + row_offset
        template_row = template_start_row + row_offset
        if template_row > AUXILIARY_HEADER_ROW:
            copy_auxiliary_row_format(worksheet, template_row, target_row)
        for column_index, value in enumerate(row_values, start=1):
            worksheet.cell(row=target_row, column=column_index, value=value)


def save_auxiliary_workbook(workbook: Workbook, settings: Settings) -> None:
    try:
        workbook.save(settings.auxiliary_systems_target_path)
    except PermissionError as exc:
        raise WorkbookLockedError(
            "Yardımcı sistemler çalışma kitabı kilitli olabileceği için "
            f"kaydedilemedi: {settings.auxiliary_systems_target_path}"
        ) from exc
    except OSError as exc:
        raise WorkbookSaveError(
            "Yardımcı sistemler çalışma kitabı kaydedilemedi: "
            f"{settings.auxiliary_systems_target_path} ({exc})"
        ) from exc
