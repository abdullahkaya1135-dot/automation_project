import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .errors import ProductionPlanningError

PLANNING_FILE_DATE_PATTERN = re.compile(
    r"^\s*(?P<day>\d{1,2})\.(?P<month>\d{1,2})\.(?P<year>\d{4})\b"
)
EXCEL_TEMP_PREFIX = "~$"


@dataclass(frozen=True)
class PlanningWorkbookCandidate:
    path: Path
    date_from_name: date | None
    modified_ns: int


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
