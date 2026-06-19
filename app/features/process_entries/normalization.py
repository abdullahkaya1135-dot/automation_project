import re
import unicodedata
from datetime import date, datetime
from typing import Any

PRODUCTION_ENGINEER_NAMES = (
    "Barış Çetik",
    "Abdullah Kaya",
    "Fevzi Kılınç",
)

_ENGINEER_ALIASES = {
    "baris cetik": "Barış Çetik",
    "abdullah kaya": "Abdullah Kaya",
    "fevzi kilinc": "Fevzi Kılınç",
    "fevzi kilnc": "Fevzi Kılınç",
}
_MACHINE_CODE_PATTERN = re.compile(r"\d+")
_DATE_FORMATS = (
    "%Y-%m-%d",
    "%d.%m.%Y",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%Y/%m/%d",
)


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).strip().split())


def _ascii_key(value: Any) -> str:
    text = _clean_text(value).casefold()
    decomposed = unicodedata.normalize("NFKD", text)
    without_marks = "".join(
        char for char in decomposed if not unicodedata.combining(char)
    )
    return without_marks.replace("ı", "i").replace("İ", "i")


def normalize_production_engineer_name(value: Any) -> str | None:
    key = _ascii_key(value)
    if not key:
        return None
    return _ENGINEER_ALIASES.get(key, _clean_text(value))


def production_engineer_display_order(name: str) -> int:
    try:
        return PRODUCTION_ENGINEER_NAMES.index(name) + 1
    except ValueError:
        return len(PRODUCTION_ENGINEER_NAMES) + 1


def normalize_machine_code(value: Any) -> str | None:
    match = _MACHINE_CODE_PATTERN.search(_clean_text(value))
    if match is None:
        return None
    return match.group(0)


def normalize_process_date(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()

    text = _clean_text(value)
    if not text:
        return None
    for date_format in _DATE_FORMATS:
        try:
            return datetime.strptime(text, date_format).date().isoformat()
        except ValueError:
            continue
    return text
