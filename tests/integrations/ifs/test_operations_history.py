from __future__ import annotations

import asyncio
from urllib.parse import unquote

import httpx
import pytest

from app.core.config import Settings
from app.integrations.ifs.client import (
    IFSClientError,
    fetch_operation_history_rows,
    fetch_pet_ongoing_operations,
    fetch_pet_stopped_operations,
    fetch_shop_order_operation_actual_rows,
    fetch_shop_order_operations,
)

from .helpers import RequestRecorder


def test_fetch_pet_ongoing_operations_uses_dispatch_filter_and_follows_next_link():
    requests: list[httpx.Request] = []
    recorder = RequestRecorder(requests)
    settings = Settings(ifs_base_url="https://ifs.example.com")

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
                            "OperationNo": 10,
                        }
                    ],
                    "@odata.nextLink": "https://ifs.example.com/next-operation-page",
                },
            )
        return httpx.Response(
            200,
            json={
                "value": [
                    {
                        "OrderNo": "2616",
                        "ReleaseNo": "*",
                        "SequenceNo": "*",
                        "OperationNo": 20,
                    }
                ]
            },
        )

    async def run() -> list[dict]:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(recorder.wrap(handler))
        ) as client:
            return await fetch_pet_ongoing_operations(
                settings,
                client=client,
                access_token="test-token",
            )

    rows = asyncio.run(run())

    assert rows == [
        {"OrderNo": "2615", "ReleaseNo": "*", "SequenceNo": "*", "OperationNo": 10},
        {"OrderNo": "2616", "ReleaseNo": "*", "SequenceNo": "*", "OperationNo": 20},
    ]
    assert len(requests) == 2
    first_path = unquote(requests[0].url.raw_path.decode()).split("?", 1)[0]
    assert first_path.startswith(
        "/main/ifsapplications/projection/v1/"
        "ShopFloorWorkbenchHandling.svc/GetOperations("
    )
    assert "Contract='S01'" in first_path
    assert "DispListFilterId='PET'" in first_path
    assert (
        "Selection=IfsApp.ShopFloorWorkbenchHandling.DisListFilterSelection'Ongoing'"
        in first_path
    )
    assert (
        "DispatchRule=IfsApp.ShopFloorWorkbenchHandling.DispatchRule'AsScheduled'"
        in first_path
    )
    assert (
        "WorkCenterCode=IfsApp.ShopFloorWorkbenchHandling.WorkCenterCodeShopFloor'InternalWorkCenter'"
        in first_path
    )
    assert "CompanyId='C01'" in first_path
    assert requests[0].url.params["$select"] == (
        "OrderNo,ReleaseNo,SequenceNo,OperationNo,Contract,WorkCenterNo,"
        "PartNo,PartNoDesc,PreferredResourceId,OperationNoDesc,RemainingQty"
    )
    assert requests[0].url.params["$top"] == "1000"
    assert str(requests[1].url) == "https://ifs.example.com/next-operation-page"


def test_fetch_pet_ongoing_operations_can_expand_inventory_part_pack_size():
    requests: list[httpx.Request] = []
    recorder = RequestRecorder(requests)
    settings = Settings(ifs_base_url="https://ifs.example.com")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "value": [
                    {
                        "OrderNo": "2615",
                        "ReleaseNo": "*",
                        "SequenceNo": "*",
                        "OperationNo": 10,
                        "InventoryPartRef": {
                            "PartNo": "MM-PET-2615",
                            "Cf_Palet_Ici_Miktar": 820,
                        },
                    }
                ]
            },
        )

    async def run() -> list[dict]:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(recorder.wrap(handler))
        ) as client:
            return await fetch_pet_ongoing_operations(
                settings,
                client=client,
                access_token="test-token",
                include_inventory_part_pack_size=True,
            )

    rows = asyncio.run(run())

    assert rows[0]["InventoryPartRef"]["Cf_Palet_Ici_Miktar"] == 820
    assert requests[0].url.params["$expand"] == (
        "InventoryPartRef($select=PartNo,Cf_Palet_Ici_Miktar)"
    )


