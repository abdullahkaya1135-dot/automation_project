from collections.abc import Mapping, Sequence
from typing import Any

from ...config import Settings
from ...shared.excel_write_lock import serialized_excel_write
from .fields import (
    AUXILIARY_CHECK_FIELD_NAMES as AUXILIARY_CHECK_FIELD_NAMES,
)
from .fields import (
    AUXILIARY_COLUMN_COUNT,
    AUXILIARY_HEADER_ROW,
)
from .fields import (
    AUXILIARY_COLUMN_LETTERS as AUXILIARY_COLUMN_LETTERS,
)
from .fields import (
    AUXILIARY_FIELD_NAMES as AUXILIARY_FIELD_NAMES,
)
from .fields import (
    AUXILIARY_HEADER_KEYWORDS_BY_COLUMN as AUXILIARY_HEADER_KEYWORDS_BY_COLUMN,
)
from .fields import (
    AUXILIARY_MEASUREMENT_FIELD_NAMES as AUXILIARY_MEASUREMENT_FIELD_NAMES,
)
from .fields import (
    AUXILIARY_ROW_SPECS as AUXILIARY_ROW_SPECS,
)
from .fields import (
    AuxiliaryRowSpec as AuxiliaryRowSpec,
)
from .row_builder import build_auxiliary_rows
from .row_builder import date_text as date_text
from .row_builder import normalize_auxiliary_value as normalize_auxiliary_value
from .workbook_append import (
    append_auxiliary_submissions_unlocked,
    append_auxiliary_systems_unlocked,
)
from .workbook_io import AuxiliarySystemsStatus as AuxiliarySystemsStatus
from .workbook_io import (
    check_auxiliary_systems_reachable as check_auxiliary_systems_reachable,
)
from .workbook_io import (
    create_auxiliary_workbook_backup as create_auxiliary_workbook_backup,
)
from .workbook_io import (
    detect_auxiliary_last_value_row as detect_auxiliary_last_value_row,
)
from .workbook_io import open_auxiliary_target_sheet as open_auxiliary_target_sheet
from .workbook_io import read_auxiliary_headers as read_auxiliary_headers
from .workbook_io import validate_auxiliary_headers as validate_auxiliary_headers
from .workbook_matching import (
    find_matching_auxiliary_block,
)
from .workbook_types import AuxiliaryBlockResult as AuxiliaryBlockResult
from .workbook_types import (
    AuxiliaryWorkbookSubmission as AuxiliaryWorkbookSubmission,
)


def append_auxiliary_systems_to_workbook(
    settings: Settings,
    payload: Mapping[str, Any] | object,
    recorded_date: Any,
    *,
    reuse_existing_match: bool = False,
) -> tuple[int, int]:
    with serialized_excel_write("auxiliary_systems_append"):
        if reuse_existing_match:
            existing_block = find_matching_auxiliary_block(
                settings,
                payload,
                recorded_date,
            )
            if existing_block is not None:
                return existing_block
        return append_auxiliary_systems_unlocked(
            settings,
            payload,
            recorded_date,
        )


def append_auxiliary_submissions_to_workbook(
    settings: Settings,
    submissions: Sequence[AuxiliaryWorkbookSubmission],
    *,
    reuse_existing_matches: bool = False,
) -> list[AuxiliaryBlockResult]:
    if not submissions:
        return []

    with serialized_excel_write("auxiliary_systems_batch_append"):
        return append_auxiliary_submissions_unlocked(
            settings,
            submissions,
            reuse_existing_matches=reuse_existing_matches,
        )


__all__ = [
    "AUXILIARY_CHECK_FIELD_NAMES",
    "AUXILIARY_COLUMN_COUNT",
    "AUXILIARY_COLUMN_LETTERS",
    "AUXILIARY_FIELD_NAMES",
    "AUXILIARY_HEADER_KEYWORDS_BY_COLUMN",
    "AUXILIARY_HEADER_ROW",
    "AUXILIARY_MEASUREMENT_FIELD_NAMES",
    "AUXILIARY_ROW_SPECS",
    "AuxiliaryBlockResult",
    "AuxiliaryRowSpec",
    "AuxiliarySystemsStatus",
    "AuxiliaryWorkbookSubmission",
    "append_auxiliary_submissions_to_workbook",
    "append_auxiliary_systems_to_workbook",
    "build_auxiliary_rows",
    "check_auxiliary_systems_reachable",
    "create_auxiliary_workbook_backup",
    "date_text",
    "detect_auxiliary_last_value_row",
    "normalize_auxiliary_value",
    "open_auxiliary_target_sheet",
    "read_auxiliary_headers",
    "validate_auxiliary_headers",
]
