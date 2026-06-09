import pytest
from sqlalchemy import inspect, text

from app.config import Settings
from app.database import DatabaseCommitError, create_session, init_db, session_scope
from app.models import (
    SYNC_STATUS_PENDING_EXCEL,
    Entry,
    TourContext,
)


def test_sqlite_model_creates_required_tables_and_columns(tmp_path):
    settings = Settings(
        excel_path="dummy.xlsx",
        app_pin="1234",
        sqlite_path=str(tmp_path / "process_entries.sqlite3"),
    )

    init_db(settings)

    with create_session(settings) as session:
        inspector = inspect(session.bind)
        table_names = set(inspector.get_table_names())
        entry_columns = {column["name"] for column in inspector.get_columns("entries")}

    assert table_names >= {"tour_contexts", "entries"}
    assert "machines_cache" not in table_names
    assert {f"col_{letter}" for letter in "abcdefghijklmnopqrstuvwxy"} <= entry_columns
    assert {
        "tour_context_id",
        "status",
        "notes",
        "mold_info",
        "sync_status",
        "excel_row_number",
        "last_error",
        "submitted_at",
        "created_at",
        "updated_at",
        "synced_at",
    } <= entry_columns


def test_session_scope_commits_and_rolls_back_safely(tmp_path):
    settings = Settings(
        excel_path="dummy.xlsx",
        app_pin="1234",
        sqlite_path=str(tmp_path / "process_entries.sqlite3"),
    )
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

    with pytest.raises(DatabaseCommitError):
        with session_scope(settings) as session:
            session.add(Entry(sync_status="not_a_real_sync_status"))

    with create_session(settings) as session:
        assert session.query(Entry).count() == 1


def test_init_db_drops_legacy_machine_cache_table(tmp_path):
    settings = Settings(
        excel_path="dummy.xlsx",
        app_pin="1234",
        sqlite_path=str(tmp_path / "process_entries.sqlite3"),
    )
    init_db(settings)

    with create_session(settings) as session:
        session.execute(
            text(
                "CREATE TABLE machines_cache ("
                "machine_id TEXT PRIMARY KEY, "
                "latest_product TEXT)"
            )
        )
        session.execute(
            text(
                "INSERT INTO machines_cache (machine_id, latest_product) "
                "VALUES ('M-01', 'Product')"
            )
        )
        session.commit()

    init_db(settings)

    with create_session(settings) as session:
        inspector = inspect(session.bind)
        assert "machines_cache" not in set(inspector.get_table_names())
