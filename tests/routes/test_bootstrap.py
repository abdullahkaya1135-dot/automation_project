from tests.routes.helpers import _tour_context


def test_bootstrap_and_health_endpoints_report_current_state(client):
    bootstrap_response = client.get("/api/bootstrap")
    assert bootstrap_response.status_code == 200
    bootstrap_payload = bootstrap_response.json()
    assert bootstrap_payload["excel"]["available"] is True
    assert bootstrap_payload["excel"]["database_backed"] is True
    assert [
        engineer["full_name"] for engineer in bootstrap_payload["production_engineers"]
    ] == [
        "Barış Çetik",
        "Abdullah Kaya",
        "Fevzi Kılınç",
    ]
    assert len(bootstrap_payload["machines"]) == 47
    assert bootstrap_payload["machines"][0]["machine_code"] == "101"
    assert bootstrap_payload["auxiliary_systems"]["form_available"] is True
    assert bootstrap_payload["auxiliary_systems"]["target_available"] is True
    assert bootstrap_payload["shop_order_source"]["available"] is True
    assert bootstrap_payload["shop_order_source"]["operation_count"] == 2
    assert bootstrap_payload["shop_order_source"]["order_count"] == 2
    assert bootstrap_payload["shop_order_source"]["resource_count"] == 2
    assert bootstrap_payload["shop_order_source"]["options"] == [
        {
            "order_no": "WO-1",
            "resource_id": "M-01",
            "release_no": "*",
            "sequence_no": "*",
            "operation_no": None,
            "part_no": "",
            "part_description": "PET0001-01 400ML SEFFAF 28MM YIVLI 6GR",
        },
        {
            "order_no": "WO-2",
            "resource_id": "M-02",
            "release_no": "*",
            "sequence_no": "*",
            "operation_no": None,
            "part_no": "",
            "part_description": "PET0002-01 400ML SEFFAF 28MM YIVLI 8GR",
        },
    ]
    assert bootstrap_payload["current_tour_timing"]["date"] == "08.06.2026"
    assert bootstrap_payload["current_tour_timing"]["shift"] == "08.00-16.00"
    assert bootstrap_payload["current_auxiliary_date"] == "08.06.2026"
    assert bootstrap_payload["latest_tour_context"] is None
    assert bootstrap_payload["last_sync_error"] is None
    assert bootstrap_payload["last_auxiliary_sync_error"] is None

    context_id = _tour_context(client)
    refreshed_bootstrap_response = client.get("/api/bootstrap")
    assert refreshed_bootstrap_response.status_code == 200
    assert (
        refreshed_bootstrap_response.json()["latest_tour_context"]["id"] == context_id
    )

    health_response = client.get("/health")
    assert health_response.status_code == 200
    health_payload = health_response.json()
    assert health_payload["status"] == "ok"
    assert health_payload["sqlite"]["ok"] is True
    assert health_payload["process_data"]["ok"] is True
    assert health_payload["process_data"]["database_backed"] is True
    assert health_payload["auxiliary_systems"]["form_ok"] is True
    assert health_payload["auxiliary_systems"]["target_ok"] is True
    assert health_payload["excel_write_lock"]["locked"] is False
    assert health_payload["excel_write_lock"]["waiting"] == 0


def test_bootstrap_can_load_shop_orders_from_ifs(client, monkeypatch):
    async def fake_fetch(_settings):
        return [
            {
                "OrderNo": "2615",
                "PreferredResourceId": "135",
                "WorkCenterNo": "SP25",
                "PartNoDesc": "Bottle",
            },
            {
                "OrderNo": "2616",
                "PreferredResourceId": "136",
                "WorkCenterNo": "SP26",
                "PartNoDesc": "Bottle 2",
            },
        ]

    monkeypatch.setattr(
        "app.features.bootstrap.api.fetch_pet_ongoing_operations", fake_fetch
    )

    response = client.get("/api/bootstrap")

    assert response.status_code == 200
    source = response.json()["shop_order_source"]
    assert source["available"] is True
    assert source["source"] == "ifs-token"
    assert source["operation_count"] == 2
    assert source["order_count"] == 2
    assert source["resource_count"] == 2
    assert source["options"] == [
        {
            "order_no": "2615",
            "resource_id": "135",
            "release_no": "*",
            "sequence_no": "*",
            "operation_no": None,
            "part_no": "",
            "part_description": "Bottle",
        },
        {
            "order_no": "2616",
            "resource_id": "136",
            "release_no": "*",
            "sequence_no": "*",
            "operation_no": None,
            "part_no": "",
            "part_description": "Bottle 2",
        },
    ]
