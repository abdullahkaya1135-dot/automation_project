from app.web.pages import PROTECTED_PAGE_PATHS, SHARED_PAGE_ASSET_URLS

SHARED_PAGE_ASSET_MARKERS = (
    f'href="{SHARED_PAGE_ASSET_URLS[0]}"',
    f'type="module" src="{SHARED_PAGE_ASSET_URLS[1]}"',
)


PAGE_SECTION_EXPECTATIONS = {
    "/": (
        'data-page="dashboard"',
        'id="dashboard-heading"',
        'class="dashboard-grid"',
        'class="dashboard-card',
        'href="/process"',
        'href="/auxiliary"',
        'href="/amount-control"',
        'href="/breakdowns"',
        'href="/reports"',
    ),
    "/process": (
        'data-page="process"',
        'id="tour-context-form"',
        'id="entry-form"',
    ),
    "/auxiliary": (
        'data-page="auxiliary"',
        'id="auxiliary-form"',
    ),
    "/amount-control": (
        'data-page="amount-control"',
        'id="amount-control-form"',
    ),
    "/breakdowns": (
        'data-page="breakdowns"',
        'id="breakdown-form"',
        'name="reason"',
        'value="00.00-08.00"',
        'id="breakdown-submissions"',
    ),
    "/reports": (
        'data-page="reports"',
        'id="phone-sync-heading"',
        'id="pending-entries"',
        'id="create-cycle-report"',
        'id="run-shift-manager-check"',
        'id="shift-manager-results"',
        'id="production-loss-form"',
        'id="production-loss-results"',
        'id="generate-whatsapp-status-message"',
        'id="copy-whatsapp-status-message"',
        'id="whatsapp-status-message-text"',
        'id="run-missing-production-starts"',
        'id="missing-production-results"',
        'id="run-ifs-planning-first-job-statuses"',
        'id="ifs-planning-first-job-results"',
        'id="run-ifs-return-candidates"',
        'id="print-ifs-return-candidates"',
        'id="ifs-return-print-area"',
        'id="label-material-availability-heading"',
        'id="label-material-availability-message"',
        'id="run-label-material-availability"',
        'id="label-material-availability-results"',
        'id="run-package-label-checklist"',
        'id="print-package-label-checklist"',
        'id="package-label-checklist-print-area"',
    ),
}


PAGE_SECTION_EXCLUSIONS = {
    "/": (
        'id="tour-context-form"',
        'id="entry-form"',
        'id="auxiliary-form"',
        'id="amount-control-form"',
        'id="breakdown-form"',
        'id="pending-entries"',
        'id="create-cycle-report"',
        'id="run-shift-manager-check"',
        'id="generate-whatsapp-status-message"',
        'id="run-missing-production-starts"',
        'id="run-ifs-planning-first-job-statuses"',
        'id="run-ifs-return-candidates"',
        'id="run-label-material-availability"',
        'id="run-package-label-checklist"',
    ),
    "/process": (
        'id="dashboard-heading"',
        'id="auxiliary-form"',
        'id="amount-control-form"',
        'id="breakdown-form"',
        'id="pending-entries"',
        'id="create-cycle-report"',
        'id="run-shift-manager-check"',
        'id="generate-whatsapp-status-message"',
        'id="run-missing-production-starts"',
        'id="run-ifs-planning-first-job-statuses"',
        'id="run-ifs-return-candidates"',
        'id="run-label-material-availability"',
        'id="run-package-label-checklist"',
    ),
    "/auxiliary": (
        'id="dashboard-heading"',
        'id="tour-context-form"',
        'id="entry-form"',
        'id="amount-control-form"',
        'id="breakdown-form"',
        'id="pending-entries"',
        'id="create-cycle-report"',
        'id="run-shift-manager-check"',
        'id="generate-whatsapp-status-message"',
        'id="run-missing-production-starts"',
        'id="run-ifs-planning-first-job-statuses"',
        'id="run-ifs-return-candidates"',
        'id="run-label-material-availability"',
        'id="run-package-label-checklist"',
    ),
    "/amount-control": (
        'id="dashboard-heading"',
        'id="tour-context-form"',
        'id="entry-form"',
        'id="auxiliary-form"',
        'id="breakdown-form"',
        'id="pending-entries"',
        'id="create-cycle-report"',
        'id="run-shift-manager-check"',
        'id="generate-whatsapp-status-message"',
        'id="run-missing-production-starts"',
        'id="run-ifs-planning-first-job-statuses"',
        'id="run-ifs-return-candidates"',
        'id="run-label-material-availability"',
        'id="run-package-label-checklist"',
    ),
    "/breakdowns": (
        'id="dashboard-heading"',
        'id="tour-context-form"',
        'id="entry-form"',
        'id="auxiliary-form"',
        'id="amount-control-form"',
        'id="pending-entries"',
        'id="create-cycle-report"',
        'id="run-shift-manager-check"',
        'id="generate-whatsapp-status-message"',
        'id="run-missing-production-starts"',
        'id="run-ifs-planning-first-job-statuses"',
        'id="run-ifs-return-candidates"',
        'id="run-label-material-availability"',
        'id="run-package-label-checklist"',
    ),
    "/reports": (
        'id="dashboard-heading"',
        'id="tour-context-form"',
        'id="entry-form"',
        'id="auxiliary-form"',
        'id="amount-control-form"',
        'id="breakdown-form"',
    ),
}


def test_page_routes_render_expected_split_sections_and_shared_assets(client):
    assert tuple(PAGE_SECTION_EXPECTATIONS) == PROTECTED_PAGE_PATHS
    assert tuple(PAGE_SECTION_EXCLUSIONS) == PROTECTED_PAGE_PATHS

    for path in PROTECTED_PAGE_PATHS:
        expected_markers = PAGE_SECTION_EXPECTATIONS[path]
        response = client.get(path)

        assert response.status_code == 200
        assert response.headers["Cache-Control"] == "no-store, max-age=0"
        for marker in (*SHARED_PAGE_ASSET_MARKERS, *expected_markers):
            assert marker in response.text
        for marker in PAGE_SECTION_EXCLUSIONS[path]:
            assert marker not in response.text


def test_breakdown_page_keeps_paper_only_fields(client):
    response = client.get("/breakdowns")

    assert response.status_code == 200
    assert 'name="reason"' in response.text
    assert 'name="duration_minutes"' in response.text
    assert 'name="stopped_at"' not in response.text
    assert 'name="resumed_at"' not in response.text
    assert "Durus baslangici" not in response.text
    assert "Durus bitisi" not in response.text


def test_breakdown_page_orders_fields_for_paper_entry(client):
    response = client.get("/breakdowns")

    assert response.status_code == 200
    field_markers = (
        'id="breakdown-date"',
        'id="breakdown-machine"',
        'id="breakdown-job-order"',
        'id="breakdown-product"',
        'id="breakdown-shift"',
        'id="breakdown-duration"',
        'id="breakdown-reason"',
        'id="breakdown-context-message"',
    )
    field_positions = [response.text.index(marker) for marker in field_markers]
    assert field_positions == sorted(field_positions)
