import asyncio
import base64
import logging
from datetime import date as Date
from urllib.parse import unquote

import httpx
import pytest
from openpyxl import Workbook

import app.core.config as config
import app.integrations.ifs.client as ifs_client
from app.core.config import Settings
from app.integrations.ifs.client import (
    IFSClientError,
    fetch_inventory_part_descriptions,
    fetch_operation_history_rows,
    fetch_operation_hm02_materials,
    fetch_package_label_checklist,
    fetch_pet_ongoing_operations,
    fetch_pet_stopped_operations,
    fetch_planning_used_hm02_materials,
    fetch_production_label_stock_rows,
    fetch_shop_order_operation_actual_rows,
    fetch_shop_order_operations,
    fetch_u1_hm02_stock,
    fetch_used_hm02_materials,
    find_u1_return_candidates,
    obtain_access_token,
    return_candidate_stock_rows,
    serialize_material_row,
    serialize_operation_row,
    serialize_package_label_checklist_row,
    serialize_stock_row,
    used_hm02_part_numbers,
)

MULTI_PREFIX_FILTER = (
    "(startswith(PartNo,'HM-02') or startswith(PartNo,'HM-03') "
    "or startswith(PartNo,'HM-04'))"
)


def _create_planning_workbook(path, values: list[object]) -> None:
    workbook = Workbook()
    worksheet = workbook.active
    for row_index, value in enumerate(values, start=1):
        worksheet.cell(row=row_index, column=1, value=value)
    workbook.save(path)
    workbook.close()


def test_get_settings_expands_default_hm02_prefix_to_configured_prefixes(monkeypatch):
    monkeypatch.setattr(config, "load_dotenv", lambda **_: None)
    monkeypatch.delenv("IFS_PART_PREFIXES", raising=False)
    monkeypatch.setenv("IFS_PART_PREFIX", "HM-02")

    settings = config.get_settings(validate=False)

    assert settings.ifs_part_prefix == "HM-02"
    assert settings.ifs_part_prefixes == ("HM-02", "HM-03", "HM-04")


def test_get_settings_accepts_new_prefix_list_and_custom_legacy_prefix(
    monkeypatch,
    caplog,
):
    monkeypatch.setattr(config, "load_dotenv", lambda **_: None)
    monkeypatch.setenv("IFS_PART_PREFIXES", "HM-03, HM-04, HM-03")
    monkeypatch.setenv("IFS_PART_PREFIX", "HM-99")
    caplog.set_level(logging.INFO, logger="app.core.config")

    settings = config.get_settings(validate=False)

    assert settings.ifs_part_prefix == "HM-99"
    assert settings.ifs_part_prefixes == ("HM-03", "HM-04")
    assert not [record for record in caplog.records if record.name == "app.core.config"]

    caplog.clear()
    monkeypatch.delenv("IFS_PART_PREFIXES", raising=False)
    settings = config.get_settings(validate=False)

    assert settings.ifs_part_prefixes == ("HM-99",)
    records = [record for record in caplog.records if record.name == "app.core.config"]
    assert len(records) == 1
    assert records[0].legacy_setting == "IFS_PART_PREFIX"
    assert records[0].replacement_setting == "IFS_PART_PREFIXES"
    assert records[0].legacy_prefix_count == 1
    assert "HM-99" not in records[0].getMessage()
    assert "HM-99" not in caplog.text


def test_part_no_prefix_filter_logs_direct_legacy_prefix_fallback(caplog):
    settings = Settings(ifs_part_prefix="HM-99", ifs_part_prefixes=())
    caplog.set_level(logging.INFO, logger="app.integrations.ifs.client")

    assert ifs_client._part_no_prefix_filter(settings) == "startswith(PartNo,'HM-99')"

    records = [
        record
        for record in caplog.records
        if record.name == "app.integrations.ifs.client"
    ]
    assert len(records) == 1
    assert records[0].legacy_setting == "IFS_PART_PREFIX"
    assert records[0].replacement_setting == "IFS_PART_PREFIXES"
    assert records[0].legacy_prefix_count == 1
    assert "HM-99" not in records[0].getMessage()
    assert "HM-99" not in caplog.text


def test_fetch_u1_hm02_stock_uses_filter_and_follows_next_link():
    requests: list[httpx.Request] = []
    settings = Settings(ifs_base_url="https://ifs.example.com")

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.headers["authorization"] == "Bearer test-token"
        if len(requests) == 1:
            return httpx.Response(
                200,
                json={
                    "value": [{"PartNo": "HM-02-A", "LotBatchNo": "L1"}],
                    "@odata.nextLink": "https://ifs.example.com/next-stock-page",
                },
            )
        return httpx.Response(
            200,
            json={"value": [{"PartNo": "HM-03-B", "LotBatchNo": "L2"}]},
        )

    async def run() -> list[dict]:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await fetch_u1_hm02_stock(
                settings,
                client=client,
                access_token="test-token",
            )

    rows = asyncio.run(run())

    assert rows == [
        {"PartNo": "HM-02-A", "LotBatchNo": "L1"},
        {"PartNo": "HM-03-B", "LotBatchNo": "L2"},
    ]
    assert len(requests) == 2
    assert requests[0].url.path.endswith(
        "/InventoryPartInStockHandling.svc/InventoryPartInStockSet"
    )
    assert requests[0].url.params["$filter"] == (
        f"Contract eq 'S01' and {MULTI_PREFIX_FILTER} "
        "and LocationNo eq 'U1' and AvailableQty gt 0"
    )
    assert "Contract%20eq%20" in requests[0].url.query.decode()
    assert "Contract+eq+" not in requests[0].url.query.decode()
    assert requests[0].url.params["$expand"] == "PartNoRef($select=Description)"
    assert requests[0].url.params["$top"] == "1000"
    assert str(requests[1].url) == "https://ifs.example.com/next-stock-page"


