from collections.abc import Mapping, Sequence
from typing import Any

import httpx

from ...config import Settings
from .auth import obtain_access_token
from .constants import STOCK_SELECT_FIELDS
from .errors import require_settings
from .http_client import get_all
from .odata import odata_string, projection_url


async def fetch_u1_hm02_stock(
    settings: Settings,
    *,
    client: httpx.AsyncClient | None = None,
    access_token: str | None = None,
) -> list[dict[str, Any]]:
    """Fetch available HM-02 stock rows in the configured U1 location."""

    require_settings(
        settings,
        (
            ("ifs_base_url", "IFS_BASE_URL"),
            ("ifs_contract", "IFS_CONTRACT"),
            ("ifs_part_prefix", "IFS_PART_PREFIX"),
            ("ifs_u1_location", "IFS_U1_LOCATION"),
        ),
    )

    close_client = client is None
    http_client = client or httpx.AsyncClient(timeout=30.0)
    try:
        token = access_token or await obtain_access_token(settings, client=http_client)
        headers = {"Authorization": f"Bearer {token}"}
        url = projection_url(
            settings,
            "InventoryPartInStockHandling.svc/InventoryPartInStockSet",
        )
        params = {
            "$filter": (
                f"Contract eq {odata_string(settings.ifs_contract)} "
                f"and startswith(PartNo,{odata_string(settings.ifs_part_prefix)}) "
                f"and LocationNo eq {odata_string(settings.ifs_u1_location)} "
                "and AvailableQty gt 0"
            ),
            "$select": ",".join(STOCK_SELECT_FIELDS),
            "$expand": "PartNoRef($select=Description)",
            "$top": "1000",
        }
        return await get_all(
            http_client,
            url,
            endpoint_category="u1-hm02-stock",
            headers=headers,
            params=params,
        )
    finally:
        if close_client:
            await http_client.aclose()


def used_hm02_part_numbers(materials: Sequence[Mapping[str, Any]]) -> set[str]:
    return {
        part_no
        for material in materials
        if (part_no := str(material.get("PartNo") or "").strip())
    }


def return_candidate_stock_rows(
    stock_rows: Sequence[Mapping[str, Any]],
    used_parts: set[str],
) -> list[Mapping[str, Any]]:
    return [
        row
        for row in stock_rows
        if str(row.get("PartNo") or "").strip() not in used_parts
    ]
