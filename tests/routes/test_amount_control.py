import pytest

from app.core.config import Settings
from app.core.database import create_session
from app.models import AmountControlShift, MachineBreakdown
from tests.routes.helpers import _amount_control_body


def test_amount_control_shift_create_list_detail_and_breakdown_links(client, tmp_path):
    response = client.post(
        "/api/amount-control/shifts",
        json=_amount_control_body(client_request_id="amount-client-request-1"),
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["saved_locally"] is True
    assert payload["idempotent_replay"] is False
    amount_shift = payload["shift"]
    assert amount_shift["client_request_id"] == "amount-client-request-1"
    assert amount_shift["record_date"] == "2026-06-08"
    assert amount_shift["machine_code"] == "101"
    assert amount_shift["job_order"] == "WO-1"
    assert amount_shift["shift"] == "08.00-16.00"
    assert amount_shift["worker_names"] == "Operator One, Operator Two"
    assert amount_shift["produced_quantity"] == 1200
    assert len(amount_shift["breakdowns"]) == 2
    assert amount_shift["breakdowns"][0]["entry_id"] is None
    assert (
        amount_shift["breakdowns"][0]["amount_control_shift_id"] == amount_shift["id"]
    )
    assert amount_shift["breakdowns"][0]["machine_code"] == "101"

    list_response = client.get(
        "/api/amount-control/shifts",
        params={
            "record_date": "2026-06-08",
            "machine_code": "101",
            "job_order": "WO-1",
        },
    )
    assert list_response.status_code == 200
    listed_shifts = list_response.json()["shifts"]
    assert len(listed_shifts) == 1
    assert listed_shifts[0]["id"] == amount_shift["id"]

    detail_response = client.get(f"/api/amount-control/shifts/{amount_shift['id']}")
    assert detail_response.status_code == 200
    assert detail_response.json()["breakdowns"][1]["stop_reason"] == "Mold change"

    settings = Settings(
        excel_path=str(tmp_path / "process.xlsx"),
        app_pin="1234",
        sqlite_path=str(tmp_path / "process_entries.sqlite3"),
        backup_dir=str(tmp_path / "backups"),
    )
    with create_session(settings) as session:
        assert session.query(AmountControlShift).count() == 1
        assert session.query(MachineBreakdown).count() == 2
        breakdown = session.query(MachineBreakdown).first()
        assert breakdown is not None
        assert breakdown.entry_id is None
        assert breakdown.amount_control_shift_id == amount_shift["id"]
        assert breakdown.record_date == "2026-06-08"
        assert breakdown.shift == "08.00-16.00"
        assert breakdown.job_order == "WO-1"


def test_amount_control_shift_is_idempotent_for_client_request_id(
    client,
    tmp_path,
):
    request_body = _amount_control_body(
        client_request_id="amount-client-request-2",
        breakdowns=[],
    )

    first_response = client.post("/api/amount-control/shifts", json=request_body)
    replay_response = client.post("/api/amount-control/shifts", json=request_body)

    assert first_response.status_code == 201
    assert replay_response.status_code == 200
    first_payload = first_response.json()
    replay_payload = replay_response.json()
    assert replay_payload["idempotent_replay"] is True
    assert replay_payload["shift"]["id"] == first_payload["shift"]["id"]
    assert replay_payload["shift"]["client_request_id"] == "amount-client-request-2"

    settings = Settings(
        excel_path=str(tmp_path / "process.xlsx"),
        app_pin="1234",
        sqlite_path=str(tmp_path / "process_entries.sqlite3"),
        backup_dir=str(tmp_path / "backups"),
    )
    with create_session(settings) as session:
        assert session.query(AmountControlShift).count() == 1


def test_amount_control_shift_rejects_duplicate_business_key(client):
    first_response = client.post(
        "/api/amount-control/shifts",
        json=_amount_control_body(client_request_id="amount-client-request-3"),
    )
    duplicate_response = client.post(
        "/api/amount-control/shifts",
        json=_amount_control_body(
            client_request_id="amount-client-request-4",
            worker_names="Operator Three",
            produced_quantity=900,
            breakdowns=[],
        ),
    )

    assert first_response.status_code == 201
    assert duplicate_response.status_code == 409
    assert "zaten var" in duplicate_response.json()["detail"]


def test_amount_control_shift_rejects_unknown_machine(client):
    response = client.post(
        "/api/amount-control/shifts",
        json=_amount_control_body(machine_code="999", breakdowns=[]),
    )

    assert response.status_code == 422
    assert "makine" in response.json()["detail"]


@pytest.mark.parametrize(
    "overrides",
    [
        {"record_date": "08.06.2026"},
        {"shift": "00.00-08.00"},
        {"job_order": " "},
        {"worker_names": " "},
        {"produced_quantity": -1},
        {
            "breakdowns": [
                {
                    "produced_product": "Product 101",
                    "stop_reason": "Fault",
                    "duration_minutes": 0,
                }
            ]
        },
        {
            "breakdowns": [
                {
                    "produced_product": "Product 101",
                    "stop_reason": "Fault",
                    "duration_minutes": 1,
                    "stopped_at": "2026-06-08T11:00:00+03:00",
                    "resumed_at": "2026-06-08T10:00:00+03:00",
                }
            ]
        },
    ],
)
def test_amount_control_shift_validates_payload(client, overrides):
    response = client.post(
        "/api/amount-control/shifts",
        json=_amount_control_body(**overrides),
    )

    assert response.status_code == 422


def test_amount_control_shift_detail_returns_404_for_missing_id(client):
    response = client.get("/api/amount-control/shifts/999999")

    assert response.status_code == 404
