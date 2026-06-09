import html
import json
import re
from dataclasses import dataclass
from json import JSONDecodeError
from pathlib import Path
from typing import Any


class ShopOrderSourceError(RuntimeError):
    """Raised when shop order options cannot be read from the source file."""


@dataclass(frozen=True)
class ShopOrderOption:
    order_no: str
    resource_id: str
    work_center_no: str = ""
    part_description: str = ""


def _clean_text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _natural_key(value: str) -> tuple[tuple[int, int | str], ...]:
    parts: list[tuple[int, int | str]] = []
    for part in re.split(r"(\d+)", value):
        if not part:
            continue
        if part.isdigit():
            parts.append((0, int(part)))
        else:
            parts.append((1, part.casefold()))
    return tuple(parts)


def _load_json_payload(raw_text: str) -> Any:
    source_text = html.unescape(raw_text.strip())
    try:
        return json.loads(source_text)
    except JSONDecodeError:
        start = source_text.find("{")
        end = source_text.rfind("}")
        if start < 0 or end <= start:
            raise ShopOrderSourceError("Kaynak dosyada JSON nesnesi bulunamadı.")

    try:
        return json.loads(source_text[start : end + 1])
    except JSONDecodeError as exc:
        raise ShopOrderSourceError(f"Kaynak dosya JSON olarak okunamadı: {exc}") from exc


def _payload_items(payload: Any) -> list[Any]:
    if isinstance(payload, dict):
        items = payload.get("value", [])
    else:
        items = payload
    if not isinstance(items, list):
        raise ShopOrderSourceError("Kaynak dosyada value listesi bulunamadı.")
    return items


def extract_shop_order_options(raw_text: str) -> list[ShopOrderOption]:
    payload = _load_json_payload(raw_text)
    seen: set[tuple[str, str]] = set()
    options: list[ShopOrderOption] = []

    for item in _payload_items(payload):
        if not isinstance(item, dict):
            continue
        order_no = _clean_text(item.get("OrderNo"))
        resource_id = _clean_text(item.get("ResourceId"))
        if not order_no or not resource_id:
            continue

        key = (order_no, resource_id)
        if key in seen:
            continue
        seen.add(key)
        options.append(
            ShopOrderOption(
                order_no=order_no,
                resource_id=resource_id,
                work_center_no=_clean_text(item.get("WorkCenterNo")),
                part_description=_clean_text(item.get("PartDescription")),
            )
        )

    options.sort(key=lambda option: (_natural_key(option.resource_id), _natural_key(option.order_no)))
    return options


def read_shop_order_options(path: str) -> list[ShopOrderOption]:
    source_path = Path(path).expanduser()
    try:
        raw_text = source_path.read_text(encoding="utf-8-sig")
    except FileNotFoundError as exc:
        raise ShopOrderSourceError(f"Kaynak dosya bulunamadı: {source_path}") from exc
    except OSError as exc:
        raise ShopOrderSourceError(f"Kaynak dosya okunamadı: {source_path} ({exc})") from exc
    return extract_shop_order_options(raw_text)


def shop_order_source_payload(path: str) -> dict[str, Any]:
    try:
        options = read_shop_order_options(path)
    except ShopOrderSourceError as exc:
        return {
            "available": False,
            "path": path,
            "last_error": str(exc),
            "operation_count": 0,
            "order_count": 0,
            "resource_count": 0,
            "options": [],
        }

    order_nos = sorted({option.order_no for option in options}, key=_natural_key)
    resource_ids = sorted({option.resource_id for option in options}, key=_natural_key)
    return {
        "available": bool(options),
        "path": path,
        "last_error": None if options else "Kaynak dosyada OrderNo ve ResourceId çifti bulunamadı.",
        "operation_count": len(options),
        "order_count": len(order_nos),
        "resource_count": len(resource_ids),
        "options": [
            {
                "order_no": option.order_no,
                "resource_id": option.resource_id,
            }
            for option in options
        ],
    }
