import re
from typing import Any

from ..models import TourContext
from . import shifts
from .entry_fields import (
    ENTRY_FIELD_NAMES,
    ENTRY_PAYLOAD_SCHEMA_VERSION,
    LEGACY_ENTRY_FIELD_NAMES,
    blank_excluded_section_fields,
    canonicalize_legacy_entry_payload,
)
from .request_values import optional_text, validation_error

MULTI_VALUE_REPEAT_FIELDS = frozenset({"col_r", "col_s", "col_x", "col_y"})
ENTRY_PAYLOAD_SCHEMA_VERSION_KEYS = (
    "payload_schema_version",
    "entry_payload_schema_version",
)
TEMPERATURE_REPEAT_TOKEN_PATTERN = re.compile(
    r"^([+-]?\d+(?:\.\d+)?)\s*[xX]\s*([1-9]\d*)$"
)
TEMPERATURE_SINGLE_TOKEN_PATTERN = re.compile(r"^[+-]?\d+(?:\.\d+)?$")
TEMPERATURE_REPEAT_MAX_COUNT = 200


def _expand_temperature_shorthand(value: str | None) -> str | None:
    if value is None or ("x" not in value and "X" not in value):
        return value

    tokens = [token.strip() for token in value.split(",") if token.strip()]
    if not tokens:
        return value

    expanded: list[str] = []
    for token in tokens:
        repeat_match = TEMPERATURE_REPEAT_TOKEN_PATTERN.fullmatch(token)
        if repeat_match:
            repeat_count = int(repeat_match.group(2))
            if repeat_count > TEMPERATURE_REPEAT_MAX_COUNT:
                return value
            expanded.extend([repeat_match.group(1)] * repeat_count)
            continue

        if TEMPERATURE_SINGLE_TOKEN_PATTERN.fullmatch(token):
            expanded.append(token)
            continue

        return value

    return "-".join(expanded)


def _is_v2_entry_payload(body: dict[str, Any], raw_payload: dict[str, Any]) -> bool:
    for key in ENTRY_PAYLOAD_SCHEMA_VERSION_KEYS:
        if str(body.get(key) or raw_payload.get(key) or "").strip() == str(
            ENTRY_PAYLOAD_SCHEMA_VERSION
        ):
            return True
    if str(raw_payload.get("_schema_version") or "").strip() == str(
        ENTRY_PAYLOAD_SCHEMA_VERSION
    ):
        return True
    return any(
        field_name in raw_payload or field_name in body
        for field_name in (
            "col_r",
            "col_s",
            "col_t",
            "col_u",
            "col_v",
            "col_w",
            "col_x",
            "col_y",
        )
    )


def _entry_payload_from_body(body: dict[str, Any]) -> dict[str, str | None]:
    raw_payload = body.get("payload", {})
    if raw_payload is None:
        raw_payload = {}
    if not isinstance(raw_payload, dict):
        raise validation_error("payload bir nesne olmalıdır.")

    source_field_names = (
        ENTRY_FIELD_NAMES
        if _is_v2_entry_payload(body, raw_payload)
        else LEGACY_ENTRY_FIELD_NAMES
    )
    source_payload = {
        field_name: optional_text(raw_payload.get(field_name), field_name)
        for field_name in source_field_names
    }
    for field_name in source_field_names:
        if field_name in body:
            source_payload[field_name] = optional_text(body.get(field_name), field_name)

    if source_field_names == LEGACY_ENTRY_FIELD_NAMES:
        payload = canonicalize_legacy_entry_payload(source_payload)
    else:
        payload = {
            field_name: source_payload.get(field_name)
            for field_name in ENTRY_FIELD_NAMES
        }

    for field_name in MULTI_VALUE_REPEAT_FIELDS:
        payload[field_name] = _expand_temperature_shorthand(payload[field_name])
    return blank_excluded_section_fields(payload)


def combined_entry_payload(
    context: TourContext,
    body: dict[str, Any],
) -> dict[str, str | None]:
    payload = _entry_payload_from_body(body)
    payload.update(
        {
            "col_a": shifts.recorded_date_text(context.date),
            "col_b": context.ambient_temp,
            "col_c": context.production_engineer,
            "col_d": context.shift_chief,
            "col_e": context.shift,
        }
    )

    required_fields = {
        "col_f": "makine",
        "col_h": "iş emri",
    }
    missing = [
        label
        for field_name, label in required_fields.items()
        if not payload.get(field_name)
    ]
    if missing:
        raise validation_error(
            "Eksik zorunlu kayıt alanı/alanları: " + ", ".join(missing)
        )
    return payload
