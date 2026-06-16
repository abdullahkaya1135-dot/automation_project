from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import Settings, get_settings
from .db.migrations import ensure_schema_migrations


class Base(DeclarativeBase):
    pass


_engine: Engine | None = None
_database_url: str | None = None
_SessionLocal: sessionmaker[Session] | None = None


class DatabaseCommitError(RuntimeError):
    """Raised after a failed commit has been rolled back."""


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
        ensure_schema_migrations(connection)


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
