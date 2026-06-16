from ..domain.request_values import validation_error
from ..models import SYNC_STATUSES


def validate_sync_status(sync_status: str | None) -> None:
    if sync_status is not None and sync_status not in SYNC_STATUSES:
        raise validation_error(
            "sync_status şunlardan biri olmalıdır: " + ", ".join(SYNC_STATUSES)
        )
