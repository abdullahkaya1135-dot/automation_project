from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
UI_SOURCE_PATHS = (
    ROOT / "app" / "templates" / "pages" / "reports.html",
    ROOT / "app" / "templates" / "partials" / "shift_manager_section.html",
    ROOT / "app" / "static" / "js" / "app.js",
    ROOT / "app" / "static" / "js" / "modules" / "main-page.js",
    ROOT / "app" / "static" / "js" / "modules" / "render.js",
    ROOT / "app" / "static" / "js" / "modules" / "shift-manager.js",
)


def _existing_sources() -> dict[Path, str]:
    return {
        path: path.read_text(encoding="utf-8")
        for path in UI_SOURCE_PATHS
        if path.exists()
    }


def _shift_manager_ui_source() -> str:
    sources = _existing_sources()
    combined = "\n".join(sources.values())
    if "shift-manager" not in combined and "Shift Manager" not in combined:
        pytest.skip("Shift Manager UI is not integrated yet.")
    return combined


def test_shift_manager_button_id_exists():
    source = _shift_manager_ui_source()

    assert (
        'id="run-shift-manager-check"' in source or 'id="run-shift-manager"' in source
    )


def test_shift_manager_js_module_is_wired():
    sources = _existing_sources()
    source = _shift_manager_ui_source()
    main_page = sources.get(
        ROOT / "app" / "static" / "js" / "modules" / "main-page.js", ""
    )
    shift_manager = sources.get(
        ROOT / "app" / "static" / "js" / "modules" / "shift-manager.js",
        "",
    )

    assert "./shift-manager.js" in source
    assert "initializeShiftManagerSection" in main_page
    assert (
        "#run-shift-manager-check" in shift_manager
        or "#run-shift-manager" in shift_manager
    )
    assert "addEventListener" in shift_manager


def test_shift_manager_renderer_includes_informed_checkbox_column():
    source = _shift_manager_ui_source()

    assert "informed" in source or "notified" in source
    assert "checkbox" in source
    assert (
        "data-shift-manager-notified" in source
        or "shiftManagerNotified" in source
        or "shift-manager-checkbox" in source
    )


def test_shift_manager_status_codes_have_requested_ui_labels():
    source = _existing_sources().get(
        ROOT / "app" / "static" / "js" / "modules" / "shift-manager.js",
        "",
    )

    assert 'next_found: "Yeni iş emri var"' in source
    assert 'no_next_job: "Yeni iş emri yok"' in source
    assert '"Yeni iş emri bulundu"' not in source
    assert '"Sonraki iş yok"' not in source
