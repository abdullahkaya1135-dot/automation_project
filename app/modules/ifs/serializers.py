from collections.abc import Mapping
from typing import Any

from .constants import MATERIAL_FIELD_MAP, OPERATION_FIELD_MAP, STOCK_FIELD_MAP


def serialize_stock_row(row: Mapping[str, Any]) -> dict[str, Any]:
    payload = {
        output_name: row.get(source_name)
        for source_name, output_name in STOCK_FIELD_MAP.items()
    }
    part_ref = row.get("PartNoRef")
    payload["material_name"] = (
        part_ref.get("Description") if isinstance(part_ref, Mapping) else None
    )
    return payload


def serialize_operation_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        output_name: row.get(source_name)
        for source_name, output_name in OPERATION_FIELD_MAP.items()
    }


def serialize_material_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        output_name: row.get(source_name)
        for source_name, output_name in MATERIAL_FIELD_MAP.items()
    }


def serialize_return_candidate_row(row: Mapping[str, Any]) -> dict[str, Any]:
    payload = serialize_stock_row(row)
    payload.pop("obj_id", None)
    return payload
