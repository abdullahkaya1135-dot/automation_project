import sqlite3

from sqlalchemy import inspect, text

from app.core.database import create_session, init_db
from app.models import MachineBreakdown

from .helpers import sqlite_settings


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
        connection.execute(
            "CREATE TABLE amount_control_shifts (id INTEGER PRIMARY KEY)"
        )
        connection.commit()
    finally:
        connection.close()

    settings = sqlite_settings(tmp_path, sqlite_path=str(sqlite_path))

    init_db(settings)

    with create_session(settings) as session:
        inspector = inspect(session.get_bind())
        for table_name in (
            "tour_contexts",
            "entries",
            "auxiliary_systems_submissions",
            "amount_control_shifts",
        ):
            columns = {column["name"] for column in inspector.get_columns(table_name)}
            assert {"client_request_id", "client_recorded_at"} <= columns


def test_init_db_migrates_production_loss_shift_snapshot_columns(tmp_path):
    sqlite_path = tmp_path / "process_entries.sqlite3"
    connection = sqlite3.connect(sqlite_path)
    try:
        connection.execute(
            "CREATE TABLE production_loss_reports ("
            "id INTEGER PRIMARY KEY, "
            "date_from VARCHAR(10) NOT NULL, "
            "date_to VARCHAR(10) NOT NULL, "
            "generated_at DATETIME NOT NULL, "
            "row_count INTEGER NOT NULL, "
            "warning_count INTEGER NOT NULL, "
            "source_summary_json TEXT NOT NULL, "
            "created_at DATETIME NOT NULL, "
            "updated_at DATETIME NOT NULL)"
        )
        connection.execute(
            "CREATE TABLE production_loss_report_rows ("
            "id INTEGER PRIMARY KEY, "
            "report_id INTEGER NOT NULL, "
            "record_date VARCHAR(10) NOT NULL, "
            "machine_code VARCHAR(16) NOT NULL, "
            "job_order TEXT NOT NULL, "
            "shift_2400_0800_quantity INTEGER NOT NULL, "
            "shift_0800_1600_quantity INTEGER NOT NULL, "
            "shift_1600_2400_quantity INTEGER NOT NULL, "
            "daily_total_quantity INTEGER NOT NULL, "
            "local_breakdown_minutes INTEGER NOT NULL, "
            "created_at DATETIME NOT NULL, "
            "updated_at DATETIME NOT NULL)"
        )
        connection.execute(
            "INSERT INTO production_loss_reports ("
            "id, date_from, date_to, generated_at, row_count, warning_count, "
            "source_summary_json, created_at, updated_at"
            ") VALUES ("
            "1, '2026-06-17', '2026-06-17', CURRENT_TIMESTAMP, 1, 0, '{}', "
            "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        )
        connection.execute(
            "INSERT INTO production_loss_report_rows ("
            "id, report_id, record_date, machine_code, job_order, "
            "shift_2400_0800_quantity, shift_0800_1600_quantity, "
            "shift_1600_2400_quantity, daily_total_quantity, "
            "local_breakdown_minutes, created_at, updated_at"
            ") VALUES ("
            "1, 1, '2026-06-17', '101', 'WO-1', 10, 20, 30, 60, 0, "
            "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        )
        connection.commit()
    finally:
        connection.close()

    settings = sqlite_settings(tmp_path, sqlite_path=str(sqlite_path))

    init_db(settings)
    init_db(settings)

    connection = sqlite3.connect(sqlite_path)
    try:
        columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(production_loss_report_rows)"
            )
        }
        row = connection.execute(
            "SELECT "
            "shift_2400_0800_quantity, shift_2400_0800_actual_quantity, "
            "shift_2400_0800_machine_minutes, "
            "shift_2400_0800_optimum_quantity, shift_2400_0800_loss_quantity, "
            "shift_0800_1600_quantity, shift_0800_1600_actual_quantity, "
            "shift_0800_1600_machine_minutes, "
            "shift_0800_1600_optimum_quantity, shift_0800_1600_loss_quantity, "
            "shift_1600_2400_quantity, shift_1600_2400_actual_quantity, "
            "shift_1600_2400_machine_minutes, "
            "shift_1600_2400_optimum_quantity, shift_1600_2400_loss_quantity "
            "FROM production_loss_report_rows WHERE id = 1"
        ).fetchone()
    finally:
        connection.close()

    assert {
        "lot_batch_no",
        "shift_2400_0800_actual_quantity",
        "shift_2400_0800_machine_minutes",
        "shift_2400_0800_optimum_quantity",
        "shift_2400_0800_loss_quantity",
        "shift_0800_1600_actual_quantity",
        "shift_0800_1600_machine_minutes",
        "shift_0800_1600_optimum_quantity",
        "shift_0800_1600_loss_quantity",
        "shift_1600_2400_actual_quantity",
        "shift_1600_2400_machine_minutes",
        "shift_1600_2400_optimum_quantity",
        "shift_1600_2400_loss_quantity",
    } <= columns
    assert row == (
        10,
        10,
        None,
        None,
        None,
        20,
        20,
        None,
        None,
        None,
        30,
        30,
        None,
        None,
        None,
    )


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

    settings = sqlite_settings(tmp_path, sqlite_path=str(sqlite_path))

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


