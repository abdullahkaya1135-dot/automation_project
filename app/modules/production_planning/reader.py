import re
from pathlib import Path
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

from .errors import ProductionPlanningError
from .spreadsheet_xml import (
    column_a_hidden,
    is_hidden_flag,
    shared_strings,
    tag,
    visible_column_a_value,
    visible_sheet_paths,
)
from .types import PlanningOrder as PlanningOrder

ORDER_TOKEN_PATTERN = re.compile(r"\d+")


def read_visible_planning_orders(path: str | Path) -> list[PlanningOrder]:
    """Read visible job orders from column A without opening the full workbook."""

    planning_path = Path(path)
    try:
        with ZipFile(planning_path) as workbook:
            shared_string_values = shared_strings(workbook)
            orders: list[PlanningOrder] = []
            seen_order_numbers: set[str] = set()

            for sheet_name, sheet_path in visible_sheet_paths(workbook):
                read_sheet_orders(
                    workbook,
                    sheet_path=sheet_path,
                    sheet_name=sheet_name,
                    shared_string_values=shared_string_values,
                    seen_order_numbers=seen_order_numbers,
                    orders=orders,
                )
            return orders
    except FileNotFoundError as exc:
        raise ProductionPlanningError(
            f"Production planning workbook was not found: {planning_path}"
        ) from exc
    except (BadZipFile, ElementTree.ParseError, KeyError, OSError) as exc:
        raise ProductionPlanningError(
            f"Production planning workbook could not be read: {planning_path}"
        ) from exc


def read_sheet_orders(
    workbook: ZipFile,
    *,
    sheet_path: str,
    sheet_name: str,
    shared_string_values: list[str],
    seen_order_numbers: set[str],
    orders: list[PlanningOrder],
) -> None:
    column_a_is_hidden = False
    for _event, element in ElementTree.iterparse(
        workbook.open(sheet_path),
        events=("end",),
    ):
        if element.tag == tag("col"):
            if column_a_hidden(element):
                column_a_is_hidden = True
            element.clear()
            continue

        if element.tag != tag("row"):
            continue

        if column_a_is_hidden or is_hidden_flag(element.get("hidden")):
            element.clear()
            continue

        append_order_tokens_from_row(
            element,
            sheet_name=sheet_name,
            shared_string_values=shared_string_values,
            seen_order_numbers=seen_order_numbers,
            orders=orders,
        )
        element.clear()


def append_order_tokens_from_row(
    row: ElementTree.Element,
    *,
    sheet_name: str,
    shared_string_values: list[str],
    seen_order_numbers: set[str],
    orders: list[PlanningOrder],
) -> None:
    row_number = int(float(row.get("r", "0") or "0"))
    cell_value = visible_column_a_value(row, shared_string_values)
    for order_no in ORDER_TOKEN_PATTERN.findall(cell_value):
        if order_no == "0" or order_no in seen_order_numbers:
            continue
        seen_order_numbers.add(order_no)
        orders.append(
            PlanningOrder(
                order_no=order_no,
                sheet_name=sheet_name,
                row_number=row_number,
                cell_value=cell_value,
            )
        )
