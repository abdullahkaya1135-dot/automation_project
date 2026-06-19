import json
from datetime import UTC, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.core.config import Settings
from app.domain import request_settings, request_values, shifts
from app.web import pages

ISTANBUL_TIMEZONE = timezone(timedelta(hours=3), "Europe/Istanbul")


def _request_with_state(**state_values):
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(**state_values)))


def _injected_json_constant(source: str, name: str):
    prefix = f"const {name} = "
    start = source.index(prefix) + len(prefix)
    value, end = json.JSONDecoder().raw_decode(source[start:])
    assert source[start + end] == ";"
    return value


def test_settings_from_request_reuses_existing_app_state(monkeypatch):
    settings = Settings(app_pin="state-pin")
    request = _request_with_state(settings=settings)

    monkeypatch.setattr(
        request_settings,
        "get_settings",
        lambda: pytest.fail("get_settings should not be called"),
    )
    monkeypatch.setattr(
        request_settings,
        "init_db",
        lambda _settings: pytest.fail("init_db should not be called"),
    )

    assert request_settings.settings_from_request(request) is settings


def test_settings_from_request_initializes_once_and_caches(monkeypatch):
    settings = Settings(app_pin="loaded-pin")
    request = _request_with_state()
    init_calls = []

    monkeypatch.setattr(request_settings, "get_settings", lambda: settings)
    monkeypatch.setattr(
        request_settings,
        "init_db",
        lambda loaded_settings: init_calls.append(loaded_settings),
    )

    assert request_settings.settings_from_request(request) is settings
    assert request.app.state.settings is settings
    assert request_settings.settings_from_request(request) is settings
    assert init_calls == [settings]


@pytest.mark.parametrize(
    ("raw_value", "expected_iso"),
    [
        ("2026-06-08T09:30:00", "2026-06-08T09:30:00+03:00"),
        ("2026-06-08T06:30:00Z", "2026-06-08T09:30:00+03:00"),
        ("2026-06-08T08:30:00+02:00", "2026-06-08T09:30:00+03:00"),
    ],
)
def test_client_recorded_datetime_uses_request_timezone(raw_value, expected_iso):
    settings = Settings(timezone="Europe/Istanbul")

    parsed = request_values.client_recorded_datetime(raw_value, settings)

    assert parsed is not None
    assert parsed.isoformat() == expected_iso


def test_client_recorded_datetime_rejects_invalid_iso_value():
    with pytest.raises(HTTPException) as exc_info:
        request_values.client_recorded_datetime("not-a-date", Settings())

    assert exc_info.value.status_code == 422
    assert "client_recorded_at" in exc_info.value.detail


def test_stored_client_recorded_at_strips_timezone_after_utc_conversion():
    recorded_at = datetime(2026, 6, 8, 9, 30, tzinfo=ISTANBUL_TIMEZONE)

    stored = request_values.stored_client_recorded_at(recorded_at)

    assert stored == datetime(2026, 6, 8, 6, 30)
    assert stored.tzinfo is None


def test_stored_client_recorded_at_accepts_utc_value_without_offset_change():
    recorded_at = datetime(2026, 6, 8, 6, 30, tzinfo=UTC)

    assert request_values.stored_client_recorded_at(recorded_at) == datetime(
        2026,
        6,
        8,
        6,
        30,
    )


def test_stored_client_recorded_at_preserves_none():
    assert request_values.stored_client_recorded_at(None) is None


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        (None, False),
        ("", False),
        (" yes ", True),
        ("evet", True),
        ("0", False),
        ("hayir", False),
    ],
)
def test_optional_bool_accepts_empty_and_common_form_values(raw_value, expected):
    assert request_values.optional_bool(raw_value, "enabled") is expected


def test_shift_chief_canonicalizes_known_options_case_insensitively():
    assert request_values.shift_chief(" selMAN ") == "Selman"


