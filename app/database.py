from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

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
}
_ENTRY_COLUMNS = {
    f"col_{letter}": "TEXT"
    for letter in "abcdefghijklmnopqrstuvwxy"
}
_ENTRY_CANONICAL_FIELDS_MIGRATION = "entries_canonical_fields_v2"


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
    from . import models  # noqa: F401

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
        connection.execute(text("DROP TABLE IF EXISTS machines_cache"))
        _migrate_legacy_entry_fields_to_canonical(connection)


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


def _migrate_legacy_entry_fields_to_canonical(connection) -> None:
    connection.execute(
        text(
            "CREATE TABLE IF NOT EXISTS app_migrations ("
            "name TEXT PRIMARY KEY, "
            "applied_at DATETIME DEFAULT CURRENT_TIMESTAMP"
            ")"
        )
    )
    already_applied = connection.execute(
        text("SELECT 1 FROM app_migrations WHERE name = :name"),
        {"name": _ENTRY_CANONICAL_FIELDS_MIGRATION},
    ).first()
    if already_applied is not None:
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
    connection.execute(
        text("INSERT INTO app_migrations (name) VALUES (:name)"),
        {"name": _ENTRY_CANONICAL_FIELDS_MIGRATION},
    )


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
