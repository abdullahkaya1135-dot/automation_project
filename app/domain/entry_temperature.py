import re

MULTI_VALUE_REPEAT_FIELDS = frozenset({"col_r", "col_s", "col_x", "col_y"})
TEMPERATURE_REPEAT_TOKEN_PATTERN = re.compile(
    r"^([+-]?\d+(?:\.\d+)?)\s*[xX]\s*([1-9]\d*)$"
)
TEMPERATURE_SINGLE_TOKEN_PATTERN = re.compile(r"^[+-]?\d+(?:\.\d+)?$")
TEMPERATURE_REPEAT_MAX_COUNT = 200


def expand_temperature_shorthand(value: str | None) -> str | None:
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


def expand_temperature_shorthand_fields(
    payload: dict[str, str | None],
) -> dict[str, str | None]:
    for field_name in MULTI_VALUE_REPEAT_FIELDS:
        payload[field_name] = expand_temperature_shorthand(payload[field_name])
    return payload