def test_fetch_pet_stopped_operations_uses_durus_interrupted_interval_window():
    requests: list[httpx.Request] = []
    recorder = RequestRecorder(requests)
    settings = Settings(ifs_base_url="https://ifs.example.com")
    date_from = "2026-05-24"
    date_to = "2026-07-23"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer test-token"
        path = unquote(request.url.raw_path.decode()).split("?", 1)[0]
        if "GetDatesForInterval" in path:
            assert "StartOffset=-30" in path
            assert "EndOffset=30" in path
            return httpx.Response(
                200,
                json={
                    "DateFrom": date_from,
                    "DateTo": date_to,
                    "value": {"DateFrom": date_from, "DateTo": date_to},
                },
            )
        if "GetOperations" in path:
            assert "DispListFilterId='DURUS'" in path
            assert (
                "Selection=IfsApp.ShopFloorWorkbenchHandling."
                "DisListFilterSelection'Interrupted'"
            ) in path
            assert (
                "WorkCenterCode=IfsApp.ShopFloorWorkbenchHandling."
                "WorkCenterCodeShopFloor'InternalWorkCenter'"
            ) in path
            assert date_from in path
            assert date_to in path
            return httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "OrderNo": "2710",
                            "ReleaseNo": "*",
                            "SequenceNo": "*",
                            "OperationNo": 30,
                        }
                    ]
                },
            )
        return httpx.Response(404, text="Unexpected URL")

    async def run() -> list[dict]:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(recorder.wrap(handler))
        ) as client:
            return await fetch_pet_stopped_operations(
                settings,
                client=client,
                access_token="test-token",
            )

    rows = asyncio.run(run())

    assert rows == [
        {"OrderNo": "2710", "ReleaseNo": "*", "SequenceNo": "*", "OperationNo": 30}
    ]
    assert len(requests) == 2
    assert "GetDatesForInterval" in unquote(requests[0].url.raw_path.decode())
    assert "GetOperations" in unquote(requests[1].url.raw_path.decode())
    assert requests[1].url.params["$select"] == (
        "OrderNo,ReleaseNo,SequenceNo,OperationNo,Contract,WorkCenterNo,"
        "PartNo,PartNoDesc,PreferredResourceId,OperationNoDesc,RemainingQty"
    )
    assert requests[1].url.params["$top"] == "1000"


def test_fetch_pet_ongoing_operations_reports_ifs_http_errors():
    settings = Settings(ifs_base_url="https://ifs.example.com")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, text="Bad GetOperations parameters")

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await fetch_pet_ongoing_operations(
                settings,
                client=client,
                access_token="test-token",
            )

    with pytest.raises(IFSClientError) as exc_info:
        asyncio.run(run())

    assert exc_info.value.status_code == 400
    assert "pet-ongoing-operations" in str(exc_info.value)
    assert "Bad GetOperations parameters" in str(exc_info.value)


def test_fetch_shop_order_operations_uses_shop_order_filter():
    requests: list[httpx.Request] = []
    recorder = RequestRecorder(requests)
    settings = Settings(ifs_base_url="https://ifs.example.com")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "value": [
                    {
                        "OrderNo": "2579",
                        "ReleaseNo": "*",
                        "SequenceNo": "*",
                        "OperationNo": 10,
                    }
                ]
            },
        )

    async def run() -> list[dict]:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(recorder.wrap(handler))
        ) as client:
            return await fetch_shop_order_operations(
                settings,
                "2579",
                client=client,
                access_token="test-token",
            )

    rows = asyncio.run(run())

    assert rows == [
        {"OrderNo": "2579", "ReleaseNo": "*", "SequenceNo": "*", "OperationNo": 10}
    ]
    assert len(requests) == 1
    path = unquote(requests[0].url.raw_path.decode()).split("?", 1)[0]
    assert (
        "FilterBy=IfsApp.ShopFloorWorkbenchHandling.DispatchListFilterBy'ShopOrder'"
        in path
    )
    assert "DispListFilterId=null" in path
    assert "Selection=null" in path
    assert "OrderNo='2579'" in path
    assert "ReleaseNo='*'" in path
    assert "SequenceNo='*'" in path
    assert requests[0].url.params["$select"] == (
        "OrderNo,ReleaseNo,SequenceNo,OperationNo,Contract,WorkCenterNo,"
        "PartNo,PartNoDesc,PreferredResourceId,OperationNoDesc,RemainingQty"
    )
    assert requests[0].url.params["$top"] == "1000"


