from typing import Any

from ...domain.entry_fields import (
    ENTRY_FORM_FIELD_NAMES,
    ENTRY_PAYLOAD_SCHEMA_VERSION,
)
from ...domain.entry_payloads import MULTI_VALUE_REPEAT_FIELDS
from ..auxiliary_systems.fields import (
    AUXILIARY_CHECK_FIELD_NAMES,
    AUXILIARY_FIELD_NAMES,
    AUXILIARY_MEASUREMENT_FIELD_NAMES,
)


def field_definitions_payload() -> dict[str, Any]:
    return {
        "process_entry": {
            "payload_schema_version": ENTRY_PAYLOAD_SCHEMA_VERSION,
            "payload_fields": list(ENTRY_FORM_FIELD_NAMES),
            "temperature_repeat_fields": [
                field_name
                for field_name in ENTRY_FORM_FIELD_NAMES
                if field_name in MULTI_VALUE_REPEAT_FIELDS
            ],
        },
        "auxiliary": {
            "payload_fields": list(AUXILIARY_FIELD_NAMES),
            "measurement_fields": list(AUXILIARY_MEASUREMENT_FIELD_NAMES),
            "check_fields": list(AUXILIARY_CHECK_FIELD_NAMES),
        },
    }
