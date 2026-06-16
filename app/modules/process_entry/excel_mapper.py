from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from ...domain.entry_fields import (
    ENTRY_FIELD_NAMES,
    blank_excluded_section_fields,
)
from .excel_schema import (
    EXCEL_COLUMN_COUNT,
    EXCEL_COLUMN_LETTERS,
    HEADER_KEYWORDS_BY_COLUMN,
    HEADER_ROW,
    NUMERIC_COLUMN_LETTERS,
    PAYLOAD_FIELD_BY_ATTRIBUTE,
    PROCESS_ENTRY_ATTRIBUTE_BY_COLUMN,
)
from .excel_values import (
    DECIMAL_NUMBER_PATTERN,
    HYPHEN_RANGE_PATTERN,
    entry_id,
    normalize_excel_value,
    payload_value,
)


@dataclass(frozen=True)
class ProcessEntryData:
    date: Any = None
    ambient_temp: Any = None
    production_engineer: Any = None
    shift_chief: Any = None
    shift: Any = None
    machine: Any = None
    product: Any = None
    work_order: Any = None
    raw_material: Any = None
    total_cavity_count: Any = None
    active_cavity_count: Any = None
    cycle_time: Any = None
    cooling_time: Any = None
    injection_time: Any = None
    blow_time: Any = None
    conditioner_temp: Any = None
    dryer_temp: Any = None
    injection_pressures: Any = None
    injection_speeds: Any = None
    holding_time: Any = None
    holding_speed: Any = None
    holding_pressure: Any = None
    clamp_force: Any = None
    oven_temps: Any = None
    mold_temps: Any = None

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any] | object) -> ProcessEntryData:
        section_payload = blank_excluded_section_fields(
            {
                field_name: _payload_value(payload, field_name)
                for field_name in ENTRY_FIELD_NAMES
            }
        )
        return cls(
            **{
                attribute: section_payload.get(field_name)
                for attribute, field_name in PAYLOAD_FIELD_BY_ATTRIBUTE.items()
            }
        )

    def as_payload(self) -> dict[str, Any]:
        return {
            field_name: getattr(self, attribute)
            for attribute, field_name in PAYLOAD_FIELD_BY_ATTRIBUTE.items()
        }


def _payload_value(payload: Mapping[str, Any] | object, field_name: str) -> Any:
    return payload_value(payload, field_name)


def build_excel_row(payload: Mapping[str, Any] | object) -> list[Any]:
    entry_data = ProcessEntryData.from_payload(payload)
    return [
        normalize_excel_value(
            getattr(entry_data, PROCESS_ENTRY_ATTRIBUTE_BY_COLUMN[column_letter]),
            column_letter,
        )
        for column_letter in EXCEL_COLUMN_LETTERS
    ]


__all__ = [
    "DECIMAL_NUMBER_PATTERN",
    "EXCEL_COLUMN_COUNT",
    "EXCEL_COLUMN_LETTERS",
    "HEADER_KEYWORDS_BY_COLUMN",
    "HEADER_ROW",
    "HYPHEN_RANGE_PATTERN",
    "NUMERIC_COLUMN_LETTERS",
    "PAYLOAD_FIELD_BY_ATTRIBUTE",
    "PROCESS_ENTRY_ATTRIBUTE_BY_COLUMN",
    "ProcessEntryData",
    "build_excel_row",
    "entry_id",
    "normalize_excel_value",
]
