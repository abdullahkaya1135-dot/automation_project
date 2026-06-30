from __future__ import annotations

import asyncio
from datetime import date as Date
from urllib.parse import unquote

import httpx
import pytest

import app.integrations.ifs.client as ifs_client
from app.core.config import Settings
from app.integrations.ifs.client import (
    IFSClientError,
    fetch_inventory_part_descriptions,
    fetch_label_material_availability,
    fetch_operation_hm02_materials,
    fetch_planning_used_hm02_materials,
    fetch_production_label_stock_rows,
    fetch_used_hm02_materials,
)

from .helpers import MULTI_PREFIX_FILTER, RequestRecorder


def test_fetch_operation_hm02_materials_encodes_operation_key_and_paginates():
    requests: list[httpx.Request] = []
    recorder = RequestRecorder(requests)
    settings = Settings(ifs_base_url="https://ifs.example.com")
    operation = {
        "OrderNo": "2615",
        "ReleaseNo": "*",
        "SequenceNo": "*",
        "OperationNo": 10,
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer test-token"
        if len(requests) == 1:
            return httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "OrderNo": "2615",
                            "ReleaseNo": "*",
                            "SequenceNo": "*",
                            "LineItemNo": 2,
                            "OperationNo": 10,
                            "PartNo": "HM-02-01-01-525",
                        }
                    ],
                    "@odata.nextLink": "https://ifs.example.com/next-material-page",
                },
            )
        return httpx.Response(
            200,
            json={
                "value": [
                    {
                        "OrderNo": "2615",
                        "ReleaseNo": "*",
                        "SequenceNo": "*",
                        "LineItemNo": 3,
                        "OperationNo": 10,
                        "PartNo": "HM-04-01-01-526",
                    }
                ]
            },
        )

    async def run() -> list[dict]:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(recorder.wrap(handler))
        ) as client:
            return await fetch_operation_hm02_materials(
                settings,
                operation,
                client=client,
                access_token="test-token",
            )

    rows = asyncio.run(run())

    assert rows == [
        {
            "OrderNo": "2615",
            "ReleaseNo": "*",
            "SequenceNo": "*",
            "LineItemNo": 2,
            "OperationNo": 10,
            "PartNo": "HM-02-01-01-525",
        },
        {
            "OrderNo": "2615",
            "ReleaseNo": "*",
            "SequenceNo": "*",
            "LineItemNo": 3,
            "OperationNo": 10,
            "PartNo": "HM-04-01-01-526",
        },
    ]
    assert len(requests) == 2
    first_raw_path = requests[0].url.raw_path.decode().split("?", 1)[0]
    assert "DispatchListOperationSet" in first_raw_path
    assert "OrderNo='2615'" in first_raw_path
    assert "ReleaseNo='%2A'" in first_raw_path
    assert "SequenceNo='%2A'" in first_raw_path
    assert "OperationNo=10" in first_raw_path
    assert "%252A" not in first_raw_path
    assert first_raw_path.endswith(")/OperationMaterialArray")
    assert requests[0].url.params["$filter"] == MULTI_PREFIX_FILTER
    assert requests[0].url.params["$select"] == (
        "OrderNo,ReleaseNo,SequenceNo,LineItemNo,OperationNo,PartNo,IssueToLoc,"
        "QtyRequired,QtyAssigned,QtyIssued,QtyRemainingToReserve,QtyAvailable,"
        "PrintUnit,SoPartNo,Cf_Tercihedilenkaynak"
    )
    assert requests[0].url.params["$top"] == "1000"
    assert str(requests[1].url) == "https://ifs.example.com/next-material-page"


def test_fetch_operation_hm02_materials_reports_ifs_http_errors():
    settings = Settings(ifs_base_url="https://ifs.example.com")
    operation = {
        "OrderNo": "2615",
        "ReleaseNo": "*",
        "SequenceNo": "*",
        "OperationNo": 10,
    }

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="Operation not found")

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await fetch_operation_hm02_materials(
                settings,
                operation,
                client=client,
                access_token="test-token",
            )

    with pytest.raises(IFSClientError) as exc_info:
        asyncio.run(run())

    assert exc_info.value.status_code == 404
    assert "operation-hm02-materials" in str(exc_info.value)
    assert "Operation not found" in str(exc_info.value)


def test_fetch_operation_hm02_materials_requires_operation_key_fields():
    settings = Settings(ifs_base_url="https://ifs.example.com")

    async def run() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda request: httpx.Response(200))
        ) as client:
            await fetch_operation_hm02_materials(
                settings,
                {"OrderNo": "2615", "ReleaseNo": "*", "OperationNo": 10},
                client=client,
                access_token="test-token",
            )

    with pytest.raises(IFSClientError, match="SequenceNo"):
        asyncio.run(run())