def test_fetch_package_label_checklist_filters_sorts_and_enriches_machine():
    requests: list[httpx.Request] = []
    settings = Settings(ifs_base_url="https://ifs.example.com")

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.headers["authorization"] == "Bearer test-token"
        path = unquote(request.url.raw_path.decode()).split("?", 1)[0]
        if path.endswith("/InventoryPartInStockHandling.svc/InventoryPartInStockSet"):
            assert request.url.params["$filter"] == (
                "Contract eq 'S01' and (startswith(PartNo,'MM') "
                "or startswith(PartNo,'YM')) "
                "and not startswith(PartNo,'MM-PET') "
                "and startswith(LocationNo,'U01') and QtyOnhand gt 0"
            )
            assert request.url.params["$orderby"] == (
                "HandlingUnitId asc,PartNo asc,LotBatchNo asc"
            )
            return httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "Contract": "S01",
                            "PartNo": "MM-AAA",
                            "PartNoDesc": "Product A",
                            "LocationNo": "U01",
                            "QtyOnhand": 12,
                            "AvailableQty": 10,
                            "UoM": "pcs",
                            "LotBatchNo": "2758-*-*-1",
                            "HandlingUnitId": "HU-2",
                            "ObjId": "obj-2",
                        },
                        {
                            "Contract": "S01",
                            "PartNo": "MM-PET-SKIP",
                            "LocationNo": "U01",
                            "QtyOnhand": 1,
                            "LotBatchNo": "2766-*-*-1",
                            "HandlingUnitId": "HU-0",
                            "ObjId": "obj-skip",
                        },
                        {
                            "Contract": "S01",
                            "PartNo": "MM-BBB",
                            "PartNoDesc": "Product B",
                            "LocationNo": "U01A",
                            "QtyOnhand": 24,
                            "AvailableQty": 24,
                            "UoM": "pcs",
                            "LotBatchNo": "2800-*-*-1",
                            "HandlingUnitId": "HU-1",
                            "ObjId": "obj-1",
                        },
                        {
                            "Contract": "S01",
                            "PartNo": "YM-CCC",
                            "PartNoDesc": "Product C",
                            "LocationNo": "U01B",
                            "QtyOnhand": 8,
                            "AvailableQty": 8,
                            "UoM": "pcs",
                            "LotBatchNo": "2820-*-*-1",
                            "HandlingUnitId": "HU-3",
                            "ObjId": "obj-3",
                        },
                    ],
                    "@odata.count": 4,
                },
            )
        if "GetOperations" in path and "OrderNo='2758'" in path:
            return httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "OrderNo": "2758",
                            "ReleaseNo": "*",
                            "SequenceNo": "*",
                            "OperationNo": 20,
                            "PartNo": "MM-AAA",
                            "PartNoDesc": "Product A",
                            "PreferredResourceId": "401",
                            "WorkCenterNo": "WC-A",
                        }
                    ]
                },
            )
        if "GetOperations" in path and "OrderNo='2800'" in path:
            return httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "OrderNo": "2800",
                            "ReleaseNo": "*",
                            "SequenceNo": "*",
                            "OperationNo": 20,
                            "PartNo": "MM-BBB",
                            "PreferredResourceId": "302",
                            "WorkCenterNo": "WC-B",
                        },
                        {
                            "OrderNo": "2800",
                            "ReleaseNo": "*",
                            "SequenceNo": "*",
                            "OperationNo": 10,
                            "PartNo": "MM-BBB",
                            "PreferredResourceId": "301",
                            "WorkCenterNo": "WC-B",
                        },
                    ]
                },
            )
        if "GetOperations" in path and "OrderNo='2820'" in path:
            return httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "OrderNo": "2820",
                            "ReleaseNo": "*",
                            "SequenceNo": "*",
                            "OperationNo": 20,
                            "PartNo": "YM-CCC",
                            "PartNoDesc": "Product C",
                            "PreferredResourceId": "501",
                            "WorkCenterNo": "WC-C",
                        }
                    ]
                },
            )
        return httpx.Response(404, text=f"Unexpected URL: {request.url}")

    async def run() -> dict:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await fetch_package_label_checklist(
                settings,
                client=client,
                access_token="test-token",
                page_size=100,
                concurrency=1,
            )

    payload = asyncio.run(run())

    assert payload["summary"]["source_stock_count"] == 4
    assert payload["summary"]["excluded_count"] == 1
    assert payload["summary"]["stock_count"] == 3
    assert payload["summary"]["row_count"] == 3
    assert payload["summary"]["job_order_count"] == 3
    assert payload["summary"]["operation_count"] == 4
    assert payload["summary"]["matched_count"] == 2
    assert payload["summary"]["ambiguous_count"] == 1
    assert payload["summary"]["operation_lookup_failed_count"] == 0
    assert payload["summary"]["operation_lookup_failed_orders"] == []
    assert [row["handling_unit_id"] for row in payload["rows"]] == [
        "HU-1",
        "HU-2",
        "HU-3",
    ]
    assert payload["rows"][0]["job_order"] == "2800"
    assert payload["rows"][0]["machine_code"] is None
    assert payload["rows"][0]["operation_no"] is None
    assert payload["rows"][0]["operation_ambiguous"] is True
    assert payload["rows"][1]["job_order"] == "2758"
    assert payload["rows"][1]["machine_code"] == "401"
    assert payload["rows"][1]["operation_match_status"] == "matched"
    assert payload["rows"][2]["part_no"] == "YM-CCC"
    assert payload["rows"][2]["job_order"] == "2820"
    assert payload["rows"][2]["machine_code"] == "501"
    assert payload["rows"][2]["operation_match_status"] == "matched"


