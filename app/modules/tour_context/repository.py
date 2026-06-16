from sqlalchemy import select
from sqlalchemy.orm import Session

from ...models import TourContext


def add_tour_context(session: Session, context: TourContext) -> TourContext:
    session.add(context)
    session.flush()
    return context


def get_tour_context(session: Session, context_id: int | None) -> TourContext | None:
    if context_id is None:
        return None
    return session.get(TourContext, context_id)


def get_tour_context_by_client_request_id(
    session: Session,
    client_request_id: str,
) -> TourContext | None:
    return session.scalars(
        select(TourContext).where(TourContext.client_request_id == client_request_id)
    ).first()


def latest_tour_context(session: Session) -> TourContext | None:
    return session.scalars(
        select(TourContext).order_by(
            TourContext.updated_at.desc(),
            TourContext.id.desc(),
        )
    ).first()