def test_fetch_production_label_stock_rows_uses_stock_journey_query():
    requests: list[httpx.Request] = []
    recorder = RequestRecorder(requests)
    settings = Settings(
        ifs_base_url="https://ifs.example.com",
        ifs_label_part_prefixes=("MM", "PM"),
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer test-token"
        if len(requests) == 1:
            return httpx.Response(
                200,
                json={
                    "@odata.count": 3,
                    "value": [
                        {"ObjId": "OBJ-1", "HandlingUnitId": "HU-1"},
                        {"ObjId": "OBJ-2", "HandlingUnitId": "HU-2"},
                    ],
                },
            )
        return httpx.Response(
            200,
            json={
                "@odata.count": 3,
                "value": [
                    {"ObjId": "OBJ-2", "HandlingUnitId": "HU-2-DUP"},
                    {"ObjId": "OBJ-3", "HandlingUnitId": "HU-3"},
                ],
            },
        )

    async def run() -> list[dict]:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(recorder.wrap(handler))
        ) as client:
            return await fetch_production_label_stock_rows(
                settings,
                date_from=Date(2026, 6, 8),
                date_to=Date(2026, 6, 9),
                client=client,
                access_token="test-token",
                page_size=2,
            )

    rows = asyncio.run(run())

    assert [row["ObjId"] for row in rows] == ["OBJ-1", "OBJ-2", "OBJ-3"]
    assert len(requests) == 2
    assert requests[0].url.path.endswith(
        "/InventoryPartInStockHandling.svc/InventoryPartInStockSet"
    )
    assert requests[0].url.params["$filter"] == (
        "Contract eq 'S01' "
        "and (startswith(PartNo,'MM') or startswith(PartNo,'PM')) "
        "and ReceiptDate ge 2026-06-08T00:00:00Z "
        "and ReceiptDate lt 2026-06-10T00:00:00Z"
    )
    assert requests[0].url.params["use-timezone-filter"] == "false"
    assert requests[0].url.params["$select"] == (
        "Contract,PartNo,PartNoDesc,LocationNo,LotBatchNo,SerialNo,QtyOnhand,"
        "CatchQtyOnhand,UnifiedOnHandQty,AvailableQty,UoM,LastCountDate,"
        "LocationType,ReceiptDate,HandlingUnitId,"
        "HandlingUnitTypeDesc,LocationDescription,Cf_Palet_Ici_Miktar,ObjId"
    )
    assert "LastActivityDate" not in requests[0].url.params["$select"]
    assert requests[0].url.params["$orderby"] == (
        "ReceiptDate asc,HandlingUnitId asc,LocationNo asc"
    )
    assert "LastActivityDate" not in requests[0].url.params["$filter"]
    assert "LastActivityDate" not in requests[0].url.params["$orderby"]
    assert requests[0].url.params["$count"] == "true"
    assert requests[0].url.params["$top"] == "2"
    assert requests[0].url.params["$skip"] == "0"
    assert requests[1].url.params["$top"] == "2"
    assert requests[1].url.params["$skip"] == "2"


def test_fetch_inventory_part_descriptions_queries_reference_inventory_part():
    requests: list[httpx.Request] = []
    recorder = RequestRecorder(requests)
    settings = Settings(ifs_base_url="https://ifs.example.com")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer test-token"
        return httpx.Response(
            200,
            json={
                "@odata.count": 2,
                "value": [
                    {
                        "Contract": "S01",
                        "PartNo": "MM-PET001",
                        "Description": "PET 28MM 35GR",
                    },
                    {
                        "Contract": "S01",
                        "PartNo": "MM-PET002",
                        "Description": "PET 30MM 40GR",
                    },
                ],
            },
        )

    async def run() -> dict[str, str]:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(recorder.wrap(handler))
        ) as client:
            return await fetch_inventory_part_descriptions(
                settings,
                ["MM-PET001", "MM-PET002", "MM-PET001"],
                client=client,
                access_token="test-token",
                page_size=1000,
            )

    descriptions = asyncio.run(run())

    assert descriptions == {
        "MM-PET001": "PET 28MM 35GR",
        "MM-PET002": "PET 30MM 40GR",
    }
    assert len(requests) == 1
    assert requests[0].url.path.endswith(
        "/InventoryPartInStockHandling.svc/Reference_InventoryPart"
    )
    assert requests[0].url.params["$filter"] == (
        "Contract eq 'S01' and (PartNo eq 'MM-PET001' or PartNo eq 'MM-PET002')"
    )
    assert requests[0].url.params["$select"] == "Contract,PartNo,Description"
    assert requests[0].url.params["$orderby"] == "PartNo asc"
    assert requests[0].url.params["$count"] == "true"
    assert requests[0].url.params["$top"] == "1000"
    assert requests[0].url.params["$skip"] == "0"


