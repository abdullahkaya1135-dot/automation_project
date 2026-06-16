from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...models import AuxiliarySystemsSubmission


def add_auxiliary_submission(
    session: Session,
    submission: AuxiliarySystemsSubmission,
) -> AuxiliarySystemsSubmission:
    session.add(submission)
    session.flush()
    return submission


def get_auxiliary_submission_by_client_request_id(
    session: Session,
    client_request_id: str,
) -> AuxiliarySystemsSubmission | None:
    return session.scalars(
        select(AuxiliarySystemsSubmission).where(
            AuxiliarySystemsSubmission.client_request_id == client_request_id
        )
    ).first()


def list_auxiliary_submissions(
    session: Session,
    *,
    sync_status: str | None,
    limit: int,
) -> list[AuxiliarySystemsSubmission]:
    query = (
        select(AuxiliarySystemsSubmission)
        .order_by(
            AuxiliarySystemsSubmission.created_at.desc(),
            AuxiliarySystemsSubmission.id.desc(),
        )
        .limit(limit)
    )
    if sync_status is not None:
        query = query.where(AuxiliarySystemsSubmission.sync_status == sync_status)
    return list(session.scalars(query).all())


def list_unsynced_auxiliary_submissions(
    session: Session,
    *,
    statuses: Sequence[str],
    limit: int,
) -> list[AuxiliarySystemsSubmission]:
    return list(
        session.scalars(
            select(AuxiliarySystemsSubmission)
            .where(AuxiliarySystemsSubmission.sync_status.in_(statuses))
            .order_by(
                AuxiliarySystemsSubmission.created_at.asc(),
                AuxiliarySystemsSubmission.id.asc(),
            )
            .limit(limit)
        ).all()
    )


def count_auxiliary_submissions_by_statuses(
    session: Session,
    statuses: Sequence[str],
) -> int:
    return int(
        session.scalar(
            select(func.count())
            .select_from(AuxiliarySystemsSubmission)
            .where(AuxiliarySystemsSubmission.sync_status.in_(statuses))
        )
        or 0
    )


def latest_auxiliary_sync_error(session: Session) -> str | None:
    submission = session.scalars(
        select(AuxiliarySystemsSubmission)
        .where(AuxiliarySystemsSubmission.last_error.is_not(None))
        .where(AuxiliarySystemsSubmission.last_error != "")
        .order_by(
            AuxiliarySystemsSubmission.updated_at.desc(),
            AuxiliarySystemsSubmission.id.desc(),
        )
    ).first()
    if submission is None:
        return None
    return submission.last_error
