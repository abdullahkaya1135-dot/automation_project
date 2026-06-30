from pathlib import Path


def test_package_label_checklist_renderer_uses_requested_columns():
    source = Path("app/static/js/modules/render.js").read_text(encoding="utf-8")
    columns_start = source.index("const PACKAGE_LABEL_CHECKLIST_ROW_SOURCES")
    columns_end = source.index("export function renderEntryList", columns_start)
    columns = source[columns_start:columns_end]
    labels = [
        'label: "Machine"',
        'label: "JobOrder"',
        'label: "PartNo"',
        'label: "Description"',
        'label: "HandlingUnitId"',
        'label: "ReceiptDate"',
        'label: "Label OK"',
        'label: "Reason"',
    ]
    positions = [columns.index(label) for label in labels]

    assert positions == sorted(positions)
    assert 'label: "No"' not in columns
    assert 'label: "Qty"' not in columns
    assert 'label: "Operation Status"' not in columns
    assert 'label: "Missing Reason"' not in columns
    assert "packageLabelChecklistMachineText" in source
    assert "packageLabelChecklistHandlingUnitText" in source
    assert "packageLabelChecklistReceiptDateText" in source
    assert 'text.replace(/\\./g, "")' in source


def test_package_label_checklist_renderer_marks_future_long_text_columns():
    source = Path("app/static/js/modules/render.js").read_text(encoding="utf-8")
    machine_start = source.index('label: "Machine"')
    job_order_start = source.index('label: "JobOrder"', machine_start)
    part_no_start = source.index('label: "PartNo"')
    description_start = source.index('label: "Description"', part_no_start)
    handling_unit_start = source.index('label: "HandlingUnitId"', description_start)
    receipt_date_start = source.index('label: "ReceiptDate"', handling_unit_start)
    label_ok_start = source.index('label: "Label OK"', receipt_date_start)
    machine_column = source[machine_start:job_order_start]
    job_order_column = source[job_order_start:part_no_start]
    part_no_column = source[part_no_start:description_start]
    description_column = source[description_start:handling_unit_start]
    handling_unit_column = source[handling_unit_start:receipt_date_start]
    receipt_date_column = source[receipt_date_start:label_ok_start]
    future_part_no = "FUTURE-2099-PACKAGE-LABEL-CHECKLIST-PART-NO-ALPHA-00000001"
    future_description = (
        "Future package label checklist description for a new IFS item family "
        "with deliberately long marketing and technical wording"
    )

    assert len(future_part_no) > 48
    assert len(future_description) > 96
    assert "package-label-checklist-machine-cell" in machine_column
    assert "package-label-checklist-job-order-cell" in job_order_column
    assert "mono-cell" in part_no_column
    assert "package-label-checklist-part-no-col" in part_no_column
    assert "package-label-checklist-single-line-cell" in part_no_column
    assert "package-label-checklist-description-col" in description_column
    assert "package-label-checklist-single-line-cell" in description_column
    assert "package-label-checklist-handling-unit-cell" in handling_unit_column
    assert "mono-cell" in receipt_date_column
    assert "package-label-checklist-single-line-cell" in receipt_date_column
    assert "package-label-checklist-receipt-date-cell" in receipt_date_column
    assert "package-label-checklist-receipt-date-col" in receipt_date_column


def test_package_label_checklist_print_css_keeps_rows_compact_and_stable():
    css = Path("app/static/css/app.css").read_text(encoding="utf-8")
    print_css = css[css.index("@media print"):]
    table_selector = ".print-only .package-label-checklist-table"
    cell_selector = (
        ".print-only .package-label-checklist-table th,\n"
        "  .print-only .package-label-checklist-table td"
    )
    single_line_selector = ".print-only .package-label-checklist-single-line-cell"
    mono_single_line_selector = (
        ".print-only .package-label-checklist-single-line-cell.mono-cell"
    )
    centered_cell_selector = ".print-only .package-label-checklist-machine-cell"
    writing_cell_selector = ".print-only .package-label-checklist-writing-cell"
    centered_cell_classes = [
        "package-label-checklist-machine-cell",
        "package-label-checklist-job-order-cell",
        "package-label-checklist-part-no-cell",
        "package-label-checklist-description-cell",
        "package-label-checklist-handling-unit-cell",
        "package-label-checklist-receipt-date-cell",
    ]
    expected_col_widths = {
        "package-label-checklist-machine-col": "8%",
        "package-label-checklist-job-order-col": "11%",
        "package-label-checklist-part-no-col": "18%",
        "package-label-checklist-description-col": "29%",
        "package-label-checklist-handling-unit-col": "9%",
        "package-label-checklist-receipt-date-col": "13%",
        "package-label-checklist-label-ok-col": "5%",
        "package-label-checklist-reason-col": "7%",
    }

    table_rule = print_css[
        print_css.index(table_selector):print_css.index("}", print_css.index(table_selector))
    ]
    cell_rule = print_css[
        print_css.index(cell_selector):print_css.index("}", print_css.index(cell_selector))
    ]
    single_line_rule = print_css[
        print_css.index(single_line_selector):print_css.index(
            "}",
            print_css.index(single_line_selector),
        )
    ]
    mono_single_line_rule = print_css[
        print_css.index(mono_single_line_selector):print_css.index(
            "}",
            print_css.index(mono_single_line_selector),
        )
    ]
    centered_cell_rule = print_css[
        print_css.index(centered_cell_selector):print_css.index(
            "}",
            print_css.index(centered_cell_selector),
        )
    ]
    writing_cell_rule = print_css[
        print_css.index(writing_cell_selector):print_css.index(
            "}",
            print_css.index(writing_cell_selector),
        )
    ]

    assert "font-size: 5.8pt;" in table_rule
    assert "line-height: 1.1;" in table_rule
    assert "font-size: 5.8pt;" in cell_rule
    assert "padding: 0.5pt 2pt;" in cell_rule
    assert "line-height: 1.1;" in cell_rule
    assert "white-space: nowrap;" in single_line_rule
    assert "overflow: hidden;" in single_line_rule
    assert "text-overflow: ellipsis;" in single_line_rule
    assert "overflow-wrap: normal;" in mono_single_line_rule
    assert "word-break: normal;" in mono_single_line_rule
    assert "text-align: center;" in centered_cell_rule
    for cell_class in centered_cell_classes:
        assert f".print-only .{cell_class}" in centered_cell_rule
    assert "height: 14pt;" in writing_cell_rule
    assert "overflow: hidden;" in writing_cell_rule
    assert "text-overflow: ellipsis;" in writing_cell_rule
    assert "white-space: nowrap;" in writing_cell_rule
    for col_class, width in expected_col_widths.items():
        selector = f".print-only .{col_class}"
        col_rule = print_css[
            print_css.index(selector):print_css.index(
                "}",
                print_css.index(selector),
            )
        ]
        assert f"width: {width};" in col_rule


