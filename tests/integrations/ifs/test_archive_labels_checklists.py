from __future__ import annotations

import asyncio
import base64
from urllib.parse import unquote

import httpx

import app.integrations.ifs.client as ifs_client
from app.core.config import Settings
from app.integrations.ifs.client import (
    fetch_package_label_checklist,
)

from .helpers import RequestRecorder


def test_fetch_package_label_checklist_filters_sorts_and_enriches_machine():
    requests: list[httpx.Request] = []
    recorder = RequestRecorder(requests)
    settings = Settings(ifs_base_url="https://ifs.example.com")

    def handler(request: httpx.Request) -> httpx.Response:
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
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(recorder.wrap(handler))
        ) as client:
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


def test_fetch_package_label_checklist_queries_stock_and_enriches_operations():
    requests: list[httpx.Request] = []
    recorder = RequestRecorder(requests)
    settings = Settings(ifs_base_url="https://ifs.example.com")

    def handler(request: httpx.Request) -> httpx.Response:
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
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(recorder.wrap(handler))
        ) as client:
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
    recorder = RequestRecorder(requests)
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
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(recorder.wrap(handler))
        ) as client:
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
    recorder = RequestRecorder(requests)
    settings = Settings(ifs_base_url="https://ifs.example.com")

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
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(recorder.wrap(handler))
        ) as client:
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
