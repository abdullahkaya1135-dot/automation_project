import asyncio
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx

from ...config import Settings
from ..production_planning.reader import read_visible_planning_orders
from ..production_planning.resolver import resolve_planning_workbook
from .auth import obtain_access_token
from .materials import (
    deduplicated_materials,
    fetch_planning_used_hm02_materials,
    fetch_used_hm02_materials,
)
from .stock import (
    fetch_u1_hm02_stock,
    return_candidate_stock_rows,
    used_hm02_part_numbers,
)


def generated_at(settings: Settings) -> str:
    try:
        tzinfo = ZoneInfo(settings.timezone)
    except ZoneInfoNotFoundError:
        tzinfo = None
    return datetime.now(tzinfo).isoformat(timespec="seconds")


async def find_u1_return_candidates(
    settings: Settings,
    *,
    client: httpx.AsyncClient | None = None,
    access_token: str | None = None,
) -> dict[str, Any]:
    """Find U1 HM-02 stock rows not used by active or planned operations."""

    planning_path = resolve_planning_workbook(
        settings.production_planning_dir,
        settings.production_planning_path,
    )
    planning_orders = read_visible_planning_orders(planning_path)
    planning_order_numbers = [order.order_no for order in planning_orders]
    close_client = client is None
    http_client = client or httpx.AsyncClient(timeout=30.0)
    try:
        token = access_token or await obtain_access_token(settings, client=http_client)
        stock_rows, active_summary, planning_summary = await asyncio.gather(
            fetch_u1_hm02_stock(
                settings,
                client=http_client,
                access_token=token,
            ),
            fetch_used_hm02_materials(
                settings,
                client=http_client,
                access_token=token,
            ),
            fetch_planning_used_hm02_materials(
                settings,
                planning_order_numbers,
                client=http_client,
                access_token=token,
            ),
        )
        used_materials = deduplicated_materials(
            [
                *active_summary["used_materials"],
                *planning_summary["planning_used_materials"],
            ]
        )
        used_hm02_parts = sorted(used_hm02_part_numbers(used_materials))
        used_parts = set(used_hm02_parts)
        candidates = list(return_candidate_stock_rows(stock_rows, used_parts))
        return {
            "generated_at": generated_at(settings),
            "planning_source_path": str(planning_path),
            "planning_source_name": planning_path.name,
            "stock_count": len(stock_rows),
            "operation_count": active_summary["operation_count"],
            "active_used_material_count": active_summary["used_material_count"],
            "active_used_hm02_part_count": active_summary["used_hm02_part_count"],
            "planning_order_count": planning_summary["planning_order_count"],
            "planning_operation_count": planning_summary["planning_operation_count"],
            "planning_used_material_count": planning_summary[
                "planning_used_material_count"
            ],
            "planning_used_hm02_part_count": planning_summary[
                "planning_used_hm02_part_count"
            ],
            "used_material_count": len(used_materials),
            "used_hm02_part_count": len(used_hm02_parts),
            "return_candidate_count": len(candidates),
            "return_candidates": candidates,
            "used_hm02_parts": used_hm02_parts,
            "used_materials": used_materials,
        }
    finally:
        if close_client:
            await http_client.aclose()
