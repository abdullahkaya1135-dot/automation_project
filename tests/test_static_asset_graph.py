import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = PROJECT_ROOT / "app" / "static"
TEMPLATE_DIR = PROJECT_ROOT / "app" / "templates"

JS_IMPORT_PATTERN = re.compile(
    r"(?:import\s+(?:[\s\S]*?\s+from\s+)?|import\s*\()\s*['\"]([^'\"]+)['\"]"
)
CSS_IMPORT_PATTERN = re.compile(r"@import\s+url\(['\"]?([^'\")]+)['\"]?\)")
STATIC_URL_PATTERN = re.compile(r"['\"](/static/[^'\"]+)['\"]")


def _split_asset_ref(reference: str) -> tuple[str, str]:
    path, separator, query = reference.partition("?")
    suffix = f"{separator}{query}" if separator else ""
    return path, suffix


def _static_path_from_url(url: str) -> Path:
    path, _query = _split_asset_ref(url)
    assert path.startswith("/static/")
    return STATIC_DIR / path.removeprefix("/static/")


def _static_url_for(path: Path, query: str = "") -> str:
    relative_path = path.relative_to(STATIC_DIR).as_posix()
    return f"/static/{relative_path}{query}"


def _local_js_asset_graph(entry_url: str) -> set[str]:
    entry_path = _static_path_from_url(entry_url)
    entry_query = _split_asset_ref(entry_url)[1]
    pending = [entry_path]
    seen_paths: set[Path] = set()
    urls = {_static_url_for(entry_path, entry_query)}

    while pending:
        current_path = pending.pop()
        if current_path in seen_paths:
            continue
        seen_paths.add(current_path)
        source = current_path.read_text(encoding="utf-8")
        for reference in JS_IMPORT_PATTERN.findall(source):
            if not reference.startswith("."):
                continue
            asset_path, query = _split_asset_ref(reference)
            resolved_path = (current_path.parent / asset_path).resolve()
            assert resolved_path.is_file(), f"Missing JS import: {reference}"
            assert STATIC_DIR in resolved_path.parents
            urls.add(_static_url_for(resolved_path, query))
            pending.append(resolved_path)

    return urls


def _local_css_asset_graph(entry_url: str) -> set[str]:
    entry_path = _static_path_from_url(entry_url)
    entry_query = _split_asset_ref(entry_url)[1]
    pending = [entry_path]
    seen_paths: set[Path] = set()
    urls = {_static_url_for(entry_path, entry_query)}

    while pending:
        current_path = pending.pop()
        if current_path in seen_paths:
            continue
        seen_paths.add(current_path)
        source = current_path.read_text(encoding="utf-8")
        for reference in CSS_IMPORT_PATTERN.findall(source):
            if not reference.startswith("."):
                continue
            asset_path, query = _split_asset_ref(reference)
            resolved_path = (current_path.parent / asset_path).resolve()
            assert resolved_path.is_file(), f"Missing CSS import: {reference}"
            assert STATIC_DIR in resolved_path.parents
            urls.add(_static_url_for(resolved_path, query))
            pending.append(resolved_path)

    return urls


def test_frontend_module_import_graph_resolves_and_is_cached():
    script_template = (TEMPLATE_DIR / "partials" / "app_script.html").read_text(
        encoding="utf-8"
    )
    style_template = (TEMPLATE_DIR / "partials" / "app_styles.html").read_text(
        encoding="utf-8"
    )
    service_worker = (STATIC_DIR / "service-worker.js").read_text(encoding="utf-8")

    script_urls = set(STATIC_URL_PATTERN.findall(script_template))
    style_urls = set(STATIC_URL_PATTERN.findall(style_template))
    assert script_urls == {"/static/js/app.js?v=20260615-shop-orders"}
    assert style_urls == {"/static/css/app.css?v=20260615-css"}

    required_urls: set[str] = set()
    for script_url in script_urls:
        required_urls.update(_local_js_asset_graph(script_url))
    for style_url in style_urls:
        required_urls.update(_local_css_asset_graph(style_url))

    for url in sorted(required_urls):
        assert f'"{url}"' in service_worker, f"{url} is missing from service worker"

    assert not (STATIC_DIR / "js" / "modules" / "main-page.js").exists()
    assert not (STATIC_DIR / "js" / "modules" / "render.js").exists()
    assert not (STATIC_DIR / "js" / "modules" / "ifs-return.js").exists()
    assert not (STATIC_DIR / "js" / "modules" / "constants.js").exists()
    assert not (STATIC_DIR / "js" / "modules" / "offline.js").exists()
    assert not (STATIC_DIR / "js" / "modules" / "shop-orders.js").exists()


def test_offline_bulk_sync_retries_only_pending_excel_queues():
    sync_source = (
        STATIC_DIR / "js" / "modules" / "offline" / "outbox-sync.js"
    ).read_text(
        encoding="utf-8"
    )
    upload_source = (
        STATIC_DIR / "js" / "modules" / "offline" / "outbox-upload.js"
    ).read_text(
        encoding="utf-8"
    )
    retry_source = (
        STATIC_DIR / "js" / "modules" / "offline" / "server-excel-retry.js"
    ).read_text(
        encoding="utf-8"
    )

    assert len(sync_source.splitlines()) <= 130
    assert "retryQueues = pendingExcelQueuesFromBulkResponse(payload);" in upload_source
    assert re.search(
        r"if \(excelPending\) \{\s+await flushServerExcelQueues\(retryQueues\);",
        sync_source,
    )
    assert "await flushServerExcelQueues();" not in sync_source
    assert 'result.type === "entry"' in retry_source
    assert 'result.type === "auxiliary_submission"' in retry_source
    assert 'apiJson("/api/sync/retry"' in retry_source
    assert 'apiJson("/api/auxiliary-systems/sync/retry"' in retry_source


