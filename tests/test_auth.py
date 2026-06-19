from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.security import (
    SESSION_COOKIE_NAME,
    create_session_cookie_value,
    verify_session_cookie_value,
)
from app.main import create_app

PROTECTED_PAGE_ROUTES = ("/", "/process", "/auxiliary", "/amount-control", "/reports")
PROTECTED_PAGE_MARKERS = {
    "/": 'id="dashboard-heading"',
    "/process": 'id="entry-form"',
    "/auxiliary": 'id="auxiliary-form"',
    "/amount-control": 'id="amount-control-form"',
    "/reports": 'id="run-ifs-return-candidates"',
}


@pytest.fixture
def client(monkeypatch, tmp_path) -> Generator[TestClient]:
    monkeypatch.setenv("EXCEL_PATH", str(tmp_path / "missing.xlsx"))
    monkeypatch.setenv("APP_PIN", "4321")
    monkeypatch.setenv("SESSION_SECRET", "test-session-secret")
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "process_entries.sqlite3"))
    monkeypatch.setenv("BACKUP_DIR", str(tmp_path / "backups"))

    with TestClient(create_app()) as test_client:
        yield test_client


def test_unauthenticated_api_requests_return_401(client):
    response = client.get("/api/bootstrap")

    assert response.status_code == 401
    assert response.json()["detail"] == "Oturum açmanız gerekiyor."


@pytest.mark.parametrize("path", PROTECTED_PAGE_ROUTES)
def test_unauthenticated_page_requests_redirect_to_login(client, path):
    response = client.get(path, follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_login_page_renders(client):
    response = client.get("/login")

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store, max-age=0"
    assert 'id="login-form"' in response.text
    assert "Proses Girişi" in response.text


def test_login_sets_cookie_and_allows_protected_routes(client):
    bad_response = client.post("/api/login", json={"pin": "0000"})
    assert bad_response.status_code == 401
    assert SESSION_COOKIE_NAME not in bad_response.cookies

    login_response = client.post("/api/login", json={"pin": "4321"})
    assert login_response.status_code == 200
    assert SESSION_COOKIE_NAME in login_response.cookies

    bootstrap_response = client.get("/api/bootstrap")
    assert bootstrap_response.status_code == 200
    bootstrap_payload = bootstrap_response.json()
    assert len(bootstrap_payload["machines"]) == 47
    assert "machine_count" not in bootstrap_payload["excel"]

    for path, marker in PROTECTED_PAGE_MARKERS.items():
        page_response = client.get(path)
        assert page_response.status_code == 200
        assert page_response.headers["Cache-Control"] == "no-store, max-age=0"
        assert marker in page_response.text

    process_response = client.get("/process")
    assert 'id="tour-context-form"' in process_response.text

    reports_response = client.get("/reports")
    assert 'id="print-ifs-return-candidates"' in reports_response.text

    login_page_response = client.get("/login", follow_redirects=False)
    assert login_page_response.status_code == 303
    assert login_page_response.headers["location"] == "/"


def test_session_cookie_is_signed_with_session_secret_not_pin():
    original_settings = Settings(
        app_pin="1111",
        session_secret="shared-session-secret",
    )
    changed_pin_settings = Settings(
        app_pin="2222",
        session_secret="shared-session-secret",
    )
    changed_secret_settings = Settings(
        app_pin="1111",
        session_secret="different-session-secret",
    )

    cookie_value = create_session_cookie_value(original_settings)

    assert verify_session_cookie_value(cookie_value, changed_pin_settings) is True
    assert verify_session_cookie_value(cookie_value, changed_secret_settings) is False