def test_init_db_backfills_entry_process_metadata(tmp_path):
    sqlite_path = tmp_path / "process_entries.sqlite3"
    connection = sqlite3.connect(sqlite_path)
    try:
        connection.execute(
            "CREATE TABLE entries ("
            "id INTEGER PRIMARY KEY, "
            "col_a TEXT, "
            "col_c TEXT, "
            "col_f TEXT, "
            "sync_status VARCHAR(32), "
            "created_at DATETIME)"
        )
        connection.execute(
            "INSERT INTO entries (id, col_a, col_c, col_f, sync_status) "
            "VALUES (1, '17.06.2026', 'BARIŞ ÇETİK', 'M-101', 'synced')"
        )
        connection.commit()
    finally:
        connection.close()

    settings = sqlite_settings(tmp_path, sqlite_path=str(sqlite_path))

    init_db(settings)

    connection = sqlite3.connect(sqlite_path)
    try:
        row = connection.execute(
            "SELECT process_date, machine_code, col_c, production_engineer_id "
            "FROM entries WHERE id = 1"
        ).fetchone()
    finally:
        connection.close()

    assert row == ("2026-06-17", "101", "Barış Çetik", 1)


def test_init_db_migrates_machine_breakdowns_amount_control_link(tmp_path):
    sqlite_path = tmp_path / "process_entries.sqlite3"
    connection = sqlite3.connect(sqlite_path)
    try:
        connection.execute(
            "CREATE TABLE machines ("
            "id INTEGER PRIMARY KEY, "
            "machine_code VARCHAR(16) NOT NULL, "
            "hall_number INTEGER NOT NULL, "
            "hall_name VARCHAR(32) NOT NULL, "
            "display_order INTEGER NOT NULL, "
            "created_at DATETIME NOT NULL, "
            "updated_at DATETIME NOT NULL)"
        )
        connection.execute(
            "CREATE TABLE entries ("
            "id INTEGER PRIMARY KEY, "
            "sync_status VARCHAR(32), "
            "created_at DATETIME)"
        )
        connection.execute(
            "CREATE TABLE machine_breakdowns ("
            "id INTEGER PRIMARY KEY, "
            "machine_id INTEGER NOT NULL, "
            "entry_id INTEGER, "
            "produced_product TEXT NOT NULL, "
            "stop_reason TEXT NOT NULL, "
            "duration_minutes INTEGER NOT NULL, "
            "stopped_at DATETIME, "
            "resumed_at DATETIME, "
            "created_at DATETIME NOT NULL, "
            "updated_at DATETIME NOT NULL)"
        )
        connection.execute(
            "INSERT INTO machines ("
            "id, machine_code, hall_number, hall_name, display_order, created_at, updated_at"
            ") VALUES (1, '101', 1, 'Hole 1', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        )
        connection.execute(
            "INSERT INTO entries (id, sync_status, created_at) "
            "VALUES (1, 'synced', CURRENT_TIMESTAMP)"
        )
        connection.execute(
            "INSERT INTO machine_breakdowns ("
            "id, machine_id, entry_id, produced_product, stop_reason, duration_minutes, "
            "created_at, updated_at"
            ") VALUES (1, 1, 1, 'Product 101', 'Hydraulic pressure fault', 45, "
            "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        )
        connection.commit()
    finally:
        connection.close()

    settings = sqlite_settings(tmp_path, sqlite_path=str(sqlite_path))
    init_db(settings)
    init_db(settings)

    with create_session(settings) as session:
        inspector = inspect(session.get_bind())
        breakdown_column_info = inspector.get_columns("machine_breakdowns")
        columns = {column["name"] for column in breakdown_column_info}
        foreign_keys = inspector.get_foreign_keys("machine_breakdowns")
        breakdown = session.query(MachineBreakdown).one()

    assert "amount_control_shift_id" in columns
    assert {
        "client_request_id",
        "client_recorded_at",
        "record_date",
        "shift",
        "job_order",
    } <= columns
    assert {column["name"]: column["nullable"] for column in breakdown_column_info}[
        "produced_product"
    ] is True
    assert breakdown.produced_product == "Product 101"
    assert breakdown.entry_id == 1
    assert breakdown.amount_control_shift_id is None
    assert {
        (
            tuple(foreign_key["constrained_columns"]),
            foreign_key["referred_table"],
            tuple(foreign_key["referred_columns"]),
            foreign_key["options"].get("ondelete"),
        )
        for foreign_key in foreign_keys
    } >= {
        (
            ("amount_control_shift_id",),
            "amount_control_shifts",
            ("id",),
            "SET NULL",
        ),
    }


def test_init_db_backfills_breakdown_context_from_amount_control_shift(tmp_path):
    sqlite_path = tmp_path / "process_entries.sqlite3"
    connection = sqlite3.connect(sqlite_path)
    try:
        connection.execute(
            "CREATE TABLE machines ("
            "id INTEGER PRIMARY KEY, "
            "machine_code VARCHAR(16) NOT NULL, "
            "hall_number INTEGER NOT NULL, "
            "hall_name VARCHAR(32) NOT NULL, "
            "display_order INTEGER NOT NULL, "
            "created_at DATETIME NOT NULL, "
            "updated_at DATETIME NOT NULL)"
        )
        connection.execute(
            "CREATE TABLE amount_control_shifts ("
            "id INTEGER PRIMARY KEY, "
            "record_date VARCHAR(10) NOT NULL, "
            "machine_id INTEGER NOT NULL, "
            "job_order TEXT NOT NULL, "
            "shift VARCHAR(16) NOT NULL, "
            "worker_names TEXT NOT NULL, "
            "produced_quantity INTEGER NOT NULL, "
            "created_at DATETIME NOT NULL, "
            "updated_at DATETIME NOT NULL)"
        )
        connection.execute(
            "CREATE TABLE machine_breakdowns ("
            "id INTEGER PRIMARY KEY, "
            "machine_id INTEGER NOT NULL, "
            "entry_id INTEGER, "
            "amount_control_shift_id INTEGER, "
            "produced_product TEXT NOT NULL, "
            "stop_reason TEXT NOT NULL, "
            "duration_minutes INTEGER NOT NULL, "
            "stopped_at DATETIME, "
            "resumed_at DATETIME, "
            "created_at DATETIME NOT NULL, "
            "updated_at DATETIME NOT NULL)"
        )
        connection.execute(
            "INSERT INTO machines ("
            "id, machine_code, hall_number, hall_name, display_order, created_at, updated_at"
            ") VALUES (1, '101', 1, 'Hole 1', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        )
        connection.execute(
            "INSERT INTO amount_control_shifts ("
            "id, record_date, machine_id, job_order, shift, worker_names, "
            "produced_quantity, created_at, updated_at"
            ") VALUES (1, '2026-06-17', 1, 'WO-1', '08.00-16.00', "
            "'Operator One', 1200, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        )
        connection.execute(
            "INSERT INTO machine_breakdowns ("
            "id, machine_id, amount_control_shift_id, produced_product, "
            "stop_reason, duration_minutes, created_at, updated_at"
            ") VALUES (1, 1, 1, 'Product 101', 'Mold change', 30, "
            "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        )
        connection.commit()
    finally:
        connection.close()

    settings = sqlite_settings(tmp_path, sqlite_path=str(sqlite_path))
    init_db(settings)

    with create_session(settings) as session:
        breakdown = session.query(MachineBreakdown).one()

    assert breakdown.amount_control_shift_id == 1
    assert breakdown.record_date == "2026-06-17"
    assert breakdown.shift == "08.00-16.00"
    assert breakdown.job_order == "WO-1"


def test_init_db_drops_legacy_machine_cache_table(tmp_path):
    settings = sqlite_settings(tmp_path)
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
