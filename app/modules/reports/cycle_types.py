from dataclasses import dataclass
from datetime import date as Date
from decimal import Decimal
from pathlib import Path
from typing import Any

REPORT_HEADERS = (
    "Makine Adı",
    "Makine No.",
    "Ağız",
    "Gramaj",
    "Toplam Göz",
    "Çalışan Göz",
    "Gerçekleşen Çevrim Süresi",
    "Optimum Çevrim Süresi",
    "Kontrol Durumu",
)
STATUS_OK = "Uygun"
STATUS_CHECK = "Kontrol Edilecek"
COMPLETE_STATUSES = frozenset({STATUS_OK, STATUS_CHECK})
CYCLE_TOLERANCE_MULTIPLIER = Decimal("1.10")


class CycleReportError(RuntimeError):
    """Raised when a cycle-control report cannot be created."""


class NoTodayRowsError(CycleReportError):
    """Raised when there are no source rows for the requested report date."""


@dataclass(frozen=True)
class ProcessCycleRow:
    row_number: int
    machine_no: str
    work_order: str
    total_cavity_count: Any
    active_cavity_count: Any
    actual_cycle_time: Decimal | None


@dataclass(frozen=True)
class CycleTableEntry:
    machine_no: str
    machine_group_key: str
    neck_diameter: Decimal
    gram: Decimal
    estimated_cycle_time: Decimal


@dataclass(frozen=True)
class CycleReportRow:
    machine_group: str | None
    machine_no: str
    neck_diameter: Decimal | None
    gram: Decimal | None
    total_cavity_count: Any
    active_cavity_count: Any
    actual_cycle_time: Decimal | None
    optimum_cycle_time: Decimal | None
    control_status: str


@dataclass(frozen=True)
class CycleReportResult:
    output_path: Path
    row_count: int
    matched_count: int
    warning_count: int
    report_date: Date

    def as_dict(self) -> dict[str, Any]:
        return {
            "output_path": str(self.output_path),
            "row_count": self.row_count,
            "matched_count": self.matched_count,
            "warning_count": self.warning_count,
            "date": self.report_date.isoformat(),
        }
