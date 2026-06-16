from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AuxiliaryWorkbookSubmission:
    payload: Mapping[str, Any] | object
    recorded_date: Any
    submission_id: int | None = None


@dataclass(frozen=True)
class AuxiliaryBlockResult:
    submission_id: int | None
    start_row: int
    end_row: int