def test_fetch_u1_hm02_stock_obtains_oauth_token_when_needed():
    requests: list[httpx.Request] = []
    settings = Settings(
        ifs_base_url="https://ifs.example.com",
        ifs_token_url="https://ifs.example.com/token",
        ifs_client_id="client-id",
        ifs_client_secret="client-secret",
        ifs_username="user",
        ifs_password="pass",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/token":
            form = httpx.QueryParams(request.content.decode())
            assert form["grant_type"] == "password"
            assert form["client_id"] == "client-id"
            assert form["client_secret"] == "client-secret"
            assert form["username"] == "user"
            assert form["password"] == "pass"
            assert "authorization" not in request.headers
            return httpx.Response(200, json={"access_token": "oauth-token"})

        assert request.headers["authorization"] == "Bearer oauth-token"
        return httpx.Response(200, json={"value": [{"PartNo": "HM-02-A"}]})

    async def run() -> list[dict]:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await fetch_u1_hm02_stock(settings, client=client)

    rows = asyncio.run(run())

    assert rows == [{"PartNo": "HM-02-A"}]
    assert [request.url.path for request in requests] == [
        "/token",
        "/main/ifsapplications/projection/v1/InventoryPartInStockHandling.svc/InventoryPartInStockSet",
    ]


def test_obtain_access_token_supports_password_grant():
    requests: list[httpx.Request] = []
    settings = Settings(
        ifs_token_url="https://ifs.example.com/token",
        ifs_client_id="client-id",
        ifs_client_secret="client-secret",
        ifs_username="user",
        ifs_password="pass",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        form = httpx.QueryParams(request.content.decode())
        assert form["grant_type"] == "password"
        assert form["client_id"] == "client-id"
        assert form["client_secret"] == "client-secret"
        assert form["username"] == "user"
        assert form["password"] == "pass"
        return httpx.Response(200, json={"access_token": "user-token"})

    async def run() -> str:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await obtain_access_token(settings, client=client)

    assert asyncio.run(run()) == "user-token"
    assert len(requests) == 1


def test_fetch_u1_hm02_stock_reports_ifs_http_errors():
    settings = Settings(ifs_base_url="https://ifs.example.com")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="Forbidden projection")

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await fetch_u1_hm02_stock(
                settings,
                client=client,
                access_token="test-token",
            )

    with pytest.raises(IFSClientError) as exc_info:
        asyncio.run(run())

    assert exc_info.value.status_code == 403
    assert "u1-hm02-stock" in str(exc_info.value)
    assert "Forbidden projection" in str(exc_info.value)


def test_fetch_pet_ongoing_operations_uses_dispatch_filter_and_follows_next_link():
    requests: list[httpx.Request] = []
    settings = Settings(ifs_base_url="https://ifs.example.com")

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
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
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
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


def test_fetch_pet_stopped_operations_uses_durus_interrupted_interval_window():
    requests: list[httpx.Request] = []
    settings = Settings(ifs_base_url="https://ifs.example.com")
    date_from = "2026-05-24"
    date_to = "2026-07-23"

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
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
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
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
    settings = Settings(ifs_base_url="https://ifs.example.com")

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
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
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
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
    settings = Settings(
        ifs_base_url="https://ifs.example.com",
        ifs_production_loss_query_start_date="2026-06-01",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
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
                    }
                ]
            },
        )

    async def run() -> list[dict]:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
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
        "RealStart ge 2026-06-01T00:00:00Z and "
        "(OrderNo eq '2579' or OrderNo eq '2580')"
    )
    assert requests[0].url.params["$select"] == (
        "OrderNo,PartDescription,RealStart,RealFinished,"
        "RealMachRunTime,InterruptionTime"
    )
    assert requests[0].url.params["$top"] == "1000"


def test_fetch_operation_hm02_materials_encodes_operation_key_and_paginates():
    requests: list[httpx.Request] = []
    settings = Settings(ifs_base_url="https://ifs.example.com")
    operation = {
        "OrderNo": "2615",
        "ReleaseNo": "*",
        "SequenceNo": "*",
        "OperationNo": 10,
    }

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
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
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
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


