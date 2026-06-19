from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from ..domain.process_records import (
    PRODUCTION_ENGINEER_NAMES,
    normalize_machine_code,
    normalize_process_date,
    normalize_production_engineer_name,
)
from .config import Settings, get_settings


class Base(DeclarativeBase):
    pass


_engine: Engine | None = None
_database_url: str | None = None
_SessionLocal: sessionmaker[Session] | None = None


class DatabaseCommitError(RuntimeError):
    """Raised after a failed commit has been rolled back."""


_OFFLINE_IDEMPOTENCY_COLUMNS = {
    "tour_contexts": {
        "client_request_id": "VARCHAR(64)",
        "client_recorded_at": "DATETIME",
    },
    "entries": {
        "client_request_id": "VARCHAR(64)",
        "client_recorded_at": "DATETIME",
    },
    "auxiliary_systems_submissions": {
        "client_request_id": "VARCHAR(64)",
        "client_recorded_at": "DATETIME",
    },
    "amount_control_shifts": {
        "client_request_id": "VARCHAR(64)",
        "client_recorded_at": "DATETIME",
    },
}
_ENTRY_COLUMNS = {
    f"col_{letter}": "TEXT"
    for letter in "abcdefghijklmnopqrstuvwxy"
}
_ENTRY_NORMALIZED_COLUMNS = {
    "process_date": "VARCHAR(10)",
    "machine_code": "VARCHAR(16)",
    "production_engineer_id": "INTEGER",
}
_ENTRY_SYNC_COLUMNS = {
    "sync_status": "VARCHAR(32)",
    "excel_row_number": "INTEGER",
    "last_error": "TEXT",
    "submitted_at": "DATETIME",
    "synced_at": "DATETIME",
}
_ENTRY_CANONICAL_FIELDS_MIGRATION = "entries_canonical_fields_v2"
_MACHINE_BREAKDOWNS_AMOUNT_CONTROL_MIGRATION = (
    "machine_breakdowns_amount_control_shift_fk_v1"
)
_PRODUCTION_ENGINEER_SEED_ROWS = tuple(
    {
        "full_name": full_name,
        "display_order": display_order,
    }
    for display_order, full_name in enumerate(PRODUCTION_ENGINEER_NAMES, start=1)
)
_MACHINE_HALLS = (
    (
        1,
        "Hole 1",
        (
            "101",
            "102",
            "103",
            "104",
            "171",
            "172",
            "173",
            "174",
            "175",
            "131",
            "132",
            "133",
            "134",
            "135",
            "138",
        ),
    ),
    (
        2,
        "Hole 2",
        (
            "176",
            "177",
            "178",
            "179",
            "271",
            "161",
            "162",
            "163",
            "164",
            "165",
            "181",
            "182",
        ),
    ),
    (
        3,
        "Hole 3",
        (
            "302",
            "303",
            "401",
            "402",
            "404",
            "405",
            "501",
            "502",
            "503",
            "505",
            "506",
        ),
    ),
    (
        4,
        "Hole 4",
        (
            "202",
            "205",
            "206",
            "207",
            "209",
            "210",
            "212",
            "213",
            "301",
        ),
    ),
)
_MACHINE_SEED_ROWS = tuple(
    {
        "machine_code": machine_code,
        "hall_number": hall_number,
        "hall_name": hall_name,
        "display_order": display_order,
    }
    for hall_number, hall_name, machine_codes in _MACHINE_HALLS
    for display_order, machine_code in enumerate(machine_codes, start=1)
)
_MACHINE_GROUP_SOURCE_ROWS = (
    ("SP25", "101"),
    ("SP80", "102"),
    ("SP80", "103"),
    ("SP80", "104"),
    ("PF4/1", "141"),
    ("PF6/2", "161"),
    ("PF6/2", "162"),
    ("PF6/2", "163"),
    ("PF6/2", "164"),
    ("PF6/2", "165"),
    ("PF8/4", "181"),
    ("50MB", "182"),
    ("50MB", "131"),
    ("50MB", "132"),
    ("50MB", "133"),
    ("50MB", "134"),
    ("50MB", "135"),
    ("12M", "138"),
    ("DPH70", "171"),
    ("DPH70", "172"),
    ("DPH70", "173"),
    ("DPH70", "174"),
    ("DPH70", "175"),
    ("DPH70", "176"),
    ("DPH70", "177"),
    ("DPH70", "178"),
    ("DPH70", "179"),
    ("DPH70", "271"),
    ("ENJK.", "201"),
    ("ENJK.", "202"),
    ("ENJK.", "203"),
    ("ENJK.", "204"),
    ("ENJK.", "205"),
    ("ENJK.", "206"),
    ("ENJK.", "207"),
    ("ENJK.", "207"),
    ("ENJK.", "208"),
    ("ENJK.", "209"),
    ("ENJK.", "210"),
    ("ENJK.", "210"),
    ("ENJK.", "211"),
    ("ENJK.", "212"),
    ("ENJK.", "213"),
    ("ENJK.", "301"),
    ("PREFORM", "302"),
    ("PREFORM", "303"),
    ("PET \u015e\u0130\u015e.", "401"),
    ("PET \u015e\u0130\u015e.", "402"),
    ("PET \u015e\u0130\u015e.", "404"),
    ("PET \u015e\u0130\u015e.", "405"),
    ("UNILOY", "501"),
    ("UNILOY", "502"),
    ("5L\u0130K", "503"),
    ("\u00d6ZKAN", "504"),
    ("\u0130LA\u00c7", "505"),
    ("\u0130LA\u00c7", "506"),
)


