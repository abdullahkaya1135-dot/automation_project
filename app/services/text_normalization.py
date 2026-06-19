from typing import Any


def stripped_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def collapsed_whitespace_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).strip().split())


def optional_collapsed_whitespace_text(value: Any) -> str | None:
    text = collapsed_whitespace_text(value)
    return text or None
