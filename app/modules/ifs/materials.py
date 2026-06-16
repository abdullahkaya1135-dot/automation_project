from collections.abc import Mapping, Sequence
from typing import Any

import httpx

from ...config import Settings
from .auth import obtain_access_token
from .concurrency import gather_limited as gather_limited
from .constants import MATERIAL_SELECT_FIELDS, PLANNING_IFS_CONCURRENCY
from .errors import require_settings
from .http_client import get_all
from .material_rows import cleaned_order_numbers as cleaned_planning_order_numbers
from .material_rows import deduplicated_materials as deduplicated_materials
from .material_rows import deduplicated_operations as deduplicated_operations
from .material_rows import deduplicated_rows as deduplicated_rows
from .material_rows import flatten_material_groups, flatten_operation_groups
from .odata import odata_string, operation_materials_path, projection_url
from .operations import fetch_pet_ongoing_operations, fetch_shop_order_operations
from .stock import used_hm02_part_numbers


async def fetch_operation_hm02_materials(
    settings: Settings,
    operation: Mapping[str, Any],
    *,
    client: httpx.AsyncClient | None = None,
    access_token: str | None = None,
) -> list[dict[str, Any]]:
    """Fetch HM-02 material lines for one dispatch-list operation."""

    require_settings(
        settings,
        (
            ("ifs_base_url", "IFS_BASE_URL"),
            ("ifs_part_prefix", "IFS_PART_PREFIX"),
        ),
    )

    close_client = client is None
    http_client = client or httpx.AsyncClient(timeout=30.0)
    try:
        token = access_token or await obtain_access_token(settings, client=http_client)
        headers = {"Authorization": f"Bearer {token}"}
        url = projection_url(settings, operation_materials_path(operation))
        params = {
            "$filter": f"startswith(PartNo,{odata_string(settings.ifs_part_prefix)})",
            "$select": ",".join(MATERIAL_SELECT_FIELDS),
            "$top": "1000",
        }
        return await get_all(
            http_client,
            url,
            endpoint_category="operation-hm02-materials",
            headers=headers,
            params=params,
        )
    finally:
        if close_client:
            await http_client.aclose()


async def fetch_hm02_materials_for_operations(
    settings: Settings,
    operations: Sequence[Mapping[str, Any]],
    *,
    client: httpx.AsyncClient,
    access_token: str,
    concurrency: int = PLANNING_IFS_CONCURRENCY,
) -> list[dict[str, Any]]:
    async def fetch_materials(operation: Mapping[str, Any]) -> list[dict[str, Any]]:
        return await fetch_operation_hm02_materials(
            settings,
            operation,
            client=client,
            access_token=access_token,
        )

    material_groups = await gather_limited(
        list(operations),
        fetch_materials,
        concurrency=concurrency,
    )
    return deduplicated_materials(flatten_material_groups(material_groups))


async def fetch_used_hm02_materials(
    settings: Settings,
    *,
    client: httpx.AsyncClient | None = None,
    access_token: str | None = None,
) -> dict[str, Any]:
    """Fetch all active PET operation materials and build the used HM-02 part set."""

    close_client = client is None
    http_client = client or httpx.AsyncClient(timeout=30.0)
    try:
        token = access_token or await obtain_access_token(settings, client=http_client)
        operations = await fetch_pet_ongoing_operations(
            settings,
            client=http_client,
            access_token=token,
        )
        operations = deduplicated_operations(operations)
        used_materials = await fetch_hm02_materials_for_operations(
            settings,
            operations,
            client=http_client,
            access_token=token,
        )

        used_parts = sorted(used_hm02_part_numbers(used_materials))
        return {
            "operation_count": len(operations),
            "used_material_count": len(used_materials),
            "used_hm02_part_count": len(used_parts),
            "used_hm02_parts": used_parts,
            "used_materials": used_materials,
        }
    finally:
        if close_client:
            await http_client.aclose()


async def fetch_planning_used_hm02_materials(
    settings: Settings,
    order_numbers: Sequence[str],
    *,
    client: httpx.AsyncClient | None = None,
    access_token: str | None = None,
    concurrency: int = PLANNING_IFS_CONCURRENCY,
) -> dict[str, Any]:
    """Fetch HM-02 material usage for visible production-planning shop orders."""

    planning_order_numbers = cleaned_planning_order_numbers(order_numbers)

    close_client = client is None
    http_client = client or httpx.AsyncClient(timeout=30.0)
    try:
        token = access_token or await obtain_access_token(settings, client=http_client)

        async def fetch_order_operations(order_no: str) -> list[dict[str, Any]]:
            return await fetch_shop_order_operations(
                settings,
                order_no,
                client=http_client,
                access_token=token,
            )

        operation_groups = await gather_limited(
            planning_order_numbers,
            fetch_order_operations,
            concurrency=concurrency,
        )
        operations = deduplicated_operations(flatten_operation_groups(operation_groups))
        used_materials = await fetch_hm02_materials_for_operations(
            settings,
            operations,
            client=http_client,
            access_token=token,
            concurrency=concurrency,
        )
        used_parts = sorted(used_hm02_part_numbers(used_materials))
        return {
            "planning_order_count": len(planning_order_numbers),
            "planning_operation_count": len(operations),
            "planning_used_material_count": len(used_materials),
            "planning_used_hm02_part_count": len(used_parts),
            "planning_used_hm02_parts": used_parts,
            "planning_used_materials": used_materials,
        }
    finally:
        if close_client:
            await http_client.aclose()