def test_fetch_shop_order_operation_actual_rows_uses_production_loss_query_projection():
    requests: list[httpx.Request] = []
    recorder = RequestRecorder(requests)
    settings = Settings(
        ifs_base_url="https://ifs.example.com",
        ifs_production_loss_query_start_date="2026-06-01",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "value": [
                    {
                        "OrderNo": "2579",
                        "PartDescription": "PET 28MM 35GR",
                        "RealStart": "2026-06-10T12:16:05Z",
                        "RealFinished": "2026-06-16T21:33:30Z",
                        "RealMachRunTime": 120,
                        "InterruptionTime": 5,
                    },
                    {
                        "OrderNo": "2580",
                        "PartDescription": "PET 24MM 29GR",
                        "RealStart": "2026-06-11T12:16:05Z",
                        "RealFinished": None,
                        "RealMachRunTime": 60,
                        "InterruptionTime": 0,
                    },
                ]
            },
        )

    async def run() -> list[dict]:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(recorder.wrap(handler))
        ) as client:
            return await fetch_shop_order_operation_actual_rows(
                settings,
                ["2579", "", "0", "2579", "2580"],
                client=client,
                access_token="test-token",
            )

    rows = asyncio.run(run())

    assert [row["OrderNo"] for row in rows] == ["2579", "2580"]
    assert len(requests) == 1
    first_path = unquote(requests[0].url.raw_path.decode()).split("?", 1)[0]
    assert first_path.endswith(
        "/main/ifsapplications/projection/v1/"
        "QueryProjectionPRODUCTIONLOSS.svc/PRODUCTIONLOSSSet"
    )
    assert requests[0].url.params["$filter"] == (
        "RealStart ge 2026-06-01T00:00:00Z and (OrderNo eq '2579' or OrderNo eq '2580')"
    )
    assert requests[0].url.params["$select"] == (
        "OrderNo,PartDescription,RealStart,RealFinished,"
        "RealMachRunTime,InterruptionTime"
    )
    assert requests[0].url.params["$top"] == "1000"