def test_role_pages_share_phone_sync_controls():
    operator_source = (
        STATIC_DIR / "js" / "modules" / "pages" / "operator.js"
    ).read_text(encoding="utf-8")
    supervisor_source = (
        STATIC_DIR / "js" / "modules" / "pages" / "supervisor.js"
    ).read_text(encoding="utf-8")
    controls_source = (
        STATIC_DIR / "js" / "modules" / "pages" / "phone-sync-controls.js"
    ).read_text(encoding="utf-8")

    assert "phone-sync-controls.js?v=20260616-page-controls" in operator_source
    assert "phone-sync-controls.js?v=20260616-page-controls" in supervisor_source
    assert "function bindPhoneSyncControls" not in operator_source
    assert "function bindPhoneSyncControls" not in supervisor_source
    assert "handlePhoneOutboxSync" not in operator_source
    assert "handlePhoneOutboxSync" not in supervisor_source
    assert "exportOfflineOutbox" not in operator_source
    assert "exportOfflineOutbox" not in supervisor_source
    assert "export function bindPhoneSyncControls" in controls_source
    assert "handlePhoneOutboxSync" in controls_source
    assert "exportOfflineOutbox" in controls_source


def test_operator_page_delegates_offline_form_submit_handlers():
    operator_source = (
        STATIC_DIR / "js" / "modules" / "pages" / "operator.js"
    ).read_text(encoding="utf-8")
    entry_source = (
        STATIC_DIR / "js" / "modules" / "pages" / "operator-entry.js"
    ).read_text(encoding="utf-8")
    tour_source = (
        STATIC_DIR / "js" / "modules" / "pages" / "operator-tour-context.js"
    ).read_text(encoding="utf-8")

    assert "operator-entry.js?v=20260616-operator-forms" in operator_source
    assert "operator-tour-context.js?v=20260616-operator-forms" in operator_source
    assert "async function handleEntrySubmit" not in operator_source
    assert "async function handleTourContextSubmit" not in operator_source
    assert "queueOfflineRecord" not in operator_source
    assert 'queueOfflineRecord("entry"' in entry_source
    assert 'queueOfflineRecord("tour_context"' in tour_source
    assert "entryRequestBody" in entry_source
    assert "automaticTourTimingForRequest" in tour_source


def test_utility_page_delegates_auxiliary_submit_handler():
    utility_source = (
        STATIC_DIR / "js" / "modules" / "pages" / "utility.js"
    ).read_text(encoding="utf-8")
    auxiliary_source = (
        STATIC_DIR / "js" / "modules" / "pages" / "utility-auxiliary.js"
    ).read_text(encoding="utf-8")

    assert "utility-auxiliary.js?v=20260616-utility-forms" in utility_source
    assert "async function handleAuxiliarySubmit" not in utility_source
    assert "queueOfflineRecord" not in utility_source
    assert "auxiliaryRequestBody" not in utility_source
    assert "hasAuxiliaryMeasurement" not in utility_source
    assert 'queueOfflineRecord("auxiliary_submission"' in auxiliary_source
    assert "auxiliaryRequestBody" in auxiliary_source
    assert "hasAuxiliaryMeasurement" in auxiliary_source


def test_supervisor_page_delegates_retry_controls():
    supervisor_source = (
        STATIC_DIR / "js" / "modules" / "pages" / "supervisor.js"
    ).read_text(encoding="utf-8")
    sync_source = (
        STATIC_DIR / "js" / "modules" / "pages" / "supervisor-sync-controls.js"
    ).read_text(encoding="utf-8")

    assert "supervisor-sync-controls.js?v=20260616-supervisor-sync" in supervisor_source
    assert "bindSupervisorSyncControls" in supervisor_source
    assert "async function handleRetrySync" not in supervisor_source
    assert "async function handleRetryAuxiliarySync" not in supervisor_source
    assert 'apiJson("/api/sync/retry"' not in supervisor_source
    assert 'apiJson("/api/auxiliary-systems/sync/retry"' not in supervisor_source
    assert "export function bindSupervisorSyncControls" in sync_source
    assert 'apiJson("/api/sync/retry"' in sync_source
    assert 'apiJson("/api/auxiliary-systems/sync/retry"' in sync_source
    assert "refreshBootstrap()" in sync_source


def test_planning_page_delegates_cycle_report_handler():
    planning_source = (
        STATIC_DIR / "js" / "modules" / "pages" / "planning.js"
    ).read_text(encoding="utf-8")
    cycle_source = (
        STATIC_DIR / "js" / "modules" / "pages" / "planning-cycle-report.js"
    ).read_text(encoding="utf-8")
    ifs_source = (
        STATIC_DIR / "js" / "modules" / "pages" / "planning-ifs-return.js"
    ).read_text(encoding="utf-8")

    assert "planning-cycle-report.js?v=20260616-planning-cycle" in planning_source
    assert "planning-ifs-return.js?v=20260616-planning-ifs" in planning_source
    assert "async function handleCreateCycleReport" not in planning_source
    assert "async function handleIfsReturnCandidates" not in planning_source
    assert 'apiJson("/api/cycle-report/today"' not in planning_source
    assert 'apiJson("/api/ifs/u1-return-candidates"' not in planning_source
    assert "export async function handleCreateCycleReport" in cycle_source
    assert 'apiJson("/api/cycle-report/today"' in cycle_source
    assert "Rapor olusturuldu" in cycle_source
    assert "export async function handleIfsReturnCandidates" in ifs_source
    assert 'apiJson("/api/ifs/u1-return-candidates"' in ifs_source
