"""Fetch IFS product/stock rows whose PartNo starts with selected prefixes.

This is a read-only data query. It does not order reports, print labels, or
create archive records.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.core.config import Settings, get_settings  # noqa: E402
from app.integrations.ifs.client import (  # noqa: E402
    _get_all,
    _odata_string,
    _projection_url,
    obtain_access_token,
)

DEFAULT_PREFIXES = ("MM-ENJ", "MM-PET")
DEFAULT_SELECT_FIELDS = (
    "Contract",
    "PartNo",
    "LocationNo",
    "HandlingUnitId",
    "QtyOnhand",
    "AvailableQty",
    "UoM",
    "LotBatchNo",
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _prefix_filter(prefixes: tuple[str, ...]) -> str:
    clauses = [
        f"startswith(PartNo,{_odata_string(prefix)})"
        for prefix in prefixes
        if prefix
    ]
    if not clauses:
        raise ValueError("At least one non-empty prefix is required.")
    if len(clauses) == 1:
        return clauses[0]
    return "(" + " or ".join(clauses) + ")"


def _stock_filter(settings: Settings, prefixes: tuple[str, ...], contract: str) -> str:
    clauses = [_prefix_filter(prefixes)]
    if contract:
        clauses.insert(0, f"Contract eq {_odata_string(contract)}")
    elif settings.ifs_contract.strip():
        clauses.insert(0, f"Contract eq {_odata_string(settings.ifs_contract)}")
    return " and ".join(clauses)


def _clean_prefixes(values: list[str] | None) -> tuple[str, ...]:
    raw_values = values or list(DEFAULT_PREFIXES)
    prefixes = tuple(
        dict.fromkeys(prefix for raw in raw_values if (prefix := raw.strip()))
    )
    if not prefixes:
        raise ValueError("At least one prefix is required.")
    return prefixes


def _select_fields(value: str) -> tuple[str, ...]:
    if not value.strip():
        return DEFAULT_SELECT_FIELDS
    fields = tuple(
        dict.fromkeys(field for raw in value.split(",") if (field := raw.strip()))
    )
    if not fields:
        raise ValueError("--select must contain at least one field.")
    return fields


def _generated_at(settings: Settings) -> str:
    try:
        tzinfo = ZoneInfo(settings.timezone)
    except ZoneInfoNotFoundError:
        return datetime.now().astimezone().isoformat(timespec="seconds")
    return datetime.now(tzinfo).isoformat(timespec="seconds")


async def fetch_product_prefix_rows(
    settings: Settings,
    *,
    prefixes: tuple[str, ...],
    contract: str,
    select_fields: tuple[str, ...],
    expand_description: bool,
    row_limit: int,
    timeout: float,
) -> list[dict[str, Any]]:
    if row_limit < 1:
        raise ValueError("--top must be greater than 0.")

    async with httpx.AsyncClient(timeout=timeout) as client:
        token = await obtain_access_token(settings, client=client)
        headers = {"Authorization": f"Bearer {token}"}
        url = _projection_url(
            settings,
            "InventoryPartInStockHandling.svc/InventoryPartInStockSet",
        )
        rows = await _get_all(
            client,
            url,
            endpoint_category="product-prefix-stock",
            headers=headers,
            params={
                "$filter": _stock_filter(settings, prefixes, contract),
                "$select": ",".join(select_fields),
                **(
                    {"$expand": "PartNoRef($select=Description)"}
                    if expand_description
                    else {}
                ),
                "$orderby": "PartNo asc",
                "$top": str(row_limit),
            },
        )
    return rows[:row_limit]


def build_output(
    rows: list[dict[str, Any]],
    *,
    prefixes: tuple[str, ...],
    contract: str,
    select_fields: tuple[str, ...],
    expand_description: bool,
    settings: Settings,
) -> dict[str, Any]:
    resolved_contract = contract or settings.ifs_contract
    return {
        "generated_at": _generated_at(settings),
        "generated_timezone": settings.timezone,
        "projection": "InventoryPartInStockHandling",
        "entity_set": "InventoryPartInStockSet",
        "contract": resolved_contract,
        "prefixes": list(prefixes),
        "selected_fields": list(select_fields),
        "description_expanded": expand_description,
        "matching_count": len(rows),
        "data": rows,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Read IFS stock/product rows where PartNo starts with MM-ENJ or MM-PET."
        )
    )
    parser.add_argument(
        "--prefix",
        action="append",
        help=(
            "PartNo prefix to search. Repeat for multiple prefixes. "
            "Defaults to MM-ENJ and MM-PET."
        ),
    )
    parser.add_argument(
        "--contract",
        default="",
        help="IFS site/contract. Defaults to IFS_CONTRACT from .env.",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=20,
        help="Maximum rows to return. Default: 20.",
    )
    parser.add_argument(
        "--select",
        default="",
        help=(
            "Comma-separated OData fields. Defaults to a conservative stock field "
            "list: Contract,PartNo,LocationNo,HandlingUnitId,QtyOnhand,"
            "AvailableQty,UoM,LotBatchNo."
        ),
    )
    parser.add_argument(
        "--no-description",
        action="store_true",
        help="Do not expand PartNoRef($select=Description).",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Optional JSON output path. If omitted, prints JSON to stdout.",
    )
    parser.add_argument("--timeout", type=float, default=60.0)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        settings = get_settings(validate=False)
        prefixes = _clean_prefixes(args.prefix)
        select_fields = _select_fields(args.select)
        expand_description = not args.no_description
        rows = asyncio.run(
            fetch_product_prefix_rows(
                settings,
                prefixes=prefixes,
                contract=_text(args.contract),
                select_fields=select_fields,
                expand_description=expand_description,
                row_limit=args.top,
                timeout=args.timeout,
            )
        )
        payload = build_output(
            rows,
            prefixes=prefixes,
            contract=_text(args.contract),
            select_fields=select_fields,
            expand_description=expand_description,
            settings=settings,
        )
    except Exception as exc:
        print(f"IFS product prefix check failed: {exc}", file=sys.stderr)
        return 1

    json_text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json_text + "\n", encoding="utf-8")
        print(f"Wrote {len(rows)} matching row(s) to {output_path}")
    else:
        print(json_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
