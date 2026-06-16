from typing import Any

from ...config import Settings
from .materials import (
    fetch_operation_hm02_materials,
    fetch_used_hm02_materials,
)
from .operations import fetch_pet_ongoing_operations
from .return_candidates import find_u1_return_candidates
from .serializers import (
    serialize_material_row,
    serialize_operation_row,
    serialize_return_candidate_row,
    serialize_stock_row,
)
from .stock import fetch_u1_hm02_stock


async def u1_hm02_stock_payload(settings: Settings) -> dict[str, Any]:
    rows = await fetch_u1_hm02_stock(settings)
    return {
        "stock_count": len(rows),
        "stock": [serialize_stock_row(row) for row in rows],
    }


async def pet_ongoing_operations_payload(settings: Settings) -> dict[str, Any]:
    rows = await fetch_pet_ongoing_operations(settings)
    return {
        "operation_count": len(rows),
        "operations": [serialize_operation_row(row) for row in rows],
    }


async def operation_hm02_materials_payload(
    settings: Settings,
    *,
    order_no: str,
    release_no: str,
    sequence_no: str,
    operation_no: int,
) -> dict[str, Any]:
    operation = {
        "OrderNo": order_no,
        "ReleaseNo": release_no,
        "SequenceNo": sequence_no,
        "OperationNo": operation_no,
    }
    rows = await fetch_operation_hm02_materials(settings, operation)
    return {
        "material_count": len(rows),
        "materials": [serialize_material_row(row) for row in rows],
    }


async def used_hm02_materials_payload(settings: Settings) -> dict[str, Any]:
    summary = await fetch_used_hm02_materials(settings)
    return {
        "operation_count": summary["operation_count"],
        "used_material_count": summary["used_material_count"],
        "used_hm02_part_count": summary["used_hm02_part_count"],
        "used_hm02_parts": summary["used_hm02_parts"],
        "used_materials": [
            serialize_material_row(row) for row in summary["used_materials"]
        ],
    }


async def u1_return_candidates_payload(settings: Settings) -> dict[str, Any]:
    summary = await find_u1_return_candidates(settings)
    return {
        "generated_at": summary["generated_at"],
        "planning_source_path": summary.get("planning_source_path"),
        "planning_source_name": summary.get("planning_source_name"),
        "stock_count": summary["stock_count"],
        "operation_count": summary["operation_count"],
        "active_used_material_count": summary["active_used_material_count"],
        "active_used_hm02_part_count": summary["active_used_hm02_part_count"],
        "planning_order_count": summary["planning_order_count"],
        "planning_operation_count": summary["planning_operation_count"],
        "planning_used_material_count": summary["planning_used_material_count"],
        "planning_used_hm02_part_count": summary["planning_used_hm02_part_count"],
        "used_material_count": summary["used_material_count"],
        "used_hm02_part_count": summary["used_hm02_part_count"],
        "return_candidate_count": summary["return_candidate_count"],
        "return_candidates": [
            serialize_return_candidate_row(row)
            for row in summary["return_candidates"]
        ],
        "used_hm02_parts": summary["used_hm02_parts"],
        "used_materials": [
            serialize_material_row(row) for row in summary["used_materials"]
        ],
    }
