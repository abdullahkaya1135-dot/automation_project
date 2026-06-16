from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from threading import Lock


@dataclass(frozen=True)
class ExcelWriteLockStatus:
    locked: bool
    waiting: int
    active_operation: str | None
    total_acquired: int

    def as_dict(self) -> dict[str, int | str | bool | None]:
        return asdict(self)


class ExcelWriteLock:
    def __init__(self) -> None:
        self._write_lock = Lock()
        self._state_lock = Lock()
        self._waiting = 0
        self._active_operation: str | None = None
        self._total_acquired = 0

    @contextmanager
    def acquire(self, operation: str) -> Generator[None]:
        operation_name = operation.strip() or "excel_write"
        with self._state_lock:
            self._waiting += 1

        self._write_lock.acquire()
        with self._state_lock:
            self._waiting -= 1
            self._active_operation = operation_name
            self._total_acquired += 1

        try:
            yield
        finally:
            with self._state_lock:
                self._active_operation = None
            self._write_lock.release()

    def status(self) -> ExcelWriteLockStatus:
        with self._state_lock:
            return ExcelWriteLockStatus(
                locked=self._active_operation is not None,
                waiting=self._waiting,
                active_operation=self._active_operation,
                total_acquired=self._total_acquired,
            )


_excel_write_lock = ExcelWriteLock()


@contextmanager
def serialized_excel_write(operation: str) -> Generator[None]:
    with _excel_write_lock.acquire(operation):
        yield


def excel_write_lock_status() -> dict[str, int | str | bool | None]:
    return _excel_write_lock.status().as_dict()
