from datetime import datetime

import pytest

from tests.routes.helpers import ISTANBUL_TIMEZONE, _freeze_request_time


def test_tour_context_uses_request_time_for_date_and_shift(client, monkeypatch):
    _freeze_request_time(
        monkeypatch,
        datetime(2026, 6, 9, 2, 30, tzinfo=ISTANBUL_TIMEZONE),
    )

    response = client.post(
        "/api/tour-context",
        json={
            "date": "1999-01-01",
            "ambient_temp": "24,5",
            "production_engineer": "Barış Çetik",
            "shift_chief": "Selman",
            "shift": "16.00-24.00",
        },
    )

    assert response.status_code == 201
    context = response.json()["tour_context"]
    assert context["date"] == "09.06.2026"
    assert context["shift"] == "24.00-08.00"


def test_tour_context_uses_client_recorded_at_for_offline_shift(
    client,
    monkeypatch,
):
    _freeze_request_time(
        monkeypatch,
        datetime(2026, 6, 8, 16, 5, tzinfo=ISTANBUL_TIMEZONE),
    )

    response = client.post(
        "/api/tour-context",
        json={
            "client_request_id": "tour-client-request-1",
            "client_recorded_at": "2026-06-08T15:55:00+03:00",
            "ambient_temp": "24,5",
            "production_engineer": "Barış Çetik",
            "shift_chief": "Selman",
        },
    )

    assert response.status_code == 201
    context = response.json()["tour_context"]
    assert context["client_request_id"] == "tour-client-request-1"
    assert context["date"] == "08.06.2026"
    assert context["shift"] == "08.00-16.00"


def test_tour_context_is_idempotent_for_client_request_id(client):
    request_body = {
        "client_request_id": "tour-client-request-2",
        "client_recorded_at": "2026-06-08T09:30:00+03:00",
        "ambient_temp": "24,5",
        "production_engineer": "Barış Çetik",
        "shift_chief": "Selman",
    }

    first_response = client.post("/api/tour-context", json=request_body)
    replay_response = client.post("/api/tour-context", json=request_body)

    assert first_response.status_code == 201
    assert replay_response.status_code == 200
    first_payload = first_response.json()
    replay_payload = replay_response.json()
    assert replay_payload["idempotent_replay"] is True
    assert replay_payload["id"] == first_payload["id"]
    assert (
        replay_payload["tour_context"]["client_request_id"] == "tour-client-request-2"
    )


def test_tour_context_rejects_unknown_shift_chief(client):
    response = client.post(
        "/api/tour-context",
        json={
            "ambient_temp": "24,5",
            "production_engineer": "Barış Çetik",
            "shift_chief": "Chief",
        },
    )

    assert response.status_code == 422
    assert "Selman, Serkan, Hakan" in response.json()["detail"]


@pytest.mark.parametrize(
    ("request_time", "expected_shift"),
    [
        (datetime(2026, 6, 8, 7, 59, tzinfo=ISTANBUL_TIMEZONE), "24.00-08.00"),
        (datetime(2026, 6, 8, 8, 0, tzinfo=ISTANBUL_TIMEZONE), "08.00-16.00"),
        (datetime(2026, 6, 8, 15, 59, tzinfo=ISTANBUL_TIMEZONE), "08.00-16.00"),
        (datetime(2026, 6, 8, 16, 0, tzinfo=ISTANBUL_TIMEZONE), "16.00-24.00"),
    ],
)
def test_shift_boundaries(request_time, expected_shift):
    from app.domain.shifts import shift_for_request_time

    assert shift_for_request_time(request_time) == expected_shift
