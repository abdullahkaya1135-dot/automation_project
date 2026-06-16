import os

import pytest
from openpyxl import Workbook

from app.modules.production_planning.errors import ProductionPlanningError
from app.modules.production_planning.reader import read_visible_planning_orders
from app.modules.production_planning.resolver import (
    latest_planning_workbook,
    resolve_planning_workbook,
)


def _write_candidate(path, modified_time):
    path.write_bytes(b"not a real workbook")
    os.utime(path, (modified_time, modified_time))


def test_read_visible_planning_orders_ignores_hidden_content_and_deduplicates(
    tmp_path,
):
    workbook_path = tmp_path / "planning.xlsx"
    workbook = Workbook()

    visible = workbook.active
    visible.title = "Visible"
    visible["A1"] = "0"
    visible["A2"] = "123"
    visible["A3"] = "KAPATILACAK"
    visible["A4"] = "123"
    visible["A5"] = "456-789"
    visible["A6"] = "999"
    visible.row_dimensions[6].hidden = True

    hidden_sheet = workbook.create_sheet("Hidden Sheet")
    hidden_sheet.sheet_state = "hidden"
    hidden_sheet["A1"] = "555"

    hidden_column = workbook.create_sheet("Hidden Column")
    hidden_column["A1"] = "777"
    hidden_column.column_dimensions["A"].hidden = True

    second_visible = workbook.create_sheet("Second Visible")
    second_visible["A1"] = "789"
    second_visible["A2"] = "321"

    workbook.save(workbook_path)
    workbook.close()

    orders = read_visible_planning_orders(workbook_path)

    assert [order.order_no for order in orders] == ["123", "456", "789", "321"]
    assert [(order.sheet_name, order.row_number, order.cell_value) for order in orders] == [
        ("Visible", 2, "123"),
        ("Visible", 5, "456-789"),
        ("Visible", 5, "456-789"),
        ("Second Visible", 2, "321"),
    ]


def test_latest_planning_workbook_prefers_newest_filename_date_over_modified_time(
    tmp_path,
):
    older_date_newer_modified = tmp_path / "12.06.2026 CIZELGE 1.xlsx"
    newer_date_older_modified = tmp_path / "13.06.2026 CIZELGE 1.xlsx"
    excel_temp_file = tmp_path / "~$14.06.2026 CIZELGE 1.xlsx"
    undated_newer_modified = tmp_path / "manual-planning.xlsx"

    _write_candidate(older_date_newer_modified, 300)
    _write_candidate(newer_date_older_modified, 100)
    _write_candidate(excel_temp_file, 500)
    _write_candidate(undated_newer_modified, 600)

    assert latest_planning_workbook(tmp_path) == newer_date_older_modified


def test_latest_planning_workbook_uses_modified_time_as_same_day_tiebreaker(
    tmp_path,
):
    first = tmp_path / "12.06.2026 CIZELGE 1.xlsx"
    second = tmp_path / "12.06.2026 CIZELGE 2.xlsx"

    _write_candidate(first, 100)
    _write_candidate(second, 200)

    assert latest_planning_workbook(tmp_path) == second


def test_latest_planning_workbook_uses_modified_time_when_names_have_no_dates(
    tmp_path,
):
    older = tmp_path / "planning-a.xlsx"
    newer = tmp_path / "planning-b.xlsx"

    _write_candidate(older, 100)
    _write_candidate(newer, 200)

    assert latest_planning_workbook(tmp_path) == newer


def test_latest_planning_workbook_raises_when_no_valid_candidates(tmp_path):
    (tmp_path / "archive").mkdir()
    _write_candidate(tmp_path / "~$12.06.2026 CIZELGE 1.xlsx", 100)
    (tmp_path / "12.06.2026 CIZELGE 1.xls").write_bytes(b"old format")

    with pytest.raises(ProductionPlanningError, match="No production planning"):
        latest_planning_workbook(tmp_path)


def test_resolve_planning_workbook_uses_static_path_when_folder_is_blank(tmp_path):
    fallback_path = tmp_path / "manual.xlsx"

    assert resolve_planning_workbook("", fallback_path) == fallback_path