def _sqlite_url(sqlite_path: str) -> str:
    path = Path(sqlite_path)
    if not path.is_absolute():
        path = Path.cwd() / path
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{path.as_posix()}"


def configure_database(settings: Settings | None = None) -> sessionmaker[Session]:
    global _engine, _database_url, _SessionLocal

    settings = settings or get_settings()
    database_url = _sqlite_url(settings.sqlite_path)
    if _SessionLocal is not None and _database_url == database_url:
        return _SessionLocal

    _engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False},
        future=True,
    )

    @event.listens_for(_engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    _database_url = database_url
    _SessionLocal = sessionmaker(
        bind=_engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        future=True,
    )
    return _SessionLocal


def get_engine(settings: Settings | None = None) -> Engine:
    configure_database(settings)
    if _engine is None:
        raise RuntimeError("Veritabanı motoru yapılandırılmadı.")
    return _engine


def init_db(settings: Settings | None = None) -> None:
    from .. import models  # noqa: F401
    from ..features.cycle_reports.seed import seed_cycle_table_from_workbook

    settings = settings or get_settings()
    engine = get_engine(settings)
    Base.metadata.create_all(bind=engine)
    with engine.begin() as connection:
        _ensure_columns(connection, "entries", _ENTRY_COLUMNS)
        for table_name, columns in _OFFLINE_IDEMPOTENCY_COLUMNS.items():
            _ensure_columns(connection, table_name, columns)

        connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS "
                "ux_tour_contexts_client_request_id "
                "ON tour_contexts (client_request_id)"
            )
        )
        connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS "
                "ux_entries_client_request_id "
                "ON entries (client_request_id)"
            )
        )
        connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS "
                "ux_auxiliary_systems_submissions_client_request_id "
                "ON auxiliary_systems_submissions (client_request_id)"
            )
        )
        connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS "
                "ux_amount_control_shifts_client_request_id "
                "ON amount_control_shifts (client_request_id)"
            )
        )
        connection.execute(text("DROP TABLE IF EXISTS machines_cache"))
        connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS "
                "ux_machines_machine_code "
                "ON machines (machine_code)"
            )
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS "
                "ix_machines_hall_display_order "
                "ON machines (hall_number, display_order)"
            )
        )
        _seed_machines(connection)
        connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS "
                "ux_production_engineers_full_name "
                "ON production_engineers (full_name)"
            )
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS "
                "ix_production_engineers_display_order "
                "ON production_engineers (display_order)"
            )
        )
        _seed_production_engineers(connection)
        connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS "
                "ux_machine_groups_group_name "
                "ON machine_groups (group_name)"
            )
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS "
                "ix_machine_groups_display_order "
                "ON machine_groups (display_order)"
            )
        )
        connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS "
                "ux_machine_group_machines_machine_id "
                "ON machine_group_machines (machine_id)"
            )
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS "
                "ix_machine_group_machines_group_id "
                "ON machine_group_machines (machine_group_id)"
            )
        )
        _seed_machine_groups(connection)
        seed_cycle_table_from_workbook(connection, settings)
        _migrate_machine_breakdowns_amount_control_shift(connection)
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS "
                "ix_machine_breakdowns_amount_control_shift_id "
                "ON machine_breakdowns (amount_control_shift_id)"
            )
        )
        _migrate_legacy_entry_fields_to_canonical(connection)
        _ensure_columns(connection, "entries", _ENTRY_NORMALIZED_COLUMNS)
        _ensure_columns(connection, "entries", _ENTRY_SYNC_COLUMNS)
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS "
                "ix_entries_process_order "
                "ON entries (process_date, machine_code, production_engineer_id, id)"
            )
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS "
                "ix_entries_process_order_numeric "
                "ON entries (process_date, CAST(machine_code AS INTEGER), "
                "production_engineer_id, id)"
            )
        )
        _backfill_entry_process_metadata(connection)
        _mark_legacy_database_only_entries_pending(connection)