def test_fetch_operation_history_rows_filters_and_pages_by_skip_count():
    requests: list[httpx.Request] = []
    settings = Settings(
        ifs_base_url="https://ifs.example.com",
        timezone="Europe/Istanbul",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
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
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
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


def test_fetch_production_label_stock_rows_uses_stock_journey_query():
    requests: list[httpx.Request] = []
    settings = Settings(
        ifs_base_url="https://ifs.example.com",
        ifs_label_part_prefixes=("MM", "PM"),
    )

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
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
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
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


def test_fetch_package_label_checklist_queries_stock_and_enriches_operations():
    requests: list[httpx.Request] = []
    settings = Settings(ifs_base_url="https://ifs.example.com")

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.headers["authorization"] == "Bearer test-token"
        path = unquote(request.url.raw_path.decode()).split("?", 1)[0]
        if "InventoryPartInStockSet" in path:
            return httpx.Response(
                200,
                json={
                    "@odata.count": 3,
                    "value": [
                        {
                            "ObjId": "OBJ-1",
                            "Contract": "S01",
                            "PartNo": "MM-CAP001",
                            "PartNoDesc": "Cap 1",
                            "LocationNo": "U0101",
                            "QtyOnhand": 10,
                            "AvailableQty": 8,
                            "UoM": "PCS",
                            "LotBatchNo": "2579-L1",
                            "SerialNo": "*",
                            "ReceiptDate": "2026-06-24T05:00:00Z",
                            "HandlingUnitId": "HU-1",
                            "ConfigurationId": "*",
                            "EngChgLevel": "1",
                            "WaivDevRejNo": "*",
                            "ActivitySeq": 0,
                        },
                        {
                            "ObjId": "OBJ-2",
                            "Contract": "S01",
                            "PartNo": "MM-CAP002",
                            "PartNoDesc": "Cap 2",
                            "LocationNo": "U0102",
                            "QtyOnhand": 5,
                            "AvailableQty": 5,
                            "UoM": "PCS",
                            "LotBatchNo": "IGNORED-L1",
                            "ShopOrderNo": "2580",
                            "HandlingUnitId": "HU-2",
                        },
                        {
                            "ObjId": "OBJ-3",
                            "Contract": "S01",
                            "PartNo": "MM-CAP003",
                            "PartNoDesc": "Cap 3",
                            "LocationNo": "U0103",
                            "QtyOnhand": 7,
                            "AvailableQty": 7,
                            "UoM": "PCS",
                            "LotBatchNo": "2590",
                            "HandlingUnitId": "HU-3",
                        },
                    ],
                },
            )
        if "GetOperations" in path and "OrderNo='2579'" in path:
            return httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "OrderNo": "2579",
                            "OperationNo": 10,
                            "WorkCenterNo": "WC-X",
                            "PreferredResourceId": "M-X",
                            "PartNo": "MM-OTHER",
                        },
                        {
                            "OrderNo": "2579",
                            "OperationNo": 20,
                            "WorkCenterNo": "WC-1",
                            "PreferredResourceId": "M-10",
                            "PartNo": "MM-CAP001",
                            "PartNoDesc": "Cap 1",
                        },
                    ]
                },
            )
        if "GetOperations" in path and "OrderNo='2580'" in path:
            return httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "OrderNo": "2580",
                            "OperationNo": 10,
                            "WorkCenterNo": "WC-2",
                            "PreferredResourceId": "M-20",
                            "PartNo": "MM-OTHER-A",
                        },
                        {
                            "OrderNo": "2580",
                            "OperationNo": 20,
                            "WorkCenterNo": "WC-3",
                            "PreferredResourceId": "M-30",
                            "PartNo": "MM-OTHER-B",
                        },
                    ]
                },
            )
        if "GetOperations" in path and "OrderNo='2590'" in path:
            return httpx.Response(200, json={"value": []})
        return httpx.Response(404, text="Unexpected URL")

    async def run() -> dict:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await fetch_package_label_checklist(
                settings,
                client=client,
                access_token="test-token",
                page_size=5000,
                concurrency=3,
            )

    checklist = asyncio.run(run())

    stock_request = requests[0]
    assert stock_request.url.path.endswith(
        "/InventoryPartInStockHandling.svc/InventoryPartInStockSet"
    )
    assert stock_request.url.params["$filter"] == (
        "Contract eq 'S01' "
        "and (startswith(PartNo,'MM') or startswith(PartNo,'YM')) "
        "and not startswith(PartNo,'MM-PET') "
        "and startswith(LocationNo,'U01') "
        "and QtyOnhand gt 0"
    )
    assert stock_request.url.params["$select"] == (
        "Contract,PartNo,PartNoDesc,LocationNo,QtyOnhand,AvailableQty,UoM,"
        "LotBatchNo,SerialNo,ReceiptDate,HandlingUnitId,ConfigurationId,"
        "EngChgLevel,WaivDevRejNo,ActivitySeq,ObjId"
    )
    assert stock_request.url.params["$orderby"] == (
        "HandlingUnitId asc,PartNo asc,LotBatchNo asc"
    )
    assert stock_request.url.params["$count"] == "true"
    assert stock_request.url.params["$top"] == "5000"
    assert stock_request.url.params["$skip"] == "0"

    operation_paths = [
        unquote(request.url.raw_path.decode()).split("?", 1)[0]
        for request in requests
        if "GetOperations" in unquote(request.url.raw_path.decode())
    ]
    assert len(operation_paths) == 3
    assert any("OrderNo='2579'" in path for path in operation_paths)
    assert any("OrderNo='2580'" in path for path in operation_paths)
    assert any("OrderNo='2590'" in path for path in operation_paths)

    summary = checklist["summary"]
    assert summary["stock_count"] == 3
    assert summary["row_count"] == 3
    assert summary["job_order_count"] == 3
    assert summary["operation_count"] == 4
    assert summary["matched_count"] == 1
    assert summary["part_matched_count"] == 1
    assert summary["ambiguous_count"] == 1
    assert summary["not_found_count"] == 1
    assert summary["operation_lookup_failed_count"] == 0
    assert summary["operation_lookup_failed_orders"] == []
    assert summary["match_status_counts"] == {
        "matched": 1,
        "ambiguous": 1,
        "not_found": 1,
    }

    rows = checklist["rows"]
    assert rows[0]["job_order"] == "2579"
    assert rows[0]["receipt_date"] == "2026-06-24T05:00:00Z"
    assert rows[0]["machine_code"] == "M-10"
    assert rows[0]["work_center_no"] == "WC-1"
    assert rows[0]["operation_no"] == 20
    assert rows[0]["operation_match_status"] == "matched"
    assert rows[0]["operation_ambiguous"] is False
    assert rows[1]["job_order"] == "2580"
    assert rows[1]["machine_code"] is None
    assert rows[1]["work_center_no"] is None
    assert rows[1]["operation_no"] is None
    assert rows[1]["operation_match_status"] == "ambiguous"
    assert rows[1]["operation_ambiguous"] is True
    assert rows[1]["operation_match_count"] == 2
    assert rows[1]["machine_code_source"] == "unresolved"
    assert rows[1]["machine_resolution_status"] == "ambiguous"
    assert rows[1]["candidate_machine_codes"] == ["M-20", "M-30"]
    assert rows[1]["candidate_operation_nos"] == ["10", "20"]
    assert rows[2]["job_order"] == "2590"
    assert rows[2]["operation_match_status"] == "not_found"


