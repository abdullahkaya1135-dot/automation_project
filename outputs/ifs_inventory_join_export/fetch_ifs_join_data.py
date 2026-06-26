import asyncio
import json
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import get_settings  # noqa: E402
from app.integrations.ifs.client import obtain_access_token  # noqa: E402

INVENTORY_PROJECTION = "InventoryTransactionsHistoryHandling"
SHOP_PROJECTION = "ShopFloorWorkbenchHandling"
INVENTORY_ENTITY_PATH = "/InventoryTransactionsHistorySet"
SHOP_ENTITY_PATH = "/Reference_OperationHistory"
PAGE_SIZE = 1000
MIN_PAGE_SIZE = 100


def _query_string(params: dict[str, object]) -> str:
    parts: list[str] = []
    for key, value in params.items():
        encoded_key = quote(str(key), safe="$")
        # IFS rejects some OData values when spaces are encoded as '+'. Keep spaces
        # percent-encoded and leave OData punctuation readable.
        encoded_value = quote(str(value), safe="(),'$=*")
        parts.append(f"{encoded_key}={encoded_value}")
    return "&".join(parts)


def _service_url(base_url: str, projection: str, path: str) -> str:
    return (
        f"{base_url.rstrip('/')}/main/ifsapplications/projection/v1/"
        f"{projection}.svc{path}"
    )


async def _json_get(
    client: httpx.AsyncClient,
    url: str,
    *,
    headers: dict[str, str],
    params: dict[str, object] | None = None,
) -> dict:
    request_url = url if params is None else f"{url}?{_query_string(params)}"
    response = await client.get(request_url, headers=headers)
    try:
        payload = response.json()
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"IFS returned non-JSON response from {url}: {response.text[:300]}"
        ) from exc
    if response.status_code >= 400:
        raise RuntimeError(
            f"IFS request failed {response.status_code} for {url}: "
            f"{json.dumps(payload, ensure_ascii=False)[:1000]}"
        )
    return payload


def _select_fields_from_openapi(openapi: dict, path: str) -> list[str]:
    operation = openapi["paths"][path]["get"]
    for parameter in operation.get("parameters", []):
        if parameter.get("name") != "$select":
            continue
        enum_values = (
            parameter.get("schema", {})
            .get("items", {})
            .get("enum", [])
        )
        return [str(value) for value in enum_values if not str(value).startswith("@")]
    raise RuntimeError(f"$select enum not found for {path}")


async def _select_fields(
    client: httpx.AsyncClient,
    base_url: str,
    headers: dict[str, str],
    projection: str,
    entity_path: str,
) -> list[str]:
    openapi = await _json_get(
        client,
        _service_url(base_url, projection, "/$openapi"),
        headers=headers,
    )
    return _select_fields_from_openapi(openapi, entity_path)