def _ensure_columns(connection, table_name: str, columns: dict[str, str]) -> None:
    existing_columns = {
        row["name"]
        for row in connection.execute(
            text(f"PRAGMA table_info({table_name})")
        ).mappings()
    }
    for column_name, column_type in columns.items():
        if column_name not in existing_columns:
            connection.execute(
                text(
                    f"ALTER TABLE {table_name} "
                    f"ADD COLUMN {column_name} {column_type}"
                )
            )


def _table_columns(connection, table_name: str) -> set[str]:
    return {
        row["name"]
        for row in connection.execute(
            text(f"PRAGMA table_info({table_name})")
        ).mappings()
    }


def _ensure_app_migrations_table(connection) -> None:
    connection.execute(
        text(
            "CREATE TABLE IF NOT EXISTS app_migrations ("
            "name TEXT PRIMARY KEY, "
            "applied_at DATETIME DEFAULT CURRENT_TIMESTAMP"
            ")"
        )
    )


def _migration_applied(connection, name: str) -> bool:
    _ensure_app_migrations_table(connection)
    return (
        connection.execute(
            text("SELECT 1 FROM app_migrations WHERE name = :name"),
            {"name": name},
        ).first()
        is not None
    )


def _mark_migration_applied(connection, name: str) -> None:
    _ensure_app_migrations_table(connection)
    connection.execute(
        text("INSERT OR IGNORE INTO app_migrations (name) VALUES (:name)"),
        {"name": name},
    )


def _migrate_machine_breakdowns_amount_control_shift(connection) -> None:
    migration_name = _MACHINE_BREAKDOWNS_AMOUNT_CONTROL_MIGRATION
    if _migration_applied(connection, migration_name):
        return

    existing_columns = _table_columns(connection, "machine_breakdowns")
    if "amount_control_shift_id" in existing_columns:
        _mark_migration_applied(connection, migration_name)
        return

    connection.execute(text("ALTER TABLE machine_breakdowns RENAME TO machine_breakdowns_old"))
    connection.execute(
        text(
            "CREATE TABLE machine_breakdowns ("
            "id INTEGER NOT NULL, "
            "machine_id INTEGER NOT NULL, "
            "entry_id INTEGER, "
            "amount_control_shift_id INTEGER, "
            "produced_product TEXT NOT NULL, "
            "stop_reason TEXT NOT NULL, "
            "duration_minutes INTEGER NOT NULL, "
            "stopped_at DATETIME, "
            "resumed_at DATETIME, "
            "created_at DATETIME NOT NULL, "
            "updated_at DATETIME NOT NULL, "
            "PRIMARY KEY (id), "
            "CONSTRAINT ck_machine_breakdowns_produced_product "
            "CHECK (trim(produced_product) <> ''), "
            "CONSTRAINT ck_machine_breakdowns_stop_reason "
            "CHECK (trim(stop_reason) <> ''), "
            "CONSTRAINT ck_machine_breakdowns_duration_minutes "
            "CHECK (duration_minutes > 0), "
            "CONSTRAINT ck_machine_breakdowns_stop_time_order "
            "CHECK (stopped_at IS NULL OR resumed_at IS NULL OR resumed_at >= stopped_at), "
            "FOREIGN KEY(machine_id) REFERENCES machines (id) ON DELETE RESTRICT, "
            "FOREIGN KEY(entry_id) REFERENCES entries (id) ON DELETE SET NULL, "
            "FOREIGN KEY(amount_control_shift_id) "
            "REFERENCES amount_control_shifts (id) ON DELETE SET NULL"
            ")"
        )
    )
    connection.execute(
        text(
            "INSERT INTO machine_breakdowns ("
            "id, machine_id, entry_id, amount_control_shift_id, produced_product, "
            "stop_reason, duration_minutes, stopped_at, resumed_at, created_at, updated_at"
            ") SELECT "
            "id, machine_id, entry_id, NULL, produced_product, "
            "stop_reason, duration_minutes, stopped_at, resumed_at, created_at, updated_at "
            "FROM machine_breakdowns_old"
        )
    )
    connection.execute(text("DROP TABLE machine_breakdowns_old"))
    for index_name, columns in (
        ("ix_machine_breakdowns_machine_id", "machine_id"),
        ("ix_machine_breakdowns_entry_id", "entry_id"),
        ("ix_machine_breakdowns_amount_control_shift_id", "amount_control_shift_id"),
        ("ix_machine_breakdowns_stopped_at", "stopped_at"),
        ("ix_machine_breakdowns_created_at", "created_at"),
    ):
        connection.execute(
            text(
                f"CREATE INDEX IF NOT EXISTS {index_name} "
                f"ON machine_breakdowns ({columns})"
            )
        )
    _mark_migration_applied(connection, migration_name)


