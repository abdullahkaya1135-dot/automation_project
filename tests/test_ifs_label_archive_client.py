import asyncio
import base64
import json
from urllib.parse import unquote

import httpx

from app.core.config import Settings
from app.integrations.ifs.client import (
    fetch_simsek_palet_etiketi_archive_labels,
    fetch_simsek_palet_etiketi_archive_rows,
    parse_simsek_palet_etiketi_rep_xml,
)


def test_fetch_simsek_palet_etiketi_archive_rows_queries_report_id():
    requests: list[httpx.Request] = []
    settings = Settings(ifs_base_url="https://ifs.example.com")

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.headers["authorization"] == "Bearer test-token"
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

    async def run() -> list[dict]:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await fetch_simsek_palet_etiketi_archive_rows(
                settings,
                client=client,
                access_token="test-token",
            )

    rows = asyncio.run(run())

    assert rows == [{"ResultKey": 101, "ReportId": "SIMSEK_PALET_ETIKETI_REP"}]
    assert len(requests) == 1
    assert requests[0].url.path.endswith("/ReportArchive.svc/ArchiveSet")
    assert requests[0].url.params["$filter"] == (
        "ReportId eq 'SIMSEK_PALET_ETIKETI_REP'"
    )
    assert "ResultKey" in requests[0].url.params["$select"]
    assert "ReportId" in requests[0].url.params["$select"]
    assert requests[0].url.params["$top"] == "1000"


def test_fetch_simsek_palet_etiketi_archive_labels_gets_xml_file_data():
    requests: list[httpx.Request] = []
    settings = Settings(ifs_base_url="https://ifs.example.com")
    xml_bytes = b"""
    <SIMSEK_PALET_ETIKETI_REP>
      <TARIH>2026-06-19T10:15:00</TARIH>
      <IC_ADEDI>48</IC_ADEDI>
      <RESOURCE_ID>SP25</RESOURCE_ID>
      <IS_EMRI_NO>2615</IS_EMRI_NO>
      <ENVANTER_KODU>MM-PET0048</ENVANTER_KODU>
      <ENVANTER_ADI>Pet Bottle</ENVANTER_ADI>
      <PAKET_ID>PKT-7</PAKET_ID>
      <LOT_BATCH_NO>LOT-42</LOT_BATCH_NO>
      <PALET_NO>PAL-3</PALET_NO>
      <SIRA_NO>9</SIRA_NO>
    </SIMSEK_PALET_ETIKETI_REP>
    """
    encoded_file_data = base64.b64encode(xml_bytes).decode()

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        path = unquote(request.url.raw_path.decode()).split("?", 1)[0]
        assert request.headers["authorization"] == "Bearer test-token"
        if request.method == "GET" and path.endswith(
            "/ReportArchive.svc/ArchiveSet"
        ):
            return httpx.Response(
                200,
                json={"value": [{"ResultKey": 101, "ReportId": "SIMSEK_PALET_ETIKETI_REP"}]},
            )
        if request.method == "POST" and path.endswith("/ReportArchive.svc/GetXml"):
            assert json.loads(request.content) == {"ResultKey": 101}
            return httpx.Response(200, json={"value": "xml-objkey"})
        if request.method == "GET" and path.endswith(
            "/ReportArchive.svc/XmlVirtualset(Objkey='xml-objkey')/FileData"
        ):
            return httpx.Response(200, json={"value": encoded_file_data})
        return httpx.Response(404, text=f"Unexpected {request.method} {path}")

    async def run() -> list[dict[str, str | None]]:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await fetch_simsek_palet_etiketi_archive_labels(
                settings,
                client=client,
                access_token="test-token",
                concurrency=1,
            )

    labels = asyncio.run(run())

    assert [request.method for request in requests] == ["GET", "POST", "GET"]
    assert labels == [
        {
            "job_order": "2615",
            "package_id": "PKT-7",
            "lot_batch_no": "LOT-42",
            "part_no": "MM-PET0048",
            "product_description": "Pet Bottle",
            "pallet_no": "PAL-3",
            "sequence_no": "9",
            "quantity": "48",
            "label_time": "2026-06-19T10:15:00",
            "machine_code": "SP25",
        }
    ]


def test_parse_simsek_palet_etiketi_rep_xml_reads_namespaced_fields():
    xml_text = """
    <root xmlns:r="urn:test">
      <r:SIMSEK_PALET_ETIKETI_REP>
        <r:TARIH>2026-06-19</r:TARIH>
        <r:IC_ADEDI>36</r:IC_ADEDI>
        <r:RESOURCE_ID>SP30</r:RESOURCE_ID>
        <r:IS_EMRI_NO>3001</r:IS_EMRI_NO>
        <r:ENVANTER_KODU>MM-PET0300</r:ENVANTER_KODU>
        <r:ENVANTER_ADI>Preform</r:ENVANTER_ADI>
        <r:PAKET_ID>PKT-1</r:PAKET_ID>
        <r:LOT_BATCH_NO>LOT-A</r:LOT_BATCH_NO>
        <r:PALET_NO>PAL-1</r:PALET_NO>
        <r:SIRA_NO>1</r:SIRA_NO>
      </r:SIMSEK_PALET_ETIKETI_REP>
    </root>
    """

    payload = parse_simsek_palet_etiketi_rep_xml(xml_text)

    assert payload == {
        "job_order": "3001",
        "package_id": "PKT-1",
        "lot_batch_no": "LOT-A",
        "part_no": "MM-PET0300",
        "product_description": "Preform",
        "pallet_no": "PAL-1",
        "sequence_no": "1",
        "quantity": "36",
        "label_time": "2026-06-19",
        "machine_code": "SP30",
    }
