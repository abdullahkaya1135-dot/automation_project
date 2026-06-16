import re
from collections.abc import Mapping
from datetime import date as Date
from datetime import datetime
from typing import Any

from ...shared.workbook_utils import clean_text
from .fields import AUXILIARY_COLUMN_LETTERS, AUXILIARY_ROW_SPECS

DECIMAL_NUMBER_PATTERN = re.compile(r"^[+-]?\d+(?:[,.]\d+)?$")


def normalize_auxiliary_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int | float):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        if DECIMAL_NUMBER_PATTERN.fullmatch(stripped):
            normalized = stripped.replace(",", ".")
            number = float(normalized)
            if number.is_integer() and "." not in normalized:
                return int(number)
            return number
        return stripped
    return value


def _normalized_existing_auxiliary_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return value


def _auxiliary_values_match(existing: Any, expected: Any) -> bool:
    return _normalized_existing_auxiliary_value(existing) == expected


def auxiliary_row_matches_expected(
    existing_values: tuple[Any, ...],
    expected_values: list[Any],
) -> bool:
    return all(
        _auxiliary_values_match(existing, expected)
        for existing, expected in zip(existing_values, expected_values, strict=True)
    )


def date_text(value: Any) -> str:
    if isinstance(value, datetime):
        return value.strftime("%d.%m.%Y")
    if isinstance(value, Date):
        return value.strftime("%d.%m.%Y")
    text = clean_text(value)
    if not text:
        raise ValueError("tarih zorunludur.")
    try:
        return datetime.fromisoformat(text).strftime("%d.%m.%Y")
    except ValueError:
        return text


def _payload_value(payload: Mapping[str, Any] | object, field_name: str) -> Any:
    if isinstance(payload, Mapping):
        return payload.get(field_name)
    return getattr(payload, field_name, None)


def build_auxiliary_rows(
    payload: Mapping[str, Any] | object,
    recorded_date: Any,
) -> list[list[Any]]:
    rows: list[list[Any]] = []
    recorded_date_text = date_text(recorded_date)
    for spec in AUXILIARY_ROW_SPECS:
        row_values = [
            recorded_date_text,
            spec["machine"],
            None,
            None,
            None,
            None,
            None,
            None,
            None,
        ]
        fields = spec["fields"]
        for column_letter, field_name in fields.items():
            column_index = AUXILIARY_COLUMN_LETTERS.index(column_letter)
            row_values[column_index] = normalize_auxiliary_value(
                _payload_value(payload, field_name)
            )
        rows.append(row_values)
    return rows