def test_fetch_used_hm02_materials_collects_materials_for_all_operations():
    requests: list[httpx.Request] = []
    recorder = RequestRecorder(requests)
    settings = Settings(ifs_base_url="https://ifs.example.com")

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.raw_path.decode().split("?", 1)[0]
        if "GetOperations" in path:
            return httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "OrderNo": "2615",
                            "ReleaseNo": "*",
                            "SequenceNo": "*",
                            "OperationNo": 10,
                        },
                        {
                            "OrderNo": "2616",
                            "ReleaseNo": "*",
                            "SequenceNo": "*",
                            "OperationNo": 20,
                        },
                    ]
                },
            )
        if "OperationNo=10" in path:
            return httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "OrderNo": "2615",
                            "OperationNo": 10,
                            "PartNo": "HM-02-A",
                        },
                        {
                            "OrderNo": "2615",
                            "OperationNo": 10,
                            "PartNo": "HM-02-A",
                        },
                    ]
                },
            )
        if "OperationNo=20" in path:
            return httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "OrderNo": "2616",
                            "OperationNo": 20,
                            "PartNo": "HM-03-B",
                        },
                        {
                            "OrderNo": "2616",
                            "OperationNo": 20,
                            "LineItemNo": 2,
                            "PartNo": "HM-04-C",
                        },
                        {
                            "OrderNo": "2616",
                            "OperationNo": 20,
                            "PartNo": "",
                        },
                    ]
                },
            )
        return httpx.Response(404, text="Unexpected URL")

    async def run() -> dict:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(recorder.wrap(handler))
        ) as client:
            return await fetch_used_hm02_materials(
                settings,
                client=client,
                access_token="test-token",
            )

    summary = asyncio.run(run())

    assert len(requests) == 3
    assert summary["operation_count"] == 2
    assert summary["used_material_count"] == 3
    assert summary["used_part_count"] == 3
    assert summary["used_parts"] == ["HM-02-A", "HM-03-B", "HM-04-C"]
    assert summary["used_hm02_part_count"] == 3
    assert summary["used_hm02_parts"] == ["HM-02-A", "HM-03-B", "HM-04-C"]
    assert [row["PartNo"] for row in summary["used_materials"]] == [
        "HM-02-A",
        "HM-03-B",
        "HM-04-C",
    ]


