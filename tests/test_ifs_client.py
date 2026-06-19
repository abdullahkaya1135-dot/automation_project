import asyncio
from urllib.parse import unquote

import httpx
import pytest
from openpyxl import Workbook

from app import config
from app.config import Settings
from app.integrations.ifs_client import (
    IFSClientError,
    fetch_operation_hm02_materials,
    fetch_pet_ongoing_operations,
    fetch_planning_used_hm02_materials,
    fetch_shop_order_operations,
    fetch_u1_hm02_stock,
    fetch_used_hm02_materials,
    find_u1_return_candidates,
    obtain_access_token,
    return_candidate_stock_rows,
    serialize_material_row,
    serialize_operation_row,
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
):
    monkeypatch.setattr(config, "load_dotenv", lambda **_: None)
    monkeypatch.setenv("IFS_PART_PREFIXES", "HM-03, HM-04, HM-03")
    monkeypatch.setenv("IFS_PART_PREFIX", "HM-99")

    settings = config.get_settings(validate=False)

    assert settings.ifs_part_prefix == "HM-99"
    assert settings.ifs_part_prefixes == ("HM-03", "HM-04")

    monkeypatch.delenv("IFS_PART_PREFIXES", raising=False)
    settings = config.get_settings(validate=False)

    assert settings.ifs_part_prefixes == ("HM-99",)


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
    assert "Selection=IfsApp.ShopFloorWorkbenchHandling.DisListFilterSelection'Ongoing'" in first_path
    assert "DispatchRule=IfsApp.ShopFloorWorkbenchHandling.DispatchRule'AsScheduled'" in first_path
    assert "WorkCenterCode=IfsApp.ShopFloorWorkbenchHandling.WorkCenterCodeShopFloor'InternalWorkCenter'" in first_path
    assert "CompanyId='C01'" in first_path
    assert requests[0].url.params["$select"] == (
        "OrderNo,ReleaseNo,SequenceNo,OperationNo,Contract,WorkCenterNo,"
        "PartNo,PartNoDesc,PreferredResourceId,OperationNoDesc,RemainingQty"
    )
    assert requests[0].url.params["$top"] == "1000"
    assert str(requests[1].url) == "https://ifs.example.com/next-operation-page"


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
    assert "FilterBy=IfsApp.ShopFloorWorkbenchHandling.DispatchListFilterBy'ShopOrder'" in path
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
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200))) as client:
            await fetch_operation_hm02_materials(
                settings,
                {"OrderNo": "2615", "ReleaseNo": "*", "OperationNo": 10},
                client=client,
                access_token="test-token",
            )

    with pytest.raises(IFSClientError, match="SequenceNo"):
        asyncio.run(run())


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


def test_find_u1_return_candidates_compares_stock_against_used_materials(tmp_path):
    requests: list[httpx.Request] = []
    planning_path = tmp_path / "planning.xlsx"
    _create_planning_workbook(planning_path, ["2579"])
    settings = Settings(
        ifs_base_url="https://ifs.example.com",
        timezone="Europe/Istanbul",
        production_planning_path=str(planning_path),
    )

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        path = unquote(request.url.raw_path.decode()).split("?", 1)[0]
        if "InventoryPartInStockSet" in path:
            return httpx.Response(
                200,
                json={
                    "value": [
                        {"PartNo": "HM-02-A", "LotBatchNo": "USED"},
                        {"PartNo": "HM-03-B", "LotBatchNo": "PLANNED"},
                        {"PartNo": "HM-04-C", "LotBatchNo": "L1"},
                    ]
                },
            )
        if "GetOperations" in path and "ShopOrder" in path:
            return httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "OrderNo": "2579",
                            "ReleaseNo": "*",
                            "SequenceNo": "*",
                            "OperationNo": 20,
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
                            "PartNo": "HM-02-A",
                        }
                    ]
                },
            )
        if "OperationMaterialArray" in path and "OrderNo='2579'" in path:
            return httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "OrderNo": "2579",
                            "OperationNo": 20,
                            "PartNo": "HM-03-B",
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

    assert len(requests) == 5
    assert summary["generated_at"]
    assert summary["stock_count"] == 3
    assert summary["operation_count"] == 1
    assert summary["active_used_material_count"] == 1
    assert summary["active_used_part_count"] == 1
    assert summary["active_used_hm02_part_count"] == 1
    assert summary["planning_order_count"] == 1
    assert summary["planning_operation_count"] == 1
    assert summary["planning_used_material_count"] == 1
    assert summary["planning_used_part_count"] == 1
    assert summary["planning_used_hm02_part_count"] == 1
    assert summary["used_material_count"] == 2
    assert summary["used_part_count"] == 2
    assert summary["used_hm02_part_count"] == 2
    assert summary["return_candidate_count"] == 1
    assert summary["used_parts"] == ["HM-02-A", "HM-03-B"]
    assert summary["used_hm02_parts"] == ["HM-02-A", "HM-03-B"]
    assert summary["return_candidates"] == [
        {"PartNo": "HM-04-C", "LotBatchNo": "L1"},
    ]
    assert summary["used_materials"] == [
        {"OrderNo": "2615", "OperationNo": 10, "PartNo": "HM-02-A"},
        {"OrderNo": "2579", "OperationNo": 20, "PartNo": "HM-03-B"},
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
