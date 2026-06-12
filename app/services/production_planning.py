import posixpath
import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
ORDER_TOKEN_PATTERN = re.compile(r"\d+")
PLANNING_FILE_DATE_PATTERN = re.compile(
    r"^\s*(?P<day>\d{1,2})\.(?P<month>\d{1,2})\.(?P<year>\d{4})\b"
)
EXCEL_TEMP_PREFIX = "~$"


class ProductionPlanningError(RuntimeError):
    """Raised when the production planning workbook cannot be read safely."""


@dataclass(frozen=True)
class PlanningOrder:
    order_no: str
    sheet_name: str
    row_number: int
    cell_value: str


@dataclass(frozen=True)
class PlanningWorkbookCandidate:
    path: Path
    date_from_name: date | None
    modified_ns: int


def _tag(name: str) -> str:
    return f"{{{MAIN_NS}}}{name}"


def _rel_attr(name: str) -> str:
    return f"{{{REL_NS}}}{name}"


def _resolve_target(base_path: str, target: str) -> str:
    if target.startswith("/"):
        return target.lstrip("/")
    return posixpath.normpath(posixpath.join(posixpath.dirname(base_path), target))


def _column_index(cell_reference: str) -> int:
    letters = "".join(char for char in cell_reference if char.isalpha()).upper()
    index = 0
    for char in letters:
        index = index * 26 + ord(char) - 64
    return index


def _shared_strings(workbook: ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in workbook.namelist():
        return []

    strings: list[str] = []
    for _event, element in ElementTree.iterparse(
        workbook.open("xl/sharedStrings.xml"),
        events=("end",),
    ):
        if element.tag == _tag("si"):
            strings.append("".join(text.text or "" for text in element.iter(_tag("t"))))
            element.clear()
    return strings


def _cell_text(cell: ElementTree.Element, shared_strings: list[str]) -> str:
    cell_type = cell.get("t")
    if cell_type == "s":
        value = cell.find(_tag("v"))
        if value is None or value.text is None:
            return ""
        try:
            return shared_strings[int(value.text)]
        except (IndexError, ValueError):
            return ""
    if cell_type == "inlineStr":
        return "".join(text.text or "" for text in cell.iter(_tag("t")))

    value = cell.find(_tag("v"))
    return "" if value is None or value.text is None else value.text


def _visible_sheet_paths(workbook: ZipFile) -> Iterable[tuple[str, str]]:
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
    for sheet in workbook_xml.findall(f"{_tag('sheets')}/{_tag('sheet')}"):
        if sheet.get("state", "visible") != "visible":
            continue
        relationship_id = sheet.get(_rel_attr("id"))
        target = targets_by_id.get(relationship_id)
        sheet_name = sheet.get("name") or ""
        if relationship_id is None or target is None:
            raise ProductionPlanningError(
                f"Production planning sheet {sheet_name!r} is missing a target."
            )
        yield sheet_name, _resolve_target("xl/workbook.xml", target)


def _is_hidden_flag(value: str | None) -> bool:
    return value in {"1", "true", "TRUE"}


def _column_a_hidden(column: ElementTree.Element) -> bool:
    try:
        min_column = int(float(column.get("min", "0")))
        max_column = int(float(column.get("max", "0")))
    except ValueError:
        return False
    return min_column <= 1 <= max_column and _is_hidden_flag(column.get("hidden"))


def _visible_column_a_value(
    row: ElementTree.Element,
    shared_strings: list[str],
) -> str:
    for cell in row.findall(_tag("c")):
        column_index = _column_index(cell.get("r", ""))
        if column_index == 1:
            return _cell_text(cell, shared_strings).strip()
        if column_index > 1:
            break
    return ""


def _date_from_planning_filename(path: Path) -> date | None:
    match = PLANNING_FILE_DATE_PATTERN.match(path.name)
    if match is None:
        return None
    try:
        return date(
            int(match.group("year")),
            int(match.group("month")),
            int(match.group("day")),
        )
    except ValueError:
        return None


def _planning_workbook_candidates(directory: str | Path) -> list[PlanningWorkbookCandidate]:
    planning_dir = Path(directory)
    try:
        entries = list(planning_dir.iterdir())
    except FileNotFoundError as exc:
        raise ProductionPlanningError(
            f"Production planning folder was not found: {planning_dir}"
        ) from exc
    except OSError as exc:
        raise ProductionPlanningError(
            f"Production planning folder could not be scanned: {planning_dir}"
        ) from exc

    candidates: list[PlanningWorkbookCandidate] = []
    for path in entries:
        if path.name.startswith(EXCEL_TEMP_PREFIX) or path.suffix.lower() != ".xlsx":
            continue
        try:
            if not path.is_file():
                continue
            stat = path.stat()
        except OSError:
            continue
        candidates.append(
            PlanningWorkbookCandidate(
                path=path,
                date_from_name=_date_from_planning_filename(path),
                modified_ns=stat.st_mtime_ns,
            )
        )
    return candidates


def latest_planning_workbook(directory: str | Path) -> Path:
    """Return the most relevant daily planning workbook from a folder."""

    candidates = _planning_workbook_candidates(directory)
    if not candidates:
        raise ProductionPlanningError(
            f"No production planning .xlsx workbooks were found in: {Path(directory)}"
        )

    dated_candidates = [
        candidate for candidate in candidates if candidate.date_from_name is not None
    ]
    if dated_candidates:
        return max(
            dated_candidates,
            key=lambda candidate: (
                candidate.date_from_name or date.min,
                candidate.modified_ns,
                candidate.path.name.lower(),
            ),
        ).path

    return max(
        candidates,
        key=lambda candidate: (candidate.modified_ns, candidate.path.name.lower()),
    ).path


def resolve_planning_workbook(
    directory: str | Path = "",
    fallback_path: str | Path = "",
) -> Path:
    if str(directory).strip():
        return latest_planning_workbook(directory)
    if str(fallback_path).strip():
        return Path(fallback_path)
    raise ProductionPlanningError(
        "Production planning folder or workbook path must be configured."
    )


def read_visible_planning_orders(path: str | Path) -> list[PlanningOrder]:
    """Read visible job orders from column A without opening the full workbook."""

    planning_path = Path(path)
    try:
        with ZipFile(planning_path) as workbook:
            shared_strings = _shared_strings(workbook)
            orders: list[PlanningOrder] = []
            seen_order_numbers: set[str] = set()

            for sheet_name, sheet_path in _visible_sheet_paths(workbook):
                column_a_is_hidden = False
                for _event, element in ElementTree.iterparse(
                    workbook.open(sheet_path),
                    events=("end",),
                ):
                    if element.tag == _tag("col"):
                        if _column_a_hidden(element):
                            column_a_is_hidden = True
                        element.clear()
                        continue

                    if element.tag != _tag("row"):
                        continue

                    if column_a_is_hidden or _is_hidden_flag(element.get("hidden")):
                        element.clear()
                        continue

                    row_number = int(float(element.get("r", "0") or "0"))
                    cell_value = _visible_column_a_value(element, shared_strings)
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
                    element.clear()
            return orders
    except FileNotFoundError as exc:
        raise ProductionPlanningError(
            f"Production planning workbook was not found: {planning_path}"
        ) from exc
    except (BadZipFile, ElementTree.ParseError, KeyError, OSError) as exc:
        raise ProductionPlanningError(
            f"Production planning workbook could not be read: {planning_path}"
        ) from exc
