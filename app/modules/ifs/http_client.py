import asyncio
from collections.abc import Mapping
from typing import Any

import httpx

from .errors import IFSClientError
from .odata import url_with_params


def body_snippet(response: httpx.Response, limit: int = 500) -> str:
    text = response.text.replace("\r", " ").replace("\n", " ").strip()
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


def raise_for_ifs_status(
    response: httpx.Response,
    *,
    endpoint_category: str,
) -> None:
    if response.status_code < 400:
        return

    snippet = body_snippet(response)
    message = f"IFS {endpoint_category} request failed with HTTP {response.status_code}"
    if snippet:
        message += f": {snippet}"
    raise IFSClientError(
        message,
        endpoint_category=endpoint_category,
        status_code=response.status_code,
    )


async def get_json_with_retry(
    client: httpx.AsyncClient,
    url: str,
    *,
    endpoint_category: str,
    headers: Mapping[str, str],
    params: Mapping[str, Any] | None = None,
    retries: int = 2,
) -> dict[str, Any]:
    for attempt in range(retries + 1):
        response = await client.get(url_with_params(url, params), headers=headers)
        if response.status_code < 500 or attempt == retries:
            break
        await asyncio.sleep(0.25 * (attempt + 1))

    raise_for_ifs_status(response, endpoint_category=endpoint_category)
    try:
        payload = response.json()
    except ValueError as exc:
        raise IFSClientError(
            f"IFS {endpoint_category} response was not valid JSON",
            endpoint_category=endpoint_category,
        ) from exc
    if not isinstance(payload, dict):
        raise IFSClientError(
            f"IFS {endpoint_category} response JSON was not an object",
            endpoint_category=endpoint_category,
        )
    return payload


async def get_all(
    client: httpx.AsyncClient,
    url: str,
    *,
    endpoint_category: str,
    headers: Mapping[str, str],
    params: Mapping[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    next_url: str | None = url
    next_params: Mapping[str, Any] | None = params

    while next_url:
        payload = await get_json_with_retry(
            client,
            next_url,
            endpoint_category=endpoint_category,
            headers=headers,
            params=next_params,
        )
        value = payload.get("value", [])
        if not isinstance(value, list):
            raise IFSClientError(
                f"IFS {endpoint_category} response did not include a value list",
                endpoint_category=endpoint_category,
            )
        rows.extend(row for row in value if isinstance(row, dict))
        next_url = payload.get("@odata.nextLink")
        next_params = None

    return rows
