import re
from collections.abc import Mapping
from typing import Any

ENTRY_FIELD_NAMES = tuple(f"col_{letter}" for letter in "abcdefghijklmnopqrstuvwxy")
LEGACY_ENTRY_FIELD_NAMES = tuple(f"col_{letter}" for letter in "abcdefghijklmnopq")
ENTRY_PAYLOAD_SCHEMA_VERSION = 2

EXCEL_FIELD_NAME_BY_COLUMN = {
    letter.upper(): f"col_{letter}"
    for letter in "abcdefghijklmnopqrstuvwxy"
}
LEGACY_TO_CANONICAL_FIELD_NAMES = {
    "col_a": "col_a",
    "col_b": "col_b",
    "col_c": "col_c",
    "col_d": "col_d",
    "col_e": "col_e",
    "col_f": "col_f",
    "col_g": "col_h",
    "col_h": "col_j",
    "col_i": "col_k",
    "col_j": "col_l",
    "col_k": "col_m",
    "col_l": "col_n",
    "col_m": "col_o",
    "col_n": "col_p",
    "col_o": "col_q",
    "col_p": "col_x",
    "col_q": "col_y",
}

FIRST_SECTION_EXCLUDED_FIELDS = frozenset(
    f"col_{letter}" for letter in "rstuvw"
)
SECOND_SECTION_EXCLUDED_FIELDS = frozenset(
    f"col_{letter}" for letter in "opq"
)
MACHINE_CODE_PATTERN = re.compile(r"\d+")


def _clean_text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def machine_code(value: Any) -> int | None:
    match = MACHINE_CODE_PATTERN.search(_clean_text(value))
    if match is None:
        return None
    return int(match.group(0))


def is_first_section_machine(value: Any) -> bool:
    code = machine_code(value)
    return code == 271 or (code is not None and 100 <= code <= 199)


def is_second_section_machine(value: Any) -> bool:
    code = machine_code(value)
    return code is not None and code != 271 and 200 <= code <= 599


def excluded_fields_for_machine(value: Any) -> frozenset[str]:
    if is_second_section_machine(value):
        return SECOND_SECTION_EXCLUDED_FIELDS
    return FIRST_SECTION_EXCLUDED_FIELDS


def blank_excluded_section_fields(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    canonical_payload = {
        field_name: payload.get(field_name)
        for field_name in ENTRY_FIELD_NAMES
    }
    for field_name in excluded_fields_for_machine(canonical_payload.get("col_f")):
        canonical_payload[field_name] = None
    return canonical_payload


def canonicalize_legacy_entry_payload(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    canonical_payload = {field_name: None for field_name in ENTRY_FIELD_NAMES}
    for old_field_name, new_field_name in LEGACY_TO_CANONICAL_FIELD_NAMES.items():
        canonical_payload[new_field_name] = payload.get(old_field_name)
    return canonical_payload
