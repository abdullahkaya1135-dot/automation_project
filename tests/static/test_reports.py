from pathlib import Path


def test_reports_javascript_wires_missing_production_check():
    source = Path("app/static/js/modules/main-page.js").read_text(encoding="utf-8")
    material_source = Path(
        "app/static/js/modules/label-material-availability.js"
    ).read_text(encoding="utf-8")
    planning_source = Path(
        "app/static/js/modules/ifs-planning-first-job.js"
    ).read_text(encoding="utf-8")

    assert "#generate-whatsapp-status-message" in source
    assert "#copy-whatsapp-status-message" in source
    assert "#whatsapp-status-message-text" in source
    assert "#run-missing-production-starts" in source
    assert "#run-ifs-planning-first-job-statuses" in source
    assert "#run-label-material-availability" in source
    assert "#label-material-availability-message" in source
    assert "#run-package-label-checklist" in source
    assert "#print-package-label-checklist" in source
    assert "#production-loss-form" in source
    assert "#sync-process-date" in source
    assert "/api/ifs/whatsapp-status-message" in source
    assert "/api/ifs/missing-production-starts?" in source
    assert "ifs-planning-first-job.js" in source
    assert "label-material-availability.js" in source
    assert "package-label-checklist.js" in source
    assert "/api/production-loss-reports" in source
    assert "process_date" in source
    assert "/api/ifs/label-material-availability" in material_source
    assert "renderLabelMaterialAvailability" in material_source
    assert "/api/ifs/planning-first-job-statuses" in planning_source
    assert "renderIfsPlanningFirstJobStatuses" in planning_source


def test_label_material_availability_renderer_shows_part_totals_and_audit_rows():
    source = Path("app/static/js/modules/render.js").read_text(encoding="utf-8")
    columns_start = source.index("const LABEL_MATERIAL_AVAILABILITY_COLUMNS")
    columns_end = source.index("export function renderEntryList", columns_start)
    columns = source[columns_start:columns_end]
    labels = [
        'label: "Status"',
        'label: "Machine"',
        'label: "Order"',
        'label: "Op"',
        'label: "Material"',
        'label: "Issue Loc"',
        'label: "Row Demand"',
        'label: "U1 Demand"',
        'label: "U1 Available"',
        'label: "Shortage"',
        'label: "IFS QtyAvailable"',
        'label: "Product"',
    ]
    positions = [columns.index(label) for label in labels]

    assert positions == sorted(positions)
    assert "const LABEL_MATERIAL_AVAILABILITY_PART_COLUMNS" in source
    assert "payload?.part_summaries" in source
    assert "payload?.blocked_rows" in source
    assert "payload?.checked_rows" in source
    assert "Parca Toplamlari" in source
    assert "U1 Uygunluk Uyarilari" in source
    assert "Tum Kontrol Satirlari" in source
    assert "label-material-availability-row-blocked" in source
    assert "blocked_insufficient_u1_available" in source
    assert "issue_location_unknown" in source
    assert "ignored_non_u1_issue_location" in source
    assert "updateStatusPill(pill, status.label, status.kind)" in source


def test_label_material_availability_css_keeps_monitor_tables_scannable():
    css = Path("app/static/css/app.css").read_text(encoding="utf-8")

    assert ".label-material-availability-table" in css
    assert "min-width: 1120px;" in css
    assert ".label-material-availability-status-cell .status-pill" in css
    assert "font-size: 0.76rem;" in css
    assert ".label-material-availability-number-cell" in css
    assert "text-align: right;" in css
    assert ".label-material-availability-row-blocked > td" in css
    assert "background: #fff8f6;" in css
