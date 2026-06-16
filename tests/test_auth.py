from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.modules.auth.service import (
    SESSION_COOKIE_NAME,
    create_session_cookie_value,
    verify_session_cookie_value,
)


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


def test_unauthenticated_page_requests_redirect_to_login(client):
    response = client.get("/", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_login_page_renders(client):
    response = client.get("/login")

    assert response.status_code == 200
    assert 'id="login-form"' in response.text
    assert "Proses Girişi" in response.text


def test_login_sets_cookie_and_allows_protected_routes(client):
    bad_response = client.post("/api/login", json={"pin": "0000"})
    assert bad_response.status_code == 401
    assert SESSION_COOKIE_NAME not in bad_response.cookies

    login_response = client.post("/api/login", json={"pin": "4321"})
    assert login_response.status_code == 200
    assert SESSION_COOKIE_NAME in login_response.cookies
    assert login_response.json()["role"] == "admin"
    assert login_response.json()["default_path"] == "/operator"

    bootstrap_response = client.get("/api/bootstrap")
    assert bootstrap_response.status_code == 200
    bootstrap_payload = bootstrap_response.json()
    assert "machines" not in bootstrap_payload
    assert "machine_count" not in bootstrap_payload["excel"]

    index_response = client.get("/")
    assert index_response.status_code == 200
    assert 'id="entry-form"' in index_response.text
    assert 'id="auxiliary-form"' not in index_response.text
    assert 'id="run-ifs-return-candidates"' not in index_response.text

    login_page_response = client.get("/login", follow_redirects=False)
    assert login_page_response.status_code == 303
    assert login_page_response.headers["location"] == "/operator"


def test_role_pin_workspaces_enforce_page_permissions(monkeypatch, tmp_path):
    monkeypatch.setenv("EXCEL_PATH", str(tmp_path / "missing.xlsx"))
    monkeypatch.setenv("APP_PIN", "")
    monkeypatch.setenv(
        "APP_ROLE_PINS",
        "operator:1111,utility:2222,supervisor:3333,planning:4444,admin:9999",
    )
    monkeypatch.setenv("SESSION_SECRET", "test-session-secret")
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "process_entries.sqlite3"))
    monkeypatch.setenv("BACKUP_DIR", str(tmp_path / "backups"))

    with TestClient(create_app()) as role_client:
        operator_login = role_client.post("/api/login", json={"pin": "1111"})
        assert operator_login.status_code == 200
        assert operator_login.json()["role"] == "operator"
        assert operator_login.json()["default_path"] == "/operator"

        operator_page = role_client.get("/operator")
        assert operator_page.status_code == 200
        assert 'data-page="operator"' in operator_page.text
        assert 'id="entry-form"' in operator_page.text
        assert 'id="sync-phone-outbox"' in operator_page.text
        assert 'id="auxiliary-form"' not in operator_page.text
        assert 'id="retry-sync"' not in operator_page.text
        assert 'id="run-ifs-return-candidates"' not in operator_page.text

        supervisor_denied = role_client.get("/supervisor")
        assert supervisor_denied.status_code == 403

    with TestClient(create_app()) as role_client:
        utility_login = role_client.post("/api/login", json={"pin": "2222"})
        assert utility_login.status_code == 200
        assert utility_login.json()["role"] == "utility"
        assert utility_login.json()["default_path"] == "/utility"

        utility_page = role_client.get("/utility")
        assert utility_page.status_code == 200
        assert 'data-page="utility"' in utility_page.text
        assert 'id="auxiliary-form"' in utility_page.text
        assert 'id="entry-form"' not in utility_page.text
        assert 'id="retry-sync"' not in utility_page.text
        assert 'id="run-ifs-return-candidates"' not in utility_page.text

    with TestClient(create_app()) as role_client:
        supervisor_login = role_client.post("/api/login", json={"pin": "3333"})
        assert supervisor_login.status_code == 200
        supervisor_page = role_client.get("/supervisor")
        assert supervisor_page.status_code == 200
        assert 'data-page="supervisor"' in supervisor_page.text
        assert 'id="retry-sync"' in supervisor_page.text
        assert 'id="retry-auxiliary-sync"' in supervisor_page.text
        assert 'id="auxiliary-form"' not in supervisor_page.text
        assert 'id="entry-form"' not in supervisor_page.text
        assert 'id="run-ifs-return-candidates"' not in supervisor_page.text

    with TestClient(create_app()) as role_client:
        planning_login = role_client.post("/api/login", json={"pin": "4444"})
        assert planning_login.status_code == 200
        planning_page = role_client.get("/planning")
        assert planning_page.status_code == 200
        assert 'data-page="planning"' in planning_page.text
        assert 'id="create-cycle-report"' in planning_page.text
        assert 'id="run-ifs-return-candidates"' in planning_page.text
        assert 'id="entry-form"' not in planning_page.text
        assert 'id="auxiliary-form"' not in planning_page.text
        assert 'id="retry-sync"' not in planning_page.text

    with TestClient(create_app()) as role_client:
        admin_login = role_client.post("/api/login", json={"pin": "9999"})
        assert admin_login.status_code == 200
        assert admin_login.json()["role"] == "admin"
        admin_operator = role_client.get("/operator")
        admin_utility = role_client.get("/utility")
        admin_supervisor = role_client.get("/supervisor")
        admin_planning = role_client.get("/planning")
        assert admin_operator.status_code == 200
        assert admin_utility.status_code == 200
        assert admin_supervisor.status_code == 200
        assert admin_planning.status_code == 200
        assert admin_operator.text.count('class="role-nav-link') == 4


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
