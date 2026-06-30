import pytest

from app.core.database import (
    DatabaseCommitError,
    create_session,
    init_db,
    session_scope,
)
from app.models import SYNC_STATUS_PENDING_EXCEL, Entry, TourContext

from .helpers import sqlite_settings


def test_session_scope_commits_and_rolls_back_safely(tmp_path):
    settings = sqlite_settings(tmp_path)
    init_db(settings)

    with session_scope(settings) as session:
        context = TourContext(
            date="2026-06-08",
            ambient_temp="24",
            production_engineer="Engineer",
            shift_chief="Selman",
            shift="A",
        )
        session.add(context)
        session.flush()
        session.add(
            Entry(
                tour_context_id=context.id,
                col_a="sample",
                sync_status=SYNC_STATUS_PENDING_EXCEL,
            )
        )

    with create_session(settings) as session:
        assert session.query(TourContext).count() == 1
        assert session.query(Entry).count() == 1

    with pytest.raises(DatabaseCommitError), session_scope(settings) as session:
        session.add(Entry(sync_status="not_a_real_sync_status"))

    with create_session(settings) as session:
        assert session.query(Entry).count() == 1
