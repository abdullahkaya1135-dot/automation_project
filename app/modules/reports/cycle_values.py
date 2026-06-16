import re
from datetime import date as Date
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

PART_NECK_PATTERN = re.compile(r"(\d+(?:[,.]\d+)?)\s*MM\b", re.IGNORECASE)
PART_GRAM_PATTERN = re.compile(r"(\d+(?:[,.]\d+)?)\s*GR\b", re.IGNORECASE)


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def identifier(value: Any) -> str:
    text = clean_text(value)
    if not text:
        return ""
    if re.fullmatch(r"\d+\.0+", text):
        return text.split(".", 1)[0]
    return text


def number(value: Any) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        return Decimal(str(value))

    text = clean_text(value).replace(",", ".")
    if not text:
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def excel_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        if value == value.to_integral_value():
            return int(value)
        return float(value)
    return value


def parse_date(value: Any) -> Date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, Date):
        return value

    text = clean_text(value)
    if not text:
        return None
    for date_format in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, date_format).date()
        except ValueError:
            continue
    return None


def parse_part_description(part_description: str) -> tuple[Decimal | None, Decimal | None]:
    neck_match = PART_NECK_PATTERN.search(part_description)
    gram_match = PART_GRAM_PATTERN.search(part_description)
    neck = number(neck_match.group(1)) if neck_match else None
    gram = number(gram_match.group(1)) if gram_match else None
    return neck, gram


def normalize_machine_group(value: Any) -> str:
    text = clean_text(value).upper()
    compact = re.sub(r"[\s\-/]+", "", text)
    aliases = {
        "70DPH": "DPH70",
        "DPH70": "DPH70",
        "50MB": "50MB",
        "50MB1": "50MB",
        "50MB2": "50MB",
        "50MB3": "50MB",
        "PF6": "PF62",
        "PF62": "PF62",
        "PF8": "PF84",
        "12M1": "12M",
        "12M": "12M",
        "TP250": "PREFORM",
        "TP380": "PREFORM",
        "PREFORM": "PREFORM",
    }
    return aliases.get(compact, compact)