async def _fetch_all(
    client: httpx.AsyncClient,
    url: str,
    *,
    headers: dict[str, str],
    base_params: dict[str, object],
    page_size: int = PAGE_SIZE,
) -> list[dict]:
    rows: list[dict] = []
    skip = 0
    current_page_size = page_size
    while True:
        params = dict(base_params)
        params["$top"] = current_page_size
        params["$skip"] = skip
        retry_count = 0
        while True:
            try:
                payload = await _json_get(client, url, headers=headers, params=params)
                break
            except Exception as exc:
                text = str(exc)
                can_shrink = (
                    ("504" in text or "ODP_OPERATION_TIMEOUT" in text)
                    and current_page_size > MIN_PAGE_SIZE
                )
                if can_shrink:
                    current_page_size = max(MIN_PAGE_SIZE, current_page_size // 2)
                    params["$top"] = current_page_size
                    print(
                        f"{Path(url).name}: timeout at skip={skip}; "
                        f"retrying with page_size={current_page_size}",
                        flush=True,
                    )
                    continue
                retry_count += 1
                if retry_count >= 3:
                    raise
                print(
                    f"{Path(url).name}: retry {retry_count} at skip={skip} after {exc}",
                    flush=True,
                )
                time.sleep(2 * retry_count)
        page_rows = payload.get("value", [])
        if not isinstance(page_rows, list):
            raise RuntimeError(f"Unexpected IFS payload shape from {url}")
        rows.extend(page_rows)
        print(
            f"{Path(url).name}: fetched page at skip={skip}, rows={len(page_rows)}",
            flush=True,
        )
        if len(page_rows) < current_page_size:
            break
        skip += len(page_rows)
    return rows


def _parse_datetime(value: object) -> datetime | None:
    if value in (None, ""):
        return None
    text = str(value)
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _clean(value: object) -> str:
    return str(value or "").strip()


def _numeric_text(value: object) -> str:
    text = _clean(value)
    if text.endswith(".0"):
        return text[:-2]
    return text


def _order_key_from_inventory(row: dict) -> tuple[str, str, str] | None:
    if _clean(row.get("SourceRefType")) != "ShopOrder":
        return None
    order_no = _clean(row.get("SourceRef1"))
    if not order_no or not order_no.replace("-", "").replace("/", "").isalnum():
        return None
    return (
        order_no,
        _clean(row.get("SourceRef2")) or "*",
        _clean(row.get("SourceRef3")) or "*",
    )


def _order_key_from_shop(row: dict) -> tuple[str, str, str] | None:
    order_no = _clean(row.get("OrderNo"))
    if not order_no:
        return None
    return (
        order_no,
        _clean(row.get("ReleaseNo")) or "*",
        _clean(row.get("SequenceNo")) or "*",
    )


def _build_shop_indexes(shop_rows: list[dict]) -> tuple[dict, dict]:
    by_order_date: dict[tuple[str, str, str, str], list[dict]] = defaultdict(list)
    by_order: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for row in shop_rows:
        order_key = _order_key_from_shop(row)
        if order_key is None:
            continue
        by_order[order_key].append(row)
        date_applied = _clean(row.get("DateApplied"))
        if date_applied:
            by_order_date[(*order_key, date_applied)].append(row)
    return by_order_date, by_order


def _score_shop_match(inventory_row: dict, shop_row: dict) -> tuple[float, float | None]:
    score = 0.0
    if _clean(shop_row.get("ResourceId")):
        score += 10000
    if _clean(shop_row.get("PartNo")) == _clean(inventory_row.get("PartNo")):
        score += 800
    if _clean(shop_row.get("TransactionCode")) == "OPFEED":
        score += 200
    source_ref4 = _numeric_text(inventory_row.get("SourceRef4"))
    if source_ref4 and source_ref4 == _numeric_text(shop_row.get("OperationNo")):
        score += 100
    inv_time = _parse_datetime(inventory_row.get("DateTimeCreated"))
    shop_time = _parse_datetime(shop_row.get("TimeOfProduction"))
    delta_seconds: float | None = None
    if inv_time is not None and shop_time is not None:
        delta_seconds = abs((inv_time - shop_time).total_seconds())
        score += max(0, 3600 - min(delta_seconds, 3600))
    return score, delta_seconds


def _best_shop_match(
    inventory_row: dict,
    by_order_date: dict,
    by_order: dict,
) -> tuple[dict | None, str, float | None, int]:
    order_key = _order_key_from_inventory(inventory_row)
    if order_key is None:
        return None, "unmatched_no_shop_order_reference", None, 0

    date_applied = _clean(inventory_row.get("DateApplied"))
    candidates = by_order_date.get((*order_key, date_applied), [])
    candidate_scope = "order_date"
    if not candidates:
        candidates = by_order.get(order_key, [])
        candidate_scope = "order_month"
    if not candidates:
        return None, "unmatched_no_shopfloor_operation_history", None, 0

    scored = [
        (*_score_shop_match(inventory_row, row), row)
        for row in candidates
    ]
    scored.sort(key=lambda item: item[0], reverse=True)
    best_score, delta_seconds, best_row = scored[0]
    if _clean(best_row.get("ResourceId")) and delta_seconds is not None and delta_seconds <= 60:
        status = "matched_order_time_resource"
    elif _clean(best_row.get("ResourceId")):
        status = f"matched_{candidate_scope}_resource"
    else:
        status = f"matched_{candidate_scope}_no_resource"
    if best_score <= 0:
        status = f"weak_{status}"
    return best_row, status, delta_seconds, len(candidates)


def _ordered_columns(rows: list[dict], priority: list[str]) -> list[str]:
    seen: set[str] = set()
    all_columns: list[str] = []
    for row in rows:
        for column in row:
            if column not in seen:
                seen.add(column)
                all_columns.append(column)
    return [column for column in priority if column in seen] + [
        column for column in all_columns if column not in priority
    ]


def _join_rows(inventory_rows: list[dict], shop_rows: list[dict]) -> list[dict]:
    by_order_date, by_order = _build_shop_indexes(shop_rows)
    joined: list[dict] = []
    for inventory_row in inventory_rows:
        match, status, delta_seconds, candidate_count = _best_shop_match(
            inventory_row,
            by_order_date,
            by_order,
        )
        output = {
            "MachineCode": _clean(match.get("ResourceId")) if match else "",
            "ResourceId": _clean(match.get("ResourceId")) if match else "",
            "WorkCenterNo": _clean(match.get("WorkCenterNo")) if match else "",
            "ResourceDescription": _clean(match.get("ResourceDescription")) if match else "",
            "JoinStatus": status,
            "JoinCandidateCount": candidate_count,
            "JoinTimeDeltaSeconds": delta_seconds,
        }
        output["inv_HandlingUnit"] = inventory_row.get("HandlingUnitId")
        output.update({f"inv_{key}": value for key, value in inventory_row.items()})
        if match is not None:
            output.update({f"shop_{key}": value for key, value in match.items()})
        joined.append(output)
    return joined


def _date_range_filter(field_name: str, start_date: object, end_date: object) -> str:
    return (
        f"{field_name} ge {start_date} "
        f"and {field_name} le {end_date}"
    )


def _parse_date_arg(value: str):
    text = value.strip()
    for date_format in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(text, date_format).date()
        except ValueError:
            pass
    raise SystemExit(
        f"Unsupported date '{value}'. Use YYYY-MM-DD or DD.MM.YYYY, "
        "for example 2026-06-22 or 22.06.2026."
    )


def _date_window_from_args(tzinfo: ZoneInfo):
    if len(sys.argv) > 3:
        raise SystemExit("Usage: python fetch_ifs_join_data.py [start_date] [end_date]")
    if len(sys.argv) >= 2:
        start_date = _parse_date_arg(sys.argv[1])
        end_date = _parse_date_arg(sys.argv[2]) if len(sys.argv) == 3 else start_date
    else:
        today = datetime.now(tzinfo).date()
        start_date = today
        end_date = today
    if end_date < start_date:
        raise SystemExit("end_date cannot be earlier than start_date")
    return start_date, end_date


async def main() -> None:
    settings = get_settings(validate=False)
    tzinfo = ZoneInfo(settings.timezone)
    start_date, end_date = _date_window_from_args(tzinfo)
    export_started_at = datetime.now(tzinfo).isoformat(timespec="seconds")

    output_dir = Path("outputs/ifs_inventory_join_export")
    output_dir.mkdir(parents=True, exist_ok=True)

    async with httpx.AsyncClient(timeout=90.0) as client:
        token = await obtain_access_token(settings, client=client)
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        base_url = settings.ifs_base_url

        inventory_fields = await _select_fields(
            client,
            base_url,
            headers,
            INVENTORY_PROJECTION,
            INVENTORY_ENTITY_PATH,
        )
        shop_fields = await _select_fields(
            client,
            base_url,
            headers,
            SHOP_PROJECTION,
            SHOP_ENTITY_PATH,
        )

        inventory_url = _service_url(base_url, INVENTORY_PROJECTION, INVENTORY_ENTITY_PATH)
        shop_url = _service_url(base_url, SHOP_PROJECTION, SHOP_ENTITY_PATH)

        inventory_rows = await _fetch_all(
            client,
            inventory_url,
            headers=headers,
            base_params={
                "$select": ",".join(inventory_fields),
                "$filter": (
                    f"Contract eq '{settings.ifs_contract}' "
                    "and startswith(PartNo,'MM-') "
                    f"and {_date_range_filter('DateApplied', start_date, end_date)}"
                ),
                "$orderby": "TransactionId asc",
            },
        )
        shop_rows = await _fetch_all(
            client,
            shop_url,
            headers=headers,
            base_params={
                "$select": ",".join(shop_fields),
                "$filter": (
                    f"contains(Contract,'{settings.ifs_contract}') "
                    f"and {_date_range_filter('DateApplied', start_date, end_date)}"
                ),
                "$orderby": "TransactionId asc",
            },
        )

    joined_rows = _join_rows(inventory_rows, shop_rows)
    important_join_columns = [
        "MachineCode",
        "WorkCenterNo",
        "inv_DateTimeCreated",
        "inv_HandlingUnit",
        "inv_PartNo",
        "inv_PartDescription",
        "inv_LocationNo",
        "inv_Quantity",
        "inv_TransactionCodeDesc",
        "shop_OrderNo",
        "shop_QtyComplete",
        "inv_DateTimeMinuteCreated",
    ]
    inventory_priority = [
        "DateApplied",
        "DateTimeCreated",
        "HandlingUnitId",
        "TransactionId",
        "PartNo",
        "PartDescription",
        "LocationNo",
        "LocationGroup",
        "Quantity",
        "QtyReversed",
        "CatchQuantity",
        "TransactionCode",
        "TransactionCodeDesc",
        "SourceRefType",
        "SourceRef1",
        "SourceRef2",
        "SourceRef3",
        "SourceRef4",
        "SourceRef5",
    ]
    shop_priority = [
        "ResourceId",
        "WorkCenterNo",
        "ResourceDescription",
        "DateApplied",
        "TimeOfProduction",
        "TransactionId",
        "OrderNo",
        "ReleaseNo",
        "SequenceNo",
        "OperationNo",
        "PartNo",
        "QtyComplete",
        "QtyScrapped",
        "TransactionCode",
        "OperStatusCode",
        "OrderType",
    ]
    summary = {
        "export_started_at": export_started_at,
        "ifs_base_url": settings.ifs_base_url,
        "contract": settings.ifs_contract,
        "export_window": f"{start_date} through {end_date}",
        "inventory_projection": INVENTORY_PROJECTION,
        "inventory_entity": INVENTORY_ENTITY_PATH.strip("/"),
        "shop_projection": SHOP_PROJECTION,
        "shop_entity": SHOP_ENTITY_PATH.strip("/"),
        "inventory_row_count": len(inventory_rows),
        "shopfloor_row_count": len(shop_rows),
        "joined_row_count": len(joined_rows),
        "matched_with_resource_count": sum(1 for row in joined_rows if row.get("ResourceId")),
        "matched_without_resource_count": sum(
            1
            for row in joined_rows
            if not row.get("ResourceId") and str(row.get("JoinStatus", "")).startswith("matched")
        ),
        "unmatched_count": sum(
            1 for row in joined_rows if str(row.get("JoinStatus", "")).startswith("unmatched")
        ),
        "join_rule": (
            "Inventory SourceRefType=ShopOrder and SourceRef1/2/3 are matched to "
            "ShopFloorWorkbenchHandling OrderNo/ReleaseNo/SequenceNo. "
            "Within the order/date group, the export prefers rows with ResourceId "
            "and the closest TimeOfProduction to inventory DateTimeCreated. "
            "Inventory rows are fetched with PartNo starting MM-."
        ),
    }
    payload = {
        "summary": summary,
        "columns": {
            "joined": _ordered_columns(joined_rows, important_join_columns),
            "inventory": _ordered_columns(inventory_rows, inventory_priority),
            "shopfloor": _ordered_columns(shop_rows, shop_priority),
        },
        "joined_rows": joined_rows,
        "inventory_rows": inventory_rows,
        "shopfloor_rows": shop_rows,
    }
    json_path = output_dir / "ifs_inventory_shopfloor_join.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"Wrote {json_path}")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
