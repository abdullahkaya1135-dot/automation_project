from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from ...config import Settings
from ...domain import shifts
from ...domain.request_values import (
    client_recorded_datetime,
    client_request_id,
    required_text,
    shift_chief,
    stored_client_recorded_at,
)
from ...models import TourContext
from .repository import (
    add_tour_context,
    get_tour_context_by_client_request_id,
)


@dataclass(frozen=True)
class SavedTourContext:
    context: TourContext
    idempotent_replay: bool


def save_tour_context(
    session: Session,
    settings: Settings,
    body: Mapping[str, Any],
) -> SavedTourContext:
    payload = dict(body)
    request_client_id = client_request_id(payload.get("client_request_id"))
    if request_client_id is not None:
        existing_context = get_tour_context_by_client_request_id(
            session,
            request_client_id,
        )
        if existing_context is not None:
            return SavedTourContext(
                context=existing_context,
                idempotent_replay=True,
            )

    client_recorded_at = client_recorded_datetime(
        payload.get("client_recorded_at"),
        settings,
    )
    request_time = client_recorded_at or shifts.request_datetime(settings)
    automatic_timing = shifts.tour_timing_for_datetime(settings, request_time)
    context = TourContext(
        client_request_id=request_client_id,
        client_recorded_at=stored_client_recorded_at(client_recorded_at),
        date=automatic_timing["date"],
        ambient_temp=required_text(
            payload.get("ambient_temp"),
            "ortam sicakligi",
            64,
        ),
        production_engineer=required_text(
            payload.get("production_engineer"),
            "uretim muhendisi",
            255,
        ),
        shift_chief=shift_chief(payload.get("shift_chief")),
        shift=automatic_timing["shift"],
    )
    return SavedTourContext(
        context=add_tour_context(session, context),
        idempotent_replay=False,
    )
