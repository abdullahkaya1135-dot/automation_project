from collections.abc import Mapping, Sequence
from typing import Any

from ...config import Settings
from ...shared.excel_write_lock import serialized_excel_write
from .excel_values import normalize_excel_value as _normalize_excel_value
from .workbook_append import ExcelRowResult as ExcelRowResult
from .workbook_append import (
    append_entries_to_workbook_unlocked,
    append_entry_to_workbook_unlocked,
)
from .workbook_matching import find_matching_entry_row


def normalize_excel_value(value: Any, column_letter: str) -> Any:
    return _normalize_excel_value(value, column_letter)


def append_entry_to_workbook(
    settings: Settings,
    payload: Mapping[str, Any] | object,
    *,
    reuse_existing_match: bool = False,
) -> int:
    with serialized_excel_write("process_entry_append"):
        if reuse_existing_match:
            existing_row = find_matching_entry_row(settings, payload)
            if existing_row is not None:
                return existing_row
        return append_entry_to_workbook_unlocked(settings, payload)


def append_entries_to_workbook(
    settings: Settings,
    payloads: Sequence[Mapping[str, Any] | object],
    *,
    reuse_existing_matches: bool = False,
) -> list[ExcelRowResult]:
    if not payloads:
        return []

    with serialized_excel_write("process_entry_batch_append"):
        return append_entries_to_workbook_unlocked(
            settings,
            payloads,
            reuse_existing_matches=reuse_existing_matches,
        )


__all__ = [
    "ExcelRowResult",
    "append_entries_to_workbook",
    "append_entry_to_workbook",
    "normalize_excel_value",
]