def test_package_label_checklist_renderer_formats_receipt_date():
    source = Path("app/static/js/modules/render.js").read_text(encoding="utf-8")
    receipt_column_start = source.index('label: "ReceiptDate"')
    receipt_column_end = source.index('label: "Label OK"', receipt_column_start)
    receipt_column = source[receipt_column_start:receipt_column_end]
    renderer_start = source.index("function packageLabelChecklistReceiptDateText")
    renderer_end = source.index("function packageLabelChecklistMachineText", renderer_start)
    renderer = source[renderer_start:renderer_end]

    assert '"receipt_date"' in receipt_column
    assert '"receiptDate"' in receipt_column
    assert '"ReceiptDate"' in receipt_column
    assert "value: packageLabelChecklistReceiptDateText" in receipt_column
    assert "const value = checklistRowValue(row, column.keys);" in renderer
    assert "return value === null ? null : formatTimestamp(value);" in renderer


def test_package_label_checklist_renderer_prefers_machine_value_for_ambiguous_rows():
    source = Path("app/static/js/modules/render.js").read_text(encoding="utf-8")
    machine_column_start = source.index('label: "Machine"')
    machine_column_end = source.index('label: "JobOrder"', machine_column_start)
    machine_column = source[machine_column_start:machine_column_end]
    renderer_start = source.index("function packageLabelChecklistMachineText")
    renderer_end = source.index("function packageLabelChecklistStatus", renderer_start)
    renderer = source[renderer_start:renderer_end]

    assert '"machine_code"' in machine_column
    assert '"resource_id"' in machine_column
    assert '"preferred_resource_id"' in machine_column
    assert '"ResourceId"' in machine_column
    assert '"PreferredResourceId"' in machine_column
    assert "row?.operation_match_status ?? row?.match_status ??" in renderer
    assert "const machine = checklistRowValue(row, column.keys);" in renderer
    assert 'return machine ?? "Belirsiz";' in renderer
    assert "return machine;" in renderer


def test_package_label_checklist_renderer_groups_shared_cells_with_rowspan():
    source = Path("app/static/js/modules/render.js").read_text(encoding="utf-8")
    columns_start = source.index("const PACKAGE_LABEL_CHECKLIST_ROW_SOURCES")
    renderer_start = source.index("function renderPackageLabelChecklistTable")
    renderer_end = source.index("function packageLabelChecklistRows", renderer_start)
    renderer = source[renderer_start:renderer_end]
    append_cell_start = source.index("function appendChecklistCell")
    append_cell_end = source.index("function checklistCellText", append_cell_start)
    append_cell = source[append_cell_start:append_cell_end]

    assert "const PACKAGE_LABEL_CHECKLIST_GROUP_COLUMN_COUNT = 4;" in source
    assert 'label: "HandlingUnitId"' in source[columns_start:renderer_start]
    assert (
        "for (const group of packageLabelChecklistGroups(rows))" in renderer
    )
    assert "group.rows.forEach((renderedRow, rowIndex) => {" in renderer
    assert "columnIndex < PACKAGE_LABEL_CHECKLIST_GROUP_COLUMN_COUNT" in renderer
    assert "if (rowIndex > 0)" in renderer
    assert "appendChecklistCell(tr, value, column.className" in renderer
    assert "group.rows.length" in renderer
    assert (
        ".slice(0, PACKAGE_LABEL_CHECKLIST_GROUP_COLUMN_COUNT)"
        in renderer
    )
    assert "cell.rowSpan = rowSpan;" in append_cell


def test_package_label_checklist_print_renderer_omits_summary_header():
    source = Path("app/static/js/modules/render.js").read_text(encoding="utf-8")
    renderer_start = source.index(
        "export function renderPackageLabelChecklistPrintArea",
    )
    renderer_end = source.index("export function renderMissingProductionStarts", renderer_start)
    renderer = source[renderer_start:renderer_end]

    assert "renderPackageLabelChecklistSummary" not in renderer
    assert "package-label-checklist-print-title" not in renderer
    assert 'textContent = "Package Label Checklist"' not in renderer
    assert "renderPackageLabelChecklistTable(rows)" in renderer
    assert "Checklist satiri yok." in renderer
    assert "activatePrintArea(container)" in renderer