def test_fetch_package_label_checklist_prefers_archive_xml_machine_for_ambiguous_operation():
    requests: list[httpx.Request] = []
    settings = Settings(ifs_base_url="https://ifs.example.com")
    xml_bytes = b"""
    <SIMSEK_PALET_ETIKETI_REP>
      <IS_EMRI_NO>2580</IS_EMRI_NO>
      <PAKET_ID>HU-2</PAKET_ID>
      <LOT_BATCH_NO>2580-L1</LOT_BATCH_NO>
      <ENVANTER_KODU>MM-CAP002</ENVANTER_KODU>
      <RESOURCE_ID>174</RESOURCE_ID>
    </SIMSEK_PALET_ETIKETI_REP>
    """
    encoded_file_data = base64.b64encode(xml_bytes).decode()

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        path = unquote(request.url.raw_path.decode()).split("?", 1)[0]
        if "InventoryPartInStockSet" in path:
            return httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "ObjId": "OBJ-1",
                            "Contract": "S01",
                            "PartNo": "MM-CAP002",
                            "PartNoDesc": "Cap 2",
                            "LocationNo": "U0102",
                            "QtyOnhand": 5,
                            "AvailableQty": 5,
                            "UoM": "PCS",
                            "LotBatchNo": "2580-L1",
                            "HandlingUnitId": "HU-2",
                        },
                    ],
                },
            )
        if request.method == "GET" and path.endswith("/ReportArchive.svc/ArchiveSet"):
            return httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "ResultKey": 101,
                            "ReportId": "SIMSEK_PALET_ETIKETI_REP",
                        }
                    ]
                },
            )
        if request.method == "POST" and path.endswith("/ReportArchive.svc/GetXml"):
            return httpx.Response(200, json={"value": "xml-objkey"})
        if request.method == "GET" and path.endswith(
            "/ReportArchive.svc/XmlVirtualset(Objkey='xml-objkey')/FileData"
        ):
            return httpx.Response(200, json={"value": encoded_file_data})
        if "GetOperations" in path and "OrderNo='2580'" in path:
            return httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "OrderNo": "2580",
                            "OperationNo": 10,
                            "PreferredResourceId": "M-20",
                            "PartNo": "MM-OTHER-A",
                        },
                        {
                            "OrderNo": "2580",
                            "OperationNo": 20,
                            "PreferredResourceId": "M-30",
                            "PartNo": "MM-OTHER-B",
                        },
                    ]
                },
            )
        return httpx.Response(404, text="Unexpected URL")

    async def run() -> dict:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await fetch_package_label_checklist(
                settings,
                client=client,
                access_token="test-token",
                page_size=5000,
                concurrency=2,
            )

    checklist = asyncio.run(run())

    assert any(
        "GetOperations" in unquote(request.url.raw_path.decode())
        for request in requests
    )
    summary = checklist["summary"]
    assert summary["archive_label_count"] == 1
    assert summary["archive_label_ifs_error"] is None
    assert summary["archive_label_matched_count"] == 1
    assert summary["archive_label_match_status_counts"] == {
        "matched_by_order_package": 1,
    }
    assert summary["archive_machine_resolved_count"] == 1
    assert summary["machine_unresolved_count"] == 0
    assert summary["machine_resolution_counts"] == {"archive_label": 1}

    row = checklist["rows"][0]
    assert row["operation_match_status"] == "ambiguous"
    assert row["machine_code"] == "174"
    assert row["machine_code_source"] == "archive_label"
    assert row["machine_resolution_status"] == "resolved"
    assert row["archive_label_machine_code"] == "174"
    assert row["archive_label_match_key"] == "order_package"
    assert row["archive_label_match_status"] == "matched_by_order_package"
    assert row["candidate_machine_codes"] == ["M-20", "M-30"]


