from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import httpx
from openpyxl import Workbook

MULTI_PREFIX_FILTER = (
    "(startswith(PartNo,'HM-02') or startswith(PartNo,'HM-03') "
    "or startswith(PartNo,'HM-04'))"
)


class RequestRecorder:
    def __init__(self, requests: list[httpx.Request] | None = None) -> None:
        self.requests = requests if requests is not None else []

    def wrap(
        self,
        handler: Callable[[httpx.Request], httpx.Response],
    ) -> Callable[[httpx.Request], httpx.Response]:
        def wrapped(request: httpx.Request) -> httpx.Response:
            self.requests.append(request)
            return handler(request)

        return wrapped


def create_planning_workbook(path: str | Path, values: list[object]) -> None:
    workbook = Workbook()
    worksheet = workbook.active
    for row_index, value in enumerate(values, start=1):
        worksheet.cell(row=row_index, column=1, value=value)
    workbook.save(path)
    workbook.close()
