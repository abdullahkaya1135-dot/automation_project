from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.auth import SESSION_COOKIE_NAME
from app.main import create_app


@pytest.fixture
def client(monkeypatch, tmp_path) -> Generator[TestClient]:
    monkeypatch.setenv("EXCEL_PATH", str(tmp_path / "missing.xlsx"))
    monkeypatch.setenv("APP_PIN", "4321")
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

    bootstrap_response = client.get("/api/bootstrap")
    assert bootstrap_response.status_code == 200
    bootstrap_payload = bootstrap_response.json()
    assert "machines" not in bootstrap_payload
    assert "machine_count" not in bootstrap_payload["excel"]

    index_response = client.get("/")
    assert index_response.status_code == 200
    assert 'id="entry-form"' in index_response.text

    login_page_response = client.get("/login", follow_redirects=False)
    assert login_page_response.status_code == 303
    assert login_page_response.headers["location"] == "/"
