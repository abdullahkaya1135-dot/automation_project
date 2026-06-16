from typing import Any

import httpx

from ...config import Settings
from .auth import obtain_access_token
from .constants import OPERATION_SELECT_FIELDS
from .errors import require_settings
from .http_client import get_all
from .odata import pet_operations_path, projection_url, shop_order_operations_path


async def fetch_pet_ongoing_operations(
    settings: Settings,
    *,
    client: httpx.AsyncClient | None = None,
    access_token: str | None = None,
) -> list[dict[str, Any]]:
    """Fetch ongoing operations from the configured PET dispatch list."""

    require_settings(
        settings,
        (
            ("ifs_base_url", "IFS_BASE_URL"),
            ("ifs_contract", "IFS_CONTRACT"),
            ("ifs_company_id", "IFS_COMPANY_ID"),
            ("ifs_dispatch_filter_id", "IFS_DISPATCH_FILTER_ID"),
        ),
    )

    close_client = client is None
    http_client = client or httpx.AsyncClient(timeout=30.0)
    try:
        token = access_token or await obtain_access_token(settings, client=http_client)
        headers = {"Authorization": f"Bearer {token}"}
        url = projection_url(settings, pet_operations_path(settings))
        params = {
            "$select": ",".join(OPERATION_SELECT_FIELDS),
            "$top": "1000",
        }
        return await get_all(
            http_client,
            url,
            endpoint_category="pet-ongoing-operations",
            headers=headers,
            params=params,
        )
    finally:
        if close_client:
            await http_client.aclose()


async def fetch_shop_order_operations(
    settings: Settings,
    order_no: str,
    *,
    client: httpx.AsyncClient | None = None,
    access_token: str | None = None,
) -> list[dict[str, Any]]:
    """Fetch dispatch-list operations for one scheduled shop order."""

    require_settings(
        settings,
        (
            ("ifs_base_url", "IFS_BASE_URL"),
            ("ifs_contract", "IFS_CONTRACT"),
            ("ifs_company_id", "IFS_COMPANY_ID"),
        ),
    )

    order_no = str(order_no or "").strip()
    if not order_no:
        return []

    close_client = client is None
    http_client = client or httpx.AsyncClient(timeout=30.0)
    try:
        token = access_token or await obtain_access_token(settings, client=http_client)
        headers = {"Authorization": f"Bearer {token}"}
        url = projection_url(settings, shop_order_operations_path(settings, order_no))
        params = {
            "$select": ",".join(OPERATION_SELECT_FIELDS),
            "$top": "1000",
        }
        return await get_all(
            http_client,
            url,
            endpoint_category="planning-shop-order-operations",
            headers=headers,
            params=params,
        )
    finally:
        if close_client:
            await http_client.aclose()
