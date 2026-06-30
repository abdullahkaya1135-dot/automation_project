from pathlib import Path


def test_breakdown_javascript_uses_machine_code_labels_only():
    source = Path("app/static/js/modules/breakdowns.js").read_text(encoding="utf-8")

    assert "label: machine.machineCode" in source
    assert 'formData.get("stopped_at")' not in source
    assert 'formData.get("resumed_at")' not in source
    assert "stopped_at:" not in source
    assert "resumed_at:" not in source


def test_breakdown_javascript_wires_previous_day_context_lookup():
    source = Path("app/static/js/modules/breakdowns.js").read_text(encoding="utf-8")

    assert "previousLocalIsoDate" in source
    assert "previousDay.setDate(previousDay.getDate() - 1)" in source
    assert "/api/breakdowns/context?" in source
    assert "applyFallbackBreakdownOptions" in source
    assert "setBreakdownContextMessage" in source


def test_breakdown_javascript_reports_empty_process_context():
    source = Path("app/static/js/modules/breakdowns.js").read_text(encoding="utf-8")

    assert "if (!contextOptions.length)" in source
    assert "makine/is emri iceren proses kaydi yok" in source
    assert "#breakdown-context-message" in source


def test_breakdown_javascript_clears_stale_job_product_on_date_context_change():
    source = Path("app/static/js/modules/breakdowns.js").read_text(encoding="utf-8")

    date_listener = source[
        source.index('.querySelector("#breakdown-date")') :
        source.index('.querySelector("#breakdown-machine")')
    ]

    assert "clearBreakdownDateScopedInputs();" in date_listener
    assert "void refreshBreakdownContextForDate();" in date_listener
    assert date_listener.index("clearBreakdownDateScopedInputs();") < (
        date_listener.index("void refreshBreakdownContextForDate();")
    )
    assert "function clearBreakdownDateScopedInputs()" in source
    assert 'document.querySelector("#breakdown-job-order")' in source
    assert 'document.querySelector("#breakdown-product")' in source
    assert "delete productInput.dataset.autofilledFor" in source
    assert "clearBreakdownDateScopedInputs();\n  applyDefaultBreakdownDate();" in source
    assert "reconcileBreakdownDateScopedInputs();" in source