def test_fetch_package_label_checklist_uses_operation_resource_fallback_for_machine(
    monkeypatch,
):
    settings = Settings(ifs_base_url="https://ifs.example.com")

    async def fake_archive_rows(*_args, **_kwargs):
        return []

    monkeypatch.setattr(
        ifs_client,
        "fetch_label_archive_event_rows",
        fake_archive_rows,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        path = unquote(request.url.raw_path.decode()).split("?", 1)[0]
        if "InventoryPartInStockSet" in path:
            return httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "ObjId": "OBJ-1",
                            "Contract": "S01",
                            "PartNo": "MM-CAP001",
                            "LocationNo": "U0101",
                            "QtyOnhand": 10,
                            "LotBatchNo": "2579-L1",
                            "HandlingUnitId": "HU-1",
                        },
                    ],
                },
            )
        if "GetOperations" in path and "OrderNo='2579'" in path:
            return httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "OrderNo": "2579",
                            "OperationNo": 20,
                            "WorkCenterNo": "WC-1",
                            "ResourceId": "174",
                            "PartNo": "MM-CAP001",
                        }
                    ]
                },
            )
        return httpx.Response(404, text="Unexpected URL")

    async def run() -> dict:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await fetch_package_label_checklist(
                settings,
                client=client,
                access_token="test-token",
            )

    row = asyncio.run(run())["rows"][0]

    assert row["operation_match_status"] == "matched"
    assert row["machine_code"] == "174"
    assert row["machine_code_source"] == "operation_match"
    assert row["operation_machine_code"] == "174"
    assert row["operation_machine_field"] == "ResourceId"


def test_fetch_package_label_checklist_resolves_ambiguous_same_machine_by_consensus(
    monkeypatch,
):
    settings = Settings(ifs_base_url="https://ifs.example.com")

    async def fake_archive_rows(*_args, **_kwargs):
        return []

    monkeypatch.setattr(
        ifs_client,
        "fetch_label_archive_event_rows",
        fake_archive_rows,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        path = unquote(request.url.raw_path.decode()).split("?", 1)[0]
        if "InventoryPartInStockSet" in path:
            return httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "ObjId": "OBJ-1",
                            "Contract": "S01",
                            "PartNo": "MM-CAP999",
                            "LocationNo": "U0101",
                            "QtyOnhand": 10,
                            "LotBatchNo": "2580-L1",
                            "HandlingUnitId": "HU-1",
                        },
                    ],
                },
            )
        if "GetOperations" in path and "OrderNo='2580'" in path:
            return httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "OrderNo": "2580",
                            "OperationNo": 10,
                            "PreferredResourceId": "174",
                            "PartNo": "MM-OTHER-A",
                        },
                        {
                            "OrderNo": "2580",
                            "OperationNo": 20,
                            "PreferredResourceId": "174",
                            "PartNo": "MM-OTHER-B",
                        },
                    ]
                },
            )
        return httpx.Response(404, text="Unexpected URL")

    async def run() -> dict:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await fetch_package_label_checklist(
                settings,
                client=client,
                access_token="test-token",
            )

    checklist = asyncio.run(run())
    row = checklist["rows"][0]

    assert row["operation_match_status"] == "matched_by_machine_consensus"
    assert row["operation_no"] == 10
    assert row["machine_code"] == "174"
    assert row["machine_code_source"] == "operation_consensus"
    assert row["machine_resolution_status"] == "resolved"
    assert row["operation_machine_code"] == "174"
    assert row["operation_machine_field"] == "PreferredResourceId"
    assert row["candidate_machine_codes"] == ["174"]
    assert row["candidate_operation_nos"] == ["10", "20"]
    assert checklist["summary"]["matched_count"] == 1
    assert checklist["summary"]["operation_consensus_count"] == 1
    assert checklist["summary"]["match_status_counts"] == {
        "matched_by_machine_consensus": 1,
    }
    assert checklist["summary"]["machine_resolution_counts"] == {
        "operation_consensus": 1,
    }


def test_fetch_package_label_checklist_keeps_rows_when_operation_lookup_fails():
    requests: list[httpx.Request] = []
    settings = Settings(ifs_base_url="https://ifs.example.com")

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        path = unquote(request.url.raw_path.decode()).split("?", 1)[0]
        if "InventoryPartInStockSet" in path:
            return httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "ObjId": "OBJ-1",
                            "Contract": "S01",
                            "PartNo": "MM-CAP001",
                            "PartNoDesc": "Cap 1",
                            "LocationNo": "U0101",
                            "QtyOnhand": 10,
                            "AvailableQty": 8,
                            "UoM": "PCS",
                            "LotBatchNo": "2579-L1",
                            "HandlingUnitId": "HU-1",
                        },
                        {
                            "ObjId": "OBJ-2",
                            "Contract": "S01",
                            "PartNo": "MM-CAP002",
                            "PartNoDesc": "Cap 2",
                            "LocationNo": "U0102",
                            "QtyOnhand": 5,
                            "AvailableQty": 5,
                            "UoM": "PCS",
                            "LotBatchNo": "2580-L1",
                            "HandlingUnitId": "HU-2",
                        },
                    ],
                },
            )
        if "GetOperations" in path and "OrderNo='2579'" in path:
            return httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "OrderNo": "2579",
                            "OperationNo": 20,
                            "WorkCenterNo": "WC-1",
                            "PreferredResourceId": "M-10",
                            "PartNo": "MM-CAP001",
                        }
                    ]
                },
            )
        if "GetOperations" in path and "OrderNo='2580'" in path:
            return httpx.Response(502, text="IFS operation timeout")
        return httpx.Response(404, text="Unexpected URL")

    async def run() -> dict:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await fetch_package_label_checklist(
                settings,
                client=client,
                access_token="test-token",
                page_size=5000,
                concurrency=2,
            )

    checklist = asyncio.run(run())

    operation_paths = [
        unquote(request.url.raw_path.decode()).split("?", 1)[0]
        for request in requests
        if "GetOperations" in unquote(request.url.raw_path.decode())
    ]
    assert any("OrderNo='2579'" in path for path in operation_paths)
    assert any("OrderNo='2580'" in path for path in operation_paths)

    summary = checklist["summary"]
    assert summary["row_count"] == 2
    assert summary["operation_count"] == 1
    assert summary["matched_count"] == 1
    assert summary["operation_lookup_failed_count"] == 1
    assert summary["operation_lookup_failed_orders"] == ["2580"]
    assert "2580" in summary["warning"]
    assert summary["match_status_counts"] == {
        "matched": 1,
        "lookup_failed": 1,
    }

    rows = checklist["rows"]
    assert rows[0]["job_order"] == "2579"
    assert rows[0]["operation_match_status"] == "matched"
    assert rows[0]["machine_code"] == "M-10"
    assert rows[1]["job_order"] == "2580"
    assert rows[1]["operation_match_status"] == "lookup_failed"
    assert rows[1]["machine_code"] is None
    assert rows[1]["operation_match_count"] == 0


