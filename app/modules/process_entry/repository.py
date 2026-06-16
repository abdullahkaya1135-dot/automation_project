from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ...models import Entry


def add_entry(session: Session, entry: Entry) -> Entry:
    session.add(entry)
    session.flush()
    return entry


def get_entry_by_client_request_id(
    session: Session,
    client_request_id: str,
) -> Entry | None:
    return session.scalars(
        select(Entry).where(Entry.client_request_id == client_request_id)
    ).first()


def list_entries(
    session: Session,
    *,
    sync_status: str | None,
    limit: int,
) -> list[Entry]:
    query = (
        select(Entry)
        .options(selectinload(Entry.tour_context))
        .order_by(Entry.created_at.desc(), Entry.id.desc())
        .limit(limit)
    )
    if sync_status is not None:
        query = query.where(Entry.sync_status == sync_status)
    return list(session.scalars(query).all())


def list_unsynced_entries(
    session: Session,
    *,
    statuses: Sequence[str],
    limit: int,
) -> list[Entry]:
    return list(
        session.scalars(
            select(Entry)
            .where(Entry.sync_status.in_(statuses))
            .order_by(Entry.created_at.asc(), Entry.id.asc())
            .limit(limit)
        ).all()
    )


def count_entries_by_statuses(session: Session, statuses: Sequence[str]) -> int:
    return int(
        session.scalar(
            select(func.count())
            .select_from(Entry)
            .where(Entry.sync_status.in_(statuses))
        )
        or 0
    )


def latest_sync_error(session: Session) -> str | None:
    entry = session.scalars(
        select(Entry)
        .where(Entry.last_error.is_not(None))
        .where(Entry.last_error != "")
        .order_by(Entry.updated_at.desc(), Entry.id.desc())
    ).first()
    if entry is None:
        return None
    return entry.last_error