def _seed_machines(connection) -> None:
    connection.execute(
        text(
            "INSERT INTO machines ("
            "machine_code, hall_number, hall_name, display_order, "
            "created_at, updated_at"
            ") VALUES ("
            ":machine_code, :hall_number, :hall_name, :display_order, "
            "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP"
            ") "
            "ON CONFLICT(machine_code) DO UPDATE SET "
            "hall_number = excluded.hall_number, "
            "hall_name = excluded.hall_name, "
            "display_order = excluded.display_order, "
            "updated_at = CURRENT_TIMESTAMP "
            "WHERE machines.hall_number <> excluded.hall_number "
            "OR machines.hall_name <> excluded.hall_name "
            "OR machines.display_order <> excluded.display_order"
        ),
        _MACHINE_SEED_ROWS,
    )


def _seed_machine_groups(connection) -> None:
    machine_ids_by_code = {
        row["machine_code"]: row["id"]
        for row in connection.execute(
            text("SELECT id, machine_code FROM machines")
        ).mappings()
    }
    group_names: list[str] = []
    seen_group_names: set[str] = set()
    seen_machine_codes: set[str] = set()
    group_machine_rows: list[dict[str, str | int]] = []

    for group_name, machine_code in _MACHINE_GROUP_SOURCE_ROWS:
        machine_id = machine_ids_by_code.get(machine_code)
        if machine_id is None or machine_code in seen_machine_codes:
            continue

        seen_machine_codes.add(machine_code)
        if group_name not in seen_group_names:
            seen_group_names.add(group_name)
            group_names.append(group_name)
        group_machine_rows.append(
            {
                "group_name": group_name,
                "machine_id": machine_id,
            }
        )

    if not group_names:
        return

    connection.execute(
        text(
            "INSERT INTO machine_groups ("
            "group_name, display_order, created_at, updated_at"
            ") VALUES ("
            ":group_name, :display_order, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP"
            ") "
            "ON CONFLICT(group_name) DO UPDATE SET "
            "display_order = excluded.display_order, "
            "updated_at = CURRENT_TIMESTAMP "
            "WHERE machine_groups.display_order <> excluded.display_order"
        ),
        [
            {
                "group_name": group_name,
                "display_order": display_order,
            }
            for display_order, group_name in enumerate(group_names, start=1)
        ],
    )

    group_ids_by_name = {
        row["group_name"]: row["id"]
        for row in connection.execute(
            text("SELECT id, group_name FROM machine_groups")
        ).mappings()
    }
    connection.execute(
        text(
            "INSERT INTO machine_group_machines ("
            "machine_group_id, machine_id, created_at, updated_at"
            ") VALUES ("
            ":machine_group_id, :machine_id, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP"
            ") "
            "ON CONFLICT(machine_id) DO UPDATE SET "
            "machine_group_id = excluded.machine_group_id, "
            "updated_at = CURRENT_TIMESTAMP "
            "WHERE machine_group_machines.machine_group_id "
            "<> excluded.machine_group_id"
        ),
        [
            {
                "machine_group_id": group_ids_by_name[row["group_name"]],
                "machine_id": row["machine_id"],
            }
            for row in group_machine_rows
        ],
    )


