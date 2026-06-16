from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class UseCaseResult:
    status_code: int
    payload: dict[str, Any]
