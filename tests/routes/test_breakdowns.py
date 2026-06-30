from datetime import datetime

import pytest

from app.core.config import Settings
from app.core.database import create_session
from app.models import Entry, MachineBreakdown
from tests.routes.helpers import _breakdown_body


def test_breakdown_create_list_detail_and_idempotent_replay(client, tmp_path):
    request_body = _breakdown_body(client_request_id="breakdown-client-request-1")

    response = client.post("/api/breakdowns", json=request_body)
    replay_response = client.post("/api/breakdowns", json=request_body)

    assert response.status_code == 201
    assert replay_response.status_code == 200
    payload = response.json()
    replay_payload = replay_response.json()
    assert payload["saved_locally"] is True
    assert payload["idempotent_replay"] is False
    assert replay_payload["idempotent_replay"] is True
    breakdown = payload["breakdown"]
    assert replay_payload["breakdown"]["id"] == breakdown["id"]
    assert breakdown["client_request_id"] == "breakdown-client-request-1"
    assert breakdown["record_date"] == "2026-06-08"
    assert breakdown["machine_code"] == "101"
    assert breakdown["shift"] == "24.00-08.00"
    assert breakdown["job_order"] == "WO-1"
    assert breakdown["produced_product"] == "Product 101"
    assert breakdown["reason"] == "Hydraulic pressure fault"
    assert breakdown["stop_reason"] == "Hydraulic pressure fault"
    assert breakdown["duration_minutes"] == 45
    assert breakdown["amount_control_shift_id"] is None

    list_response = client.get(
        "/api/breakdowns",
        params={
            "record_date": "2026-06-08",
            "machine_code": "101",
            "shift": "00:00-08:00",
            "job_order": "WO-1",
        },
    )
    assert list_response.status_code == 200
    listed_breakdowns = list_response.json()["breakdowns"]
    assert [item["id"] for item in listed_breakdowns] == [breakdown["id"]]

    detail_response = client.get(f"/api/breakdowns/{breakdown['id']}")
    assert detail_response.status_code == 200
    assert detail_response.json()["reason"] == "Hydraulic pressure fault"

    settings = Settings(
        excel_path=str(tmp_path / "process.xlsx"),
        app_pin="1234",
        sqlite_path=str(tmp_path / "process_entries.sqlite3"),
        backup_dir=str(tmp_path / "backups"),
    )
    with create_session(settings) as session:
        assert session.query(MachineBreakdown).count() == 1
        persisted = session.query(MachineBreakdown).one()
        assert persisted.record_date == "2026-06-08"
        assert persisted.shift == "24.00-08.00"
        assert persisted.job_order == "WO-1"
        assert persisted.produced_product == "Product 101"
        assert persisted.stop_reason == "Hydraulic pressure fault"


def test_breakdown_context_returns_process_entry_prefill_options(client, tmp_path):
    settings = Settings(
        excel_path=str(tmp_path / "process.xlsx"),
        app_pin="1234",
        sqlite_path=str(tmp_path / "process_entries.sqlite3"),
        backup_dir=str(tmp_path / "backups"),
    )
    older_duplicate = Entry(
        process_date="2026-06-08",
        machine_code="2",
        col_f="2",
        col_g="Product A",
        col_h="WO-1",
        sync_status="synced",
        submitted_at=datetime(2026, 6, 8, 8, 0),
        created_at=datetime(2026, 6, 8, 8, 1),
    )
    latest_duplicate = Entry(
        process_date="2026-06-08",
        machine_code="2",
        col_f="2",
        col_g="Product A",
        col_h="WO-1",
        sync_status="synced",
        submitted_at=datetime(2026, 6, 8, 9, 0),
        created_at=datetime(2026, 6, 8, 9, 1),
    )
    machine_ten = Entry(
        process_date="2026-06-08",
        machine_code="10",
        col_f="10",
        col_g="Product B",
        col_h="WO-2",
        sync_status="synced",
        submitted_at=datetime(2026, 6, 8, 9, 30),
        created_at=datetime(2026, 6, 8, 9, 31),
    )
    older_fallback = Entry(
        process_date="2026-06-08",
        machine_code=None,
        col_f="101",
        col_g="Product C",
        col_h="WO-3",
        sync_status="synced",
        created_at=datetime(2026, 6, 8, 10, 0),
    )
    latest_fallback = Entry(
        process_date="2026-06-08",
        machine_code=None,
        col_f="101",
        col_g="Product C",
        col_h="WO-3",
        sync_status="synced",
        created_at=datetime(2026, 6, 8, 11, 0),
    )

    with create_session(settings) as session:
        session.add_all(
            [
                older_duplicate,
                latest_duplicate,
                machine_ten,
                older_fallback,
                latest_fallback,
                Entry(
                    process_date="2026-06-08",
                    machine_code="5",
                    col_f="5",
                    col_g="Missing job order",
                    col_h=" ",
                    sync_status="synced",
                ),
                Entry(
                    process_date="2026-06-08",
                    machine_code=None,
                    col_f=" ",
                    col_g="Missing machine",
                    col_h="WO-MISSING-MACHINE",
                    sync_status="synced",
                ),
                Entry(
                    process_date="2026-06-09",
                    machine_code="1",
                    col_f="1",
                    col_g="Other date",
                    col_h="WO-OTHER",
                    sync_status="synced",
                ),
            ]
        )
        session.commit()

    response = client.get(
        "/api/breakdowns/context",
        params={"record_date": "2026-06-08"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["record_date"] == "2026-06-08"
    assert payload["source"] == "process_entries"
    assert payload["option_count"] == 3
    assert payload["options"] == [
        {
            "machine_code": "2",
            "job_order": "WO-1",
            "produced_product": "Product A",
            "entry_id": latest_duplicate.id,
            "submitted_at": "2026-06-08T09:00:00Z",
        },
        {
            "machine_code": "10",
            "job_order": "WO-2",
            "produced_product": "Product B",
            "entry_id": machine_ten.id,
            "submitted_at": "2026-06-08T09:30:00Z",
        },
        {
            "machine_code": "101",
            "job_order": "WO-3",
            "produced_product": "Product C",
            "entry_id": latest_fallback.id,
            "submitted_at": None,
        },
    ]


def test_breakdown_accepts_paper_minimum_payload(client):
    response = client.post(
        "/api/breakdowns",
        json=_breakdown_body(
            job_order=None,
            produced_product=None,
            stopped_at=None,
            resumed_at=None,
        ),
    )

    assert response.status_code == 201
    breakdown = response.json()["breakdown"]
    assert breakdown["job_order"] is None
    assert breakdown["produced_product"] is None
    assert breakdown["stopped_at"] is None
    assert breakdown["resumed_at"] is None


@pytest.mark.parametrize(
    "overrides",
    [
        {"record_date": "08.06.2026"},
        {"machine_code": "999"},
        {"shift": "00.00-09.00"},
        {"reason": " "},
        {"duration_minutes": 0},
        {
            "stopped_at": "2026-06-08T11:00:00+03:00",
            "resumed_at": "2026-06-08T10:00:00+03:00",
        },
    ],
)
def test_breakdown_validates_payload(client, overrides):
    response = client.post("/api/breakdowns", json=_breakdown_body(**overrides))

    assert response.status_code == 422


def test_breakdown_detail_returns_404_for_missing_id(client):
    response = client.get("/api/breakdowns/999999")

    assert response.status_code == 404