def test_fetch_label_material_availability_blocks_by_aggregated_u1_available_qty():
    requests: list[httpx.Request] = []
    recorder = RequestRecorder(requests)
    settings = Settings(ifs_base_url="https://ifs.example.com")

    def handler(request: httpx.Request) -> httpx.Response:
        path = unquote(request.url.raw_path.decode()).split("?", 1)[0]
        if "GetOperations" in path:
            assert "OperStatusCode" in request.url.params["$select"]
            return httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "OrderNo": "2615",
                            "ReleaseNo": "*",
                            "SequenceNo": "*",
                            "OperationNo": 10,
                            "OperStatusCode": "InProcess",
                            "PreferredResourceId": "135",
                            "WorkCenterNo": "WC-1",
                            "PartNo": "MM-PET-A",
                            "PartNoDesc": "Bottle A",
                        },
                        {
                            "OrderNo": "2616",
                            "ReleaseNo": "*",
                            "SequenceNo": "*",
                            "OperationNo": 20,
                            "OperStatusCode": "InProcess",
                            "PreferredResourceId": "136",
                            "WorkCenterNo": "WC-2",
                            "PartNo": "MM-PET-B",
                            "PartNoDesc": "Bottle B",
                        },
                        {
                            "OrderNo": "2617",
                            "ReleaseNo": "*",
                            "SequenceNo": "*",
                            "OperationNo": 30,
                            "OperStatusCode": "Released",
                            "PreferredResourceId": "137",
                        },
                    ]
                },
            )
        if "OperationMaterialArray" in path and "OrderNo='2615'" in path:
            assert request.url.params["$filter"] == (
                "(startswith(PartNo,'HM') or startswith(PartNo,'YM'))"
            )
            return httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "OrderNo": "2615",
                            "ReleaseNo": "*",
                            "SequenceNo": "*",
                            "OperationNo": 10,
                            "LineItemNo": 1,
                            "PartNo": "HM-A",
                            "IssueToLoc": "U1",
                            "QtyRemainingToReserve": 7,
                            "QtyAvailable": 100,
                        },
                        {
                            "OrderNo": "2615",
                            "ReleaseNo": "*",
                            "SequenceNo": "*",
                            "OperationNo": 10,
                            "LineItemNo": 2,
                            "PartNo": "HM-B",
                            "IssueToLoc": None,
                            "QtyRemainingToReserve": 99,
                            "QtyAvailable": 0,
                        },
                        {
                            "OrderNo": "2615",
                            "ReleaseNo": "*",
                            "SequenceNo": "*",
                            "OperationNo": 10,
                            "LineItemNo": 3,
                            "PartNo": "YM-C",
                            "IssueToLoc": "U2",
                            "QtyRemainingToReserve": 5,
                            "QtyAvailable": 5,
                        },
                    ]
                },
            )
        if "OperationMaterialArray" in path and "OrderNo='2616'" in path:
            return httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "OrderNo": "2616",
                            "ReleaseNo": "*",
                            "SequenceNo": "*",
                            "OperationNo": 20,
                            "LineItemNo": 1,
                            "PartNo": "HM-A",
                            "IssueToLoc": "U1",
                            "QtyRemainingToReserve": 6,
                            "QtyAvailable": 50,
                        },
                        {
                            "OrderNo": "2616",
                            "ReleaseNo": "*",
                            "SequenceNo": "*",
                            "OperationNo": 20,
                            "LineItemNo": 2,
                            "PartNo": "YM-D",
                            "IssueToLoc": "U1",
                            "QtyRemainingToReserve": 1,
                            "QtyAvailable": 0,
                        },
                    ]
                },
            )
        if "OperationMaterialArray" in path and "OrderNo='2617'" in path:
            return httpx.Response(500, text="Released operation should be ignored")
        if path.endswith("/InventoryPartInStockHandling.svc/InventoryPartInStockSet"):
            stock_filter = request.url.params["$filter"]
            assert "LocationNo eq 'U1'" in stock_filter
            assert "AvailableQty gt 0" not in stock_filter
            assert "PartNo eq 'HM-A'" in stock_filter
            assert "PartNo eq 'HM-B'" in stock_filter
            assert "PartNo eq 'YM-C'" in stock_filter
            assert "PartNo eq 'YM-D'" in stock_filter
            assert request.url.params["$select"] == ",".join(
                ifs_client.STOCK_SELECT_FIELDS
            )
            return httpx.Response(
                200,
                json={
                    "@odata.count": 3,
                    "value": [
                        {
                            "Contract": "S01",
                            "PartNo": "HM-A",
                            "LocationNo": "U1",
                            "AvailableQty": 10,
                            "QtyOnhand": 20,
                            "ObjId": "stock-1",
                        },
                        {
                            "Contract": "S01",
                            "PartNo": "HM-B",
                            "LocationNo": "U1",
                            "AvailableQty": 0,
                            "QtyOnhand": 0,
                            "ObjId": "stock-2",
                        },
                        {
                            "Contract": "S01",
                            "PartNo": "YM-D",
                            "LocationNo": "U1",
                            "AvailableQty": 1,
                            "QtyOnhand": 1,
                            "ObjId": "stock-3",
                        },
                    ],
                },
            )
        return httpx.Response(404, text=f"Unexpected URL: {request.url}")

    async def run() -> dict:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(recorder.wrap(handler))
        ) as client:
            return await fetch_label_material_availability(
                settings,
                client=client,
                access_token="test-token",
                concurrency=1,
            )

    payload = asyncio.run(run())

    request_paths = [unquote(request.url.raw_path.decode()) for request in requests]
    assert not any("OrderNo='2617'" in path for path in request_paths)
    assert payload["summary"]["monitor_only"] is True
    assert payload["summary"]["material_prefixes"] == ["HM", "YM"]
    assert payload["summary"]["active_operation_status"] == "InProcess"
    assert payload["summary"]["blocking_stock_field"] == "AvailableQty"
    assert payload["summary"]["demand_field"] == "QtyRemainingToReserve"
    assert payload["summary"]["source_operation_count"] == 3
    assert payload["summary"]["operation_count"] == 2
    assert payload["summary"]["checked_row_count"] == 5
    assert payload["summary"]["blocked_row_count"] == 2
    assert payload["summary"]["blocked_parts"] == ["HM-A"]
    assert payload["summary"]["status_counts"] == {
        "blocked_insufficient_u1_available": 2,
        "ignored_non_u1_issue_location": 1,
        "issue_location_unknown": 1,
        "ok": 1,
    }
    assert payload["part_summaries"] == [
        {
            "part_no": "HM-A",
            "u1_demand_qty_remaining_to_reserve": 13,
            "u1_available_qty": 10,
            "u1_qty_onhand": 20,
            "u1_shortage_qty": 3,
            "is_blocked": True,
        },
        {
            "part_no": "HM-B",
            "u1_demand_qty_remaining_to_reserve": 0,
            "u1_available_qty": 0,
            "u1_qty_onhand": 0,
            "u1_shortage_qty": 0,
            "is_blocked": False,
        },
        {
            "part_no": "YM-C",
            "u1_demand_qty_remaining_to_reserve": 0,
            "u1_available_qty": 0,
            "u1_qty_onhand": 0,
            "u1_shortage_qty": 0,
            "is_blocked": False,
        },
        {
            "part_no": "YM-D",
            "u1_demand_qty_remaining_to_reserve": 1,
            "u1_available_qty": 1,
            "u1_qty_onhand": 1,
            "u1_shortage_qty": 0,
            "is_blocked": False,
        },
    ]
    assert [row["part_no"] for row in payload["blocked_rows"]] == ["HM-A", "HM-A"]
    assert {row["order_no"] for row in payload["blocked_rows"]} == {"2615", "2616"}
    by_part = {row["part_no"]: row for row in payload["checked_rows"]}
    assert by_part["HM-B"]["status"] == "issue_location_unknown"
    assert by_part["YM-C"]["status"] == "ignored_non_u1_issue_location"
    assert by_part["YM-D"]["status"] == "ok"
    assert by_part["YM-D"]["material_qty_available_reference"] == 0


