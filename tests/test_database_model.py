import sqlite3

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
        inspector = inspect(session.get_bind())
        table_names = set(inspector.get_table_names())
        entry_columns = {column["name"] for column in inspector.get_columns("entries")}

    assert table_names >= {"tour_contexts", "entries"}
    assert "machines_cache" not in table_names
    assert {f"col_{letter}" for letter in "abcdefghijklmnopqrstuvwxy"} <= entry_columns
    assert {
        "client_request_id",
        "client_recorded_at",
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


def test_init_db_migrates_existing_tables_for_offline_idempotency(tmp_path):
    sqlite_path = tmp_path / "process_entries.sqlite3"
    connection = sqlite3.connect(sqlite_path)
    try:
        connection.execute("CREATE TABLE tour_contexts (id INTEGER PRIMARY KEY)")
        connection.execute(
            "CREATE TABLE entries ("
            "id INTEGER PRIMARY KEY, "
            "sync_status VARCHAR(32), "
            "tour_context_id INTEGER, "
            "created_at DATETIME)"
        )
        connection.execute(
            "CREATE TABLE auxiliary_systems_submissions ("
            "id INTEGER PRIMARY KEY, "
            "sync_status VARCHAR(32), "
            "recorded_date VARCHAR(32), "
            "created_at DATETIME)"
        )
        connection.commit()
    finally:
        connection.close()

    settings = Settings(
        excel_path="dummy.xlsx",
        app_pin="1234",
        sqlite_path=str(sqlite_path),
    )

    init_db(settings)

    with create_session(settings) as session:
        inspector = inspect(session.get_bind())
        for table_name in (
            "tour_contexts",
            "entries",
            "auxiliary_systems_submissions",
        ):
            columns = {
                column["name"]
                for column in inspector.get_columns(table_name)
            }
            assert {"client_request_id", "client_recorded_at"} <= columns


def test_init_db_canonicalizes_legacy_entry_columns_once(tmp_path):
    sqlite_path = tmp_path / "process_entries.sqlite3"
    connection = sqlite3.connect(sqlite_path)
    try:
        connection.execute(
            "CREATE TABLE entries ("
            "id INTEGER PRIMARY KEY, "
            "col_f TEXT, "
            "col_g TEXT, "
            "col_h TEXT, "
            "col_i TEXT, "
            "col_j TEXT, "
            "col_k TEXT, "
            "col_l TEXT, "
            "col_m TEXT, "
            "col_n TEXT, "
            "col_o TEXT, "
            "col_p TEXT, "
            "col_q TEXT, "
            "col_x TEXT, "
            "col_y TEXT, "
            "sync_status VARCHAR(32), "
            "created_at DATETIME)"
        )
        connection.execute(
            "INSERT INTO entries ("
            "id, col_f, col_g, col_h, col_i, col_j, col_p, col_q, sync_status"
            ") VALUES (1, '101', 'WO-1', '16', '12', '12.5', '270x2', '30x2', 'synced')"
        )
        connection.commit()
    finally:
        connection.close()

    settings = Settings(
        excel_path="dummy.xlsx",
        app_pin="1234",
        sqlite_path=str(sqlite_path),
    )

    init_db(settings)
    init_db(settings)

    connection = sqlite3.connect(sqlite_path)
    try:
        row = connection.execute(
            "SELECT col_g, col_h, col_j, col_k, col_l, col_x, col_y "
            "FROM entries WHERE id = 1"
        ).fetchone()
    finally:
        connection.close()

    assert row == (None, "WO-1", "16", "12", "12.5", "270x2", "30x2")


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

    with pytest.raises(DatabaseCommitError), session_scope(settings) as session:
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
        inspector = inspect(session.get_bind())
        assert "machines_cache" not in set(inspector.get_table_names())
