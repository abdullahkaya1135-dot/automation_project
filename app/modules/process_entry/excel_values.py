import re
from collections.abc import Mapping
from typing import Any

from .excel_schema import NUMERIC_COLUMN_LETTERS

DECIMAL_NUMBER_PATTERN = re.compile(r"^[+-]?\d+(?:[,.]\d+)?$")
HYPHEN_RANGE_PATTERN = re.compile(r"\d\s*-\s*\d")


def payload_value(payload: Mapping[str, Any] | object, field_name: str) -> Any:
    if isinstance(payload, Mapping):
        return payload.get(field_name)
    return getattr(payload, field_name, None)


def normalize_excel_value(value: Any, column_letter: str) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        if HYPHEN_RANGE_PATTERN.search(stripped):
            return stripped
        if (
            column_letter in NUMERIC_COLUMN_LETTERS
            and DECIMAL_NUMBER_PATTERN.fullmatch(stripped)
        ):
            normalized = stripped.replace(",", ".")
            number = float(normalized)
            if number.is_integer() and "." not in normalized:
                return int(number)
            return number
        return stripped
    return value


def entry_id(payload: Mapping[str, Any] | object) -> int | None:
    raw_id = payload.get("id") if isinstance(payload, Mapping) else getattr(payload, "id", None)
    if isinstance(raw_id, int):
        return raw_id
    return None


__all__ = [
    "DECIMAL_NUMBER_PATTERN",
    "HYPHEN_RANGE_PATTERN",
    "entry_id",
    "normalize_excel_value",
    "payload_value",
]