def test_fetch_planning_used_hm02_materials_collects_visible_order_materials():
    requests: list[httpx.Request] = []
    recorder = RequestRecorder(requests)
    settings = Settings(ifs_base_url="https://ifs.example.com")

    def handler(request: httpx.Request) -> httpx.Response:
        path = unquote(request.url.raw_path.decode()).split("?", 1)[0]
        if "GetOperations" in path and "OrderNo='2579'" in path:
            return httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "OrderNo": "2579",
                            "ReleaseNo": "*",
                            "SequenceNo": "*",
                            "OperationNo": 10,
                        },
                        {
                            "OrderNo": "2579",
                            "ReleaseNo": "*",
                            "SequenceNo": "*",
                            "OperationNo": 1,
                        },
                        {
                            "OrderNo": "2579",
                            "ReleaseNo": "*",
                            "SequenceNo": "*",
                            "OperationNo": 10,
                        },
                    ]
                },
            )
        if "GetOperations" in path and "OrderNo='2580'" in path:
            return httpx.Response(200, json={"value": []})
        if "OperationNo=10" in path:
            return httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "OrderNo": "2579",
                            "ReleaseNo": "*",
                            "SequenceNo": "*",
                            "OperationNo": 10,
                            "LineItemNo": 2,
                            "PartNo": "HM-03-S",
                        },
                        {
                            "OrderNo": "2579",
                            "ReleaseNo": "*",
                            "SequenceNo": "*",
                            "OperationNo": 10,
                            "LineItemNo": 2,
                            "PartNo": "HM-03-S",
                        },
                    ]
                },
            )
        if "OperationNo=1" in path:
            return httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "OrderNo": "2579",
                            "ReleaseNo": "*",
                            "SequenceNo": "*",
                            "OperationNo": 1,
                            "LineItemNo": 3,
                            "PartNo": "HM-04-P",
                        },
                        {
                            "OrderNo": "2579",
                            "ReleaseNo": "*",
                            "SequenceNo": "*",
                            "OperationNo": 1,
                            "LineItemNo": 4,
                            "PartNo": "",
                        },
                    ]
                },
            )
        return httpx.Response(404, text="Unexpected URL")

    async def run() -> dict:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(recorder.wrap(handler))
        ) as client:
            return await fetch_planning_used_hm02_materials(
                settings,
                ["2579", "2579", "0", "2580", ""],
                client=client,
                access_token="test-token",
                concurrency=2,
            )

    summary = asyncio.run(run())

    assert summary["planning_order_count"] == 2
    assert summary["planning_operation_count"] == 2
    assert summary["planning_used_material_count"] == 2
    assert summary["planning_used_part_count"] == 2
    assert summary["planning_used_parts"] == ["HM-03-S", "HM-04-P"]
    assert summary["planning_used_hm02_part_count"] == 2
    assert summary["planning_used_hm02_parts"] == ["HM-03-S", "HM-04-P"]
    assert [row["PartNo"] for row in summary["planning_used_materials"]] == [
        "HM-03-S",
        "HM-04-P",
    ]
    assert len(requests) == 4