def test_fetch_operation_history_rows_requests_each_date_applied_month_bucket():
    requests: list[httpx.Request] = []
    settings = Settings(
        ifs_base_url="https://ifs.example.com",
        timezone="Europe/Istanbul",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
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
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
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


def test_fetch_inventory_part_descriptions_queries_reference_inventory_part():
    requests: list[httpx.Request] = []
    settings = Settings(ifs_base_url="https://ifs.example.com")

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
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
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
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


def test_used_hm02_part_numbers_deduplicates_and_ignores_blank_values():
    used_parts = used_hm02_part_numbers(
        [
            {"PartNo": "HM-02-A"},
            {"PartNo": "HM-02-A"},
            {"PartNo": " HM-03-B "},
            {"PartNo": "HM-04-C"},
            {"PartNo": ""},
            {},
        ]
    )

    assert used_parts == {"HM-02-A", "HM-03-B", "HM-04-C"}


def test_return_candidate_stock_rows_excludes_used_parts_and_sorts_by_part_no():
    stock_rows = [
        {"PartNo": "HM-02-A", "LotBatchNo": "USED"},
        {"PartNo": "HM-04-C", "LotBatchNo": "L2"},
        {"PartNo": "HM-03-B", "LotBatchNo": "L1"},
    ]

    candidates = return_candidate_stock_rows(stock_rows, {"HM-02-A"})

    assert candidates == [
        {"PartNo": "HM-03-B", "LotBatchNo": "L1"},
        {"PartNo": "HM-04-C", "LotBatchNo": "L2"},
    ]


def test_fetch_used_hm02_materials_collects_materials_for_all_operations():
    requests: list[httpx.Request] = []
    settings = Settings(ifs_base_url="https://ifs.example.com")

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
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
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
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


def test_fetch_planning_used_hm02_materials_collects_visible_order_materials():
    requests: list[httpx.Request] = []
    settings = Settings(ifs_base_url="https://ifs.example.com")

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
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
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
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


def test_find_u1_return_candidates_excludes_active_and_stopped_used_materials(
    tmp_path,
):
    requests: list[httpx.Request] = []
    planning_path = tmp_path / "planning.xlsx"
    _create_planning_workbook(planning_path, [])
    settings = Settings(
        ifs_base_url="https://ifs.example.com",
        timezone="Europe/Istanbul",
        production_planning_path=str(planning_path),
    )
    date_from = "2026-05-24"
    date_to = "2026-07-23"

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        path = unquote(request.url.raw_path.decode()).split("?", 1)[0]
        if "InventoryPartInStockSet" in path:
            return httpx.Response(
                200,
                json={
                    "value": [
                        {"PartNo": "HM-02-RUNNING", "LotBatchNo": "ACTIVE"},
                        {"PartNo": "HM-03-DURAN", "LotBatchNo": "STOPPED"},
                        {"PartNo": "HM-04-FREE", "LotBatchNo": "FREE"},
                    ]
                },
            )
        if "GetDatesForInterval" in path:
            return httpx.Response(
                200,
                json={
                    "DateFrom": date_from,
                    "DateTo": date_to,
                    "value": {"DateFrom": date_from, "DateTo": date_to},
                },
            )
        if "GetOperations" in path and "DispListFilterId='DURUS'" in path:
            assert (
                "Selection=IfsApp.ShopFloorWorkbenchHandling."
                "DisListFilterSelection'Interrupted'"
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
                        }
                    ]
                },
            )
        if "OperationMaterialArray" in path and "OrderNo='2615'" in path:
            return httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "OrderNo": "2615",
                            "OperationNo": 10,
                            "PartNo": "HM-02-RUNNING",
                        }
                    ]
                },
            )
        if "OperationMaterialArray" in path and "OrderNo='2710'" in path:
            return httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "OrderNo": "2710",
                            "OperationNo": 30,
                            "PartNo": "HM-03-DURAN",
                        }
                    ]
                },
            )
        return httpx.Response(404, text="Unexpected URL")

    async def run() -> dict:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await find_u1_return_candidates(
                settings,
                client=client,
                access_token="test-token",
            )

    summary = asyncio.run(run())

    request_paths = [unquote(request.url.raw_path.decode()) for request in requests]
    assert any("GetDatesForInterval" in path for path in request_paths)
    assert any(
        "GetOperations" in path and "DispListFilterId='DURUS'" in path
        for path in request_paths
    )
    assert summary["generated_at"]
    assert summary["stock_count"] == 3
    assert summary["operation_count"] == 1
    assert summary["active_used_material_count"] == 1
    assert summary["active_used_part_count"] == 1
    assert summary["active_used_hm02_part_count"] == 1
    assert summary["stopped_operation_count"] == 1
    assert summary["stopped_used_material_count"] == 1
    assert summary["stopped_used_part_count"] == 1
    assert summary["stopped_used_hm02_part_count"] == 1
    assert summary["planning_order_count"] == 0
    assert summary["planning_operation_count"] == 0
    assert summary["planning_used_material_count"] == 0
    assert summary["planning_used_part_count"] == 0
    assert summary["planning_used_hm02_part_count"] == 0
    assert summary["used_material_count"] == 2
    assert summary["used_part_count"] == 2
    assert summary["used_hm02_part_count"] == 2
    assert summary["return_candidate_count"] == 1
    assert summary["used_parts"] == ["HM-02-RUNNING", "HM-03-DURAN"]
    assert summary["used_hm02_parts"] == ["HM-02-RUNNING", "HM-03-DURAN"]
    assert summary["return_candidates"] == [
        {"PartNo": "HM-04-FREE", "LotBatchNo": "FREE"},
    ]
    assert summary["used_materials"] == [
        {"OrderNo": "2615", "OperationNo": 10, "PartNo": "HM-02-RUNNING"},
        {"OrderNo": "2710", "OperationNo": 30, "PartNo": "HM-03-DURAN"},
    ]


