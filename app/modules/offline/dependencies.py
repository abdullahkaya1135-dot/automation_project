from typing import Any

from sqlalchemy.orm import Session

from ...domain.request_values import client_request_id, validation_error
from ...schemas import OfflineBulkRecord
from ..tour_context.repository import get_tour_context_by_client_request_id


def resolve_entry_dependency(
    session: Session,
    body: dict[str, Any],
    record: OfflineBulkRecord,
    context_ids_by_client_id: dict[str, int],
) -> None:
    dependency_client_id = client_request_id(record.depends_on_client_request_id)
    if dependency_client_id is None:
        return

    context_id = context_ids_by_client_id.get(dependency_client_id)
    if context_id is None:
        context = get_tour_context_by_client_request_id(
            session,
            dependency_client_id,
        )
        if context is not None:
            context_id = context.id

    if context_id is None:
        raise validation_error("Bagimli tur bilgisi bulunamadi.")

    body["tour_context_id"] = context_id


__all__ = ["resolve_entry_dependency"]
