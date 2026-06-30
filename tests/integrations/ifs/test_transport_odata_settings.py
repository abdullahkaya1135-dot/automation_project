from __future__ import annotations

import asyncio
import logging

import httpx
import pytest

import app.core.config as config
import app.integrations.ifs.client as ifs_client
from app.core.config import Settings
from app.integrations.ifs.client import (
    IFSClientError,
    fetch_u1_hm02_stock,
    obtain_access_token,
)

from .helpers import MULTI_PREFIX_FILTER, RequestRecorder


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
    recorder = RequestRecorder(requests)
    settings = Settings(ifs_base_url="https://ifs.example.com")

    def handler(request: httpx.Request) -> httpx.Response:
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
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(recorder.wrap(handler))
        ) as client:
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
    recorder = RequestRecorder(requests)
    settings = Settings(
        ifs_base_url="https://ifs.example.com",
        ifs_token_url="https://ifs.example.com/token",
        ifs_client_id="client-id",
        ifs_client_secret="client-secret",
        ifs_username="user",
        ifs_password="pass",
    )

    def handler(request: httpx.Request) -> httpx.Response:
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
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(recorder.wrap(handler))
        ) as client:
            return await fetch_u1_hm02_stock(settings, client=client)

    rows = asyncio.run(run())

    assert rows == [{"PartNo": "HM-02-A"}]
    assert [request.url.path for request in requests] == [
        "/token",
        "/main/ifsapplications/projection/v1/InventoryPartInStockHandling.svc/InventoryPartInStockSet",
    ]


def test_obtain_access_token_supports_password_grant():
    requests: list[httpx.Request] = []
    recorder = RequestRecorder(requests)
    settings = Settings(
        ifs_token_url="https://ifs.example.com/token",
        ifs_client_id="client-id",
        ifs_client_secret="client-secret",
        ifs_username="user",
        ifs_password="pass",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        form = httpx.QueryParams(request.content.decode())
        assert form["grant_type"] == "password"
        assert form["client_id"] == "client-id"
        assert form["client_secret"] == "client-secret"
        assert form["username"] == "user"
        assert form["password"] == "pass"
        return httpx.Response(200, json={"access_token": "user-token"})

    async def run() -> str:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(recorder.wrap(handler))
        ) as client:
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