def test_serialize_stock_row_uses_api_output_shape():
    payload = serialize_stock_row(
        {
            "Contract": "S01",
            "PartNo": "HM-02-A",
            "PartNoRef": {"Description": "Raw Material"},
            "LocationNo": "U1",
            "LotBatchNo": "L1",
            "AvailableQty": 12.5,
            "QtyOnhand": 15,
            "UoM": "kg",
            "ObjId": "obj-1",
        }
    )

    assert payload["contract"] == "S01"
    assert payload["part_no"] == "HM-02-A"
    assert payload["material_name"] == "Raw Material"
    assert payload["location_no"] == "U1"
    assert payload["lot_batch_no"] == "L1"
    assert payload["available_qty"] == 12.5
    assert payload["qty_onhand"] == 15
    assert payload["uom"] == "kg"
    assert payload["obj_id"] == "obj-1"


def test_serialize_package_label_checklist_row_uses_api_output_shape():
    payload = serialize_package_label_checklist_row(
        {
            "Contract": "S01",
            "PartNo": "MM-CAP001",
            "PartNoDesc": "Cap 1",
            "LocationNo": "U0101",
            "QtyOnhand": 10,
            "AvailableQty": 8,
            "UoM": "PCS",
            "LotBatchNo": "2579-L1",
            "SerialNo": "*",
            "ReceiptDate": "2026-06-24T05:00:00Z",
            "HandlingUnitId": 284844,
            "ConfigurationId": "*",
            "EngChgLevel": "1",
            "WaivDevRejNo": "*",
            "ActivitySeq": 0,
            "ObjId": "obj-1",
        }
    )

    assert payload == {
        "contract": "S01",
        "part_no": "MM-CAP001",
        "part_description": "Cap 1",
        "location_no": "U0101",
        "qty_onhand": 10,
        "available_qty": 8,
        "uom": "PCS",
        "lot_batch_no": "2579-L1",
        "serial_no": "*",
        "receipt_date": "2026-06-24T05:00:00Z",
        "handling_unit_id": "284844",
        "configuration_id": "*",
        "eng_chg_level": "1",
        "waiv_dev_rej_no": "*",
        "activity_seq": 0,
        "obj_id": "obj-1",
    }


def test_serialize_operation_row_uses_api_output_shape():
    payload = serialize_operation_row(
        {
            "OrderNo": "2615",
            "ReleaseNo": "*",
            "SequenceNo": "*",
            "OperationNo": 10,
            "Contract": "S01",
            "WorkCenterNo": "SP25",
            "PartNo": "MM-PET0048-12-024Y-025",
            "PartNoDesc": "Bottle",
            "PreferredResourceId": "135",
            "OperationNoDesc": "Run",
            "RemainingQty": 42,
        }
    )

    assert payload == {
        "order_no": "2615",
        "release_no": "*",
        "sequence_no": "*",
        "operation_no": 10,
        "contract": "S01",
        "work_center_no": "SP25",
        "part_no": "MM-PET0048-12-024Y-025",
        "part_description": "Bottle",
        "preferred_resource_id": "135",
        "operation_description": "Run",
        "remaining_qty": 42,
    }


def test_serialize_material_row_uses_api_output_shape():
    payload = serialize_material_row(
        {
            "OrderNo": "2615",
            "ReleaseNo": "*",
            "SequenceNo": "*",
            "LineItemNo": 2,
            "OperationNo": 10,
            "PartNo": "HM-02-01-01-525",
            "IssueToLoc": "U1",
            "QtyRequired": 25.578,
            "QtyAssigned": 0,
            "QtyIssued": 0,
            "QtyRemainingToReserve": 25.578,
            "QtyAvailable": 100.72,
            "PrintUnit": "kg",
            "SoPartNo": "MM-PET0048-12-024Y-025",
            "Cf_Tercihedilenkaynak": "135",
        }
    )

    assert payload == {
        "order_no": "2615",
        "release_no": "*",
        "sequence_no": "*",
        "line_item_no": 2,
        "operation_no": 10,
        "part_no": "HM-02-01-01-525",
        "issue_to_location": "U1",
        "qty_required": 25.578,
        "qty_assigned": 0,
        "qty_issued": 0,
        "qty_remaining_to_reserve": 25.578,
        "qty_available": 100.72,
        "print_unit": "kg",
        "produced_part_no": "MM-PET0048-12-024Y-025",
        "machine": "135",
    }