@pytest.mark.parametrize(
    ("request_time", "expected_shift"),
    [
        (datetime(2026, 6, 8, 0, 0, tzinfo=ISTANBUL_TIMEZONE), "24.00-08.00"),
        (datetime(2026, 6, 8, 7, 59, 59, 999999, ISTANBUL_TIMEZONE), "24.00-08.00"),
        (datetime(2026, 6, 8, 8, 0, tzinfo=ISTANBUL_TIMEZONE), "08.00-16.00"),
        (datetime(2026, 6, 8, 15, 59, 59, 999999, ISTANBUL_TIMEZONE), "08.00-16.00"),
        (datetime(2026, 6, 8, 16, 0, tzinfo=ISTANBUL_TIMEZONE), "16.00-24.00"),
        (datetime(2026, 6, 8, 23, 59, 59, 999999, ISTANBUL_TIMEZONE), "16.00-24.00"),
    ],
)
def test_shift_for_request_time_covers_full_day_edges(request_time, expected_shift):
    assert shifts.shift_for_request_time(request_time) == expected_shift


def test_tour_timing_for_datetime_formats_date_shift_timezone_and_generated_at():
    settings = Settings(timezone="Europe/Istanbul")
    request_time = datetime(2026, 6, 8, 16, 0, 1, 123456, ISTANBUL_TIMEZONE)

    timing = shifts.tour_timing_for_datetime(settings, request_time)

    assert timing == {
        "date": "08.06.2026",
        "shift": "16.00-24.00",
        "timezone": "Europe/Istanbul",
        "generated_at": "2026-06-08T16:00:01+03:00",
    }


def test_recorded_date_text_leaves_non_iso_values_unchanged():
    assert shifts.recorded_date_text("2026-06-08") == "08.06.2026"
    assert shifts.recorded_date_text("08.06.2026") == "08.06.2026"


def test_request_timezone_falls_back_to_fixed_istanbul_offset(monkeypatch):
    def missing_zone(_timezone_name):
        raise shifts.ZoneInfoNotFoundError

    monkeypatch.setattr(shifts, "ZoneInfo", missing_zone)

    assert shifts.request_timezone(Settings(timezone="Europe/Istanbul")) is (
        shifts.FIXED_TIMEZONE_OFFSETS["Europe/Istanbul"]
    )


def test_page_metadata_constants_stay_consistent():
    protected_paths = tuple(route.path for route in pages.PROTECTED_PAGE_ROUTES)
    active_pages = tuple(route.active_page for route in pages.PROTECTED_PAGE_ROUTES)
    protected_pages = {route.path: route for route in pages.PROTECTED_PAGE_ROUTES}
    no_cache_page_paths = (*pages.PROTECTED_PAGE_PATHS, pages.LOGIN_PAGE_PATH)

    assert protected_paths == pages.PROTECTED_PAGE_PATHS
    assert protected_pages == pages.PROTECTED_PAGES
    assert no_cache_page_paths == pages.NO_CACHE_PAGE_PATHS
    assert no_cache_page_paths == pages.APP_ROUTE_URLS
    assert len(set(protected_paths)) == len(protected_paths)
    assert len(set(active_pages)) == len(active_pages)
    assert pages.LOGIN_PAGE_PATH not in pages.PROTECTED_PAGES
    for route in pages.PROTECTED_PAGE_ROUTES:
        assert route.path.startswith("/")
        assert route.template_name.startswith("pages/")
        assert route.template_name.endswith(".html")
        assert route.title
        assert route.active_page


def test_static_asset_urls_share_versioned_static_prefix():
    assert pages.APP_STYLESHEET_URL in pages.SHARED_PAGE_ASSET_URLS
    assert pages.APP_SCRIPT_URL in pages.SHARED_PAGE_ASSET_URLS
    for asset_url in pages.APP_SHELL_URLS:
        if asset_url == pages.MANIFEST_URL:
            continue
        assert asset_url.startswith(pages.STATIC_URL_PREFIX)
        assert asset_url.endswith(f"?v={pages.STATIC_ASSET_VERSION}")


def test_service_worker_injects_current_route_and_shell_constants():
    response = pages.service_worker()
    source = bytes(response.body).decode()

    assert response.media_type == "application/javascript"
    assert response.headers["Cache-Control"] == "no-cache"
    assert response.headers["Service-Worker-Allowed"] == "/"
    assert _injected_json_constant(source, "APP_ROUTE_URLS") == list(pages.APP_ROUTE_URLS)
    assert _injected_json_constant(source, "APP_SHELL_URLS") == list(pages.APP_SHELL_URLS)
    assert source.index("const APP_ROUTE_URLS") < source.index("const APP_SHELL_URLS")
    assert source.index("const APP_SHELL_URLS") < source.index("const CACHE_NAME")