def test_fetch_operation_history_rows_filters_and_pages_by_skip_count():
    requests: list[httpx.Request] = []
    recorder = RequestRecorder(requests)
    settings = Settings(
        ifs_base_url="https://ifs.example.com",
        timezone="Europe/Istanbul",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer test-token"
        if request.url.params["$skip"] == "0":
            return httpx.Response(
                200,
                json={
                    "@odata.count": 3,
                    "value": [
                        {
                            "TransactionId": "T1",
                            "OrderNo": "WO-1",
                            "ResourceId": "174",
                            "PartNo": "MM-PET001",
                            "QtyComplete": 10,
                            "TimeOfProduction": "2026-06-08T08:15:00Z",
                        },
                        {
                            "TransactionId": "T2",
                            "OrderNo": "WO-2",
                            "ResourceId": "175",
                            "PartNo": "MM-PET002",
                            "QtyComplete": 20,
                            "TimeOfProduction": "2026-06-08T09:15:00Z",
                        },
                    ],
                },
            )
        return httpx.Response(
            200,
            json={
                "@odata.count": 3,
                "value": [
                    {
                        "TransactionId": "T2",
                        "OrderNo": "WO-2",
                        "ResourceId": "175",
                        "PartNo": "MM-PET002",
                        "QtyComplete": 20,
                        "TimeOfProduction": "2026-06-08T09:15:00Z",
                    },
                    {
                        "TransactionId": "T3",
                        "OrderNo": "WO-3",
                        "ResourceId": "176",
                        "PartNo": "MM-PET003",
                        "QtyComplete": 30,
                        "TimeOfProduction": "2026-06-08T10:15:00Z",
                    },
                ],
            },
        )

    async def run() -> list[dict]:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(recorder.wrap(handler))
        ) as client:
            return await fetch_operation_history_rows(
                settings,
                "2026-06-08",
                "2026-06-08",
                ("MM-PET", "MM-PREFORM"),
                client=client,
                access_token="test-token",
                page_size=2,
            )

    rows = asyncio.run(run())

    assert [row["TransactionId"] for row in rows] == ["T1", "T2", "T3"]
    assert len(requests) == 2
    assert requests[0].url.path.endswith(
        "/ShopFloorWorkbenchHandling.svc/Reference_OperationHistory"
    )
    assert requests[0].url.params["$filter"] == (
        "contains(Contract,'S01') "
        "and startswith(cast(DateApplied,Edm.String),'2026-06') "
        "and (startswith(PartNo,'MM-PET') or startswith(PartNo,'MM-PREFORM'))"
    )
    assert "TimeOfProduction ge" not in requests[0].url.params["$filter"]
    assert "QtyComplete gt" not in requests[0].url.params["$filter"]
    assert "OrderNo ne" not in requests[0].url.params["$filter"]
    assert "ResourceId ne" not in requests[0].url.params["$filter"]
    assert requests[0].url.params["$select"] == (
        "TransactionId,OrderNo,ReleaseNo,SequenceNo,OperationNo,Contract,"
        "WorkCenterNo,ResourceId,ResourceDescription,PartNo,DateApplied,"
        "TransactionDate,Dated,TimeOfProduction,QtyComplete,QtyScrapped,"
        "TransactionCode,OperStatusCode,OrderType"
    )
    assert requests[0].url.params["$orderby"] == "TransactionId asc"
    assert requests[0].url.params["$count"] == "true"
    assert requests[0].url.params["$top"] == "2"
    assert requests[0].url.params["$skip"] == "0"
    assert requests[1].url.params["$top"] == "2"
    assert requests[1].url.params["$skip"] == "2"


def test_fetch_operation_history_rows_requests_each_date_applied_month_bucket():
    requests: list[httpx.Request] = []
    recorder = RequestRecorder(requests)
    settings = Settings(
        ifs_base_url="https://ifs.example.com",
        timezone="Europe/Istanbul",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        filter_text = request.url.params["$filter"]
        if "'2026-05'" in filter_text:
            rows = [
                {"TransactionId": "MAY-1", "PartNo": "MM-PET001"},
                {"TransactionId": "DUP-1", "PartNo": "MM-PET001"},
            ]
        elif "'2026-06'" in filter_text:
            rows = [
                {"TransactionId": "DUP-1", "PartNo": "MM-PET001"},
                {"TransactionId": "JUN-1", "PartNo": "MM-PET001"},
            ]
        else:
            rows = []
        return httpx.Response(200, json={"@odata.count": len(rows), "value": rows})

    async def run() -> list[dict]:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(recorder.wrap(handler))
        ) as client:
            return await fetch_operation_history_rows(
                settings,
                "2026-05-31",
                "2026-06-01",
                ("MM-PET",),
                client=client,
                access_token="test-token",
                page_size=10,
            )

    rows = asyncio.run(run())

    filters = [request.url.params["$filter"] for request in requests]
    assert len(requests) == 2
    assert any(
        "startswith(cast(DateApplied,Edm.String),'2026-05')" in item for item in filters
    )
    assert any(
        "startswith(cast(DateApplied,Edm.String),'2026-06')" in item for item in filters
    )
    assert [row["TransactionId"] for row in rows] == ["MAY-1", "DUP-1", "JUN-1"]
