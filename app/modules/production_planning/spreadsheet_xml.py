import posixpath
from collections.abc import Iterable
from xml.etree import ElementTree
from zipfile import ZipFile

from .errors import ProductionPlanningError

MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def tag(name: str) -> str:
    return f"{{{MAIN_NS}}}{name}"


def rel_attr(name: str) -> str:
    return f"{{{REL_NS}}}{name}"


def resolve_target(base_path: str, target: str) -> str:
    if target.startswith("/"):
        return target.lstrip("/")
    return posixpath.normpath(posixpath.join(posixpath.dirname(base_path), target))


def column_index(cell_reference: str) -> int:
    letters = "".join(char for char in cell_reference if char.isalpha()).upper()
    index = 0
    for char in letters:
        index = index * 26 + ord(char) - 64
    return index


def shared_strings(workbook: ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in workbook.namelist():
        return []

    strings: list[str] = []
    for _event, element in ElementTree.iterparse(
        workbook.open("xl/sharedStrings.xml"),
        events=("end",),
    ):
        if element.tag == tag("si"):
            strings.append("".join(text.text or "" for text in element.iter(tag("t"))))
            element.clear()
    return strings


def cell_text(cell: ElementTree.Element, shared_string_values: list[str]) -> str:
    cell_type = cell.get("t")
    if cell_type == "s":
        value = cell.find(tag("v"))
        if value is None or value.text is None:
            return ""
        try:
            return shared_string_values[int(value.text)]
        except (IndexError, ValueError):
            return ""
    if cell_type == "inlineStr":
        return "".join(text.text or "" for text in cell.iter(tag("t")))

    value = cell.find(tag("v"))
    return "" if value is None or value.text is None else value.text


def visible_sheet_paths(workbook: ZipFile) -> Iterable[tuple[str, str]]:
    try:
        relationships = ElementTree.parse(
            workbook.open("xl/_rels/workbook.xml.rels")
        ).getroot()
        workbook_xml = ElementTree.parse(workbook.open("xl/workbook.xml")).getroot()
    except (ElementTree.ParseError, KeyError) as exc:
        raise ProductionPlanningError(
            "Production planning workbook metadata could not be read."
        ) from exc

    targets_by_id = {
        relationship.get("Id"): relationship.get("Target")
        for relationship in relationships
    }
    for sheet in workbook_xml.findall(f"{tag('sheets')}/{tag('sheet')}"):
        if sheet.get("state", "visible") != "visible":
            continue
        relationship_id = sheet.get(rel_attr("id"))
        target = targets_by_id.get(relationship_id)
        sheet_name = sheet.get("name") or ""
        if relationship_id is None or target is None:
            raise ProductionPlanningError(
                f"Production planning sheet {sheet_name!r} is missing a target."
            )
        yield sheet_name, resolve_target("xl/workbook.xml", target)


def is_hidden_flag(value: str | None) -> bool:
    return value in {"1", "true", "TRUE"}


def column_a_hidden(column: ElementTree.Element) -> bool:
    try:
        min_column = int(float(column.get("min", "0")))
        max_column = int(float(column.get("max", "0")))
    except ValueError:
        return False
    return min_column <= 1 <= max_column and is_hidden_flag(column.get("hidden"))


def visible_column_a_value(
    row: ElementTree.Element,
    shared_string_values: list[str],
) -> str:
    for cell in row.findall(tag("c")):
        cell_column_index = column_index(cell.get("r", ""))
        if cell_column_index == 1:
            return cell_text(cell, shared_string_values).strip()
        if cell_column_index > 1:
            break
    return ""