def _seed_production_engineers(connection) -> None:
    connection.execute(
        text(
            "INSERT INTO production_engineers ("
            "full_name, display_order, active, created_at, updated_at"
            ") VALUES ("
            ":full_name, :display_order, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP"
            ") "
            "ON CONFLICT(full_name) DO UPDATE SET "
            "display_order = excluded.display_order, "
            "active = 1, "
            "updated_at = CURRENT_TIMESTAMP "
            "WHERE production_engineers.display_order <> excluded.display_order "
            "OR production_engineers.active <> 1"
        ),
        _PRODUCTION_ENGINEER_SEED_ROWS,
    )


def _production_engineer_ids_by_name(connection) -> dict[str, int]:
    return {
        row["full_name"]: row["id"]
        for row in connection.execute(
            text("SELECT id, full_name FROM production_engineers")
        ).mappings()
    }


def _backfill_entry_process_metadata(connection) -> None:
    engineer_ids = _production_engineer_ids_by_name(connection)
    rows = connection.execute(
        text(
            "SELECT id, col_a, col_c, col_f, process_date, machine_code, "
            "production_engineer_id "
            "FROM entries"
        )
    ).mappings()

    updates: list[dict[str, str | int | None]] = []
    for row in rows:
        process_date = normalize_process_date(row["col_a"])
        machine_code = normalize_machine_code(row["col_f"])
        engineer_name = normalize_production_engineer_name(row["col_c"])
        engineer_id = engineer_ids.get(engineer_name or "")

        if (
            row["process_date"] == process_date
            and row["machine_code"] == machine_code
            and row["production_engineer_id"] == engineer_id
            and row["col_c"] == engineer_name
        ):
            continue

        updates.append(
            {
                "id": row["id"],
                "process_date": process_date,
                "machine_code": machine_code,
                "production_engineer_id": engineer_id,
                "col_c": engineer_name,
            }
        )

    if not updates:
        return

    connection.execute(
        text(
            "UPDATE entries SET "
            "process_date = :process_date, "
            "machine_code = :machine_code, "
            "production_engineer_id = :production_engineer_id, "
            "col_c = :col_c "
            "WHERE id = :id"
        ),
        updates,
    )


def _mark_legacy_database_only_entries_pending(connection) -> None:
    connection.execute(
        text(
            "UPDATE entries SET "
            "sync_status = 'pending_excel', "
            "synced_at = NULL, "
            "last_error = NULL "
            "WHERE sync_status = 'synced' "
            "AND excel_row_number IS NULL "
            "AND submitted_at IS NOT NULL"
        )
    )


def _migrate_legacy_entry_fields_to_canonical(connection) -> None:
    if _migration_applied(connection, _ENTRY_CANONICAL_FIELDS_MIGRATION):
        return

    connection.execute(
        text(
            "UPDATE entries SET "
            "col_y = col_q, "
            "col_x = col_p, "
            "col_q = col_o, "
            "col_p = col_n, "
            "col_o = col_m, "
            "col_n = col_l, "
            "col_m = col_k, "
            "col_l = col_j, "
            "col_k = col_i, "
            "col_j = col_h, "
            "col_i = NULL, "
            "col_h = col_g, "
            "col_g = NULL "
            "WHERE col_x IS NULL "
            "AND col_y IS NULL "
            "AND (col_g IS NOT NULL OR col_p IS NOT NULL OR col_q IS NOT NULL)"
        )
    )
    _mark_migration_applied(connection, _ENTRY_CANONICAL_FIELDS_MIGRATION)


def sqlite_health(settings: Settings | None = None) -> dict[str, str | bool]:
    try:
        engine = get_engine(settings)
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"ok": True, "error": ""}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def create_session(settings: Settings | None = None) -> Session:
    return configure_database(settings)()


def commit_session(session: Session) -> None:
    try:
        session.commit()
    except SQLAlchemyError as exc:
        session.rollback()
        raise DatabaseCommitError(
            "Veritabanı kaydı başarısız oldu; değişiklikler geri alındı."
        ) from exc


@contextmanager
def session_scope(settings: Settings | None = None) -> Generator[Session]:
    session = create_session(settings)
    try:
        yield session
        commit_session(session)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Generator[Session]:
    session = create_session()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
