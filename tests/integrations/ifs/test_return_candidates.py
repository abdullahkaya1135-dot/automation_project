from __future__ import annotations

import asyncio
from urllib.parse import unquote

import httpx

from app.core.config import Settings
from app.integrations.ifs.client import (
    find_u1_return_candidates,
    return_candidate_stock_rows,
    used_hm02_part_numbers,
)

from .helpers import RequestRecorder, create_planning_workbook


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


def test_find_u1_return_candidates_excludes_active_and_stopped_used_materials(
    tmp_path,
):
    requests: list[httpx.Request] = []
    recorder = RequestRecorder(requests)
    planning_path = tmp_path / "planning.xlsx"
    create_planning_workbook(planning_path, [])
    settings = Settings(
        ifs_base_url="https://ifs.example.com",
        timezone="Europe/Istanbul",
        production_planning_path=str(planning_path),
    )
    date_from = "2026-05-24"
    date_to = "2026-07-23"

    def handler(request: httpx.Request) -> httpx.Response:
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
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(recorder.wrap(handler))
        ) as client:
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
