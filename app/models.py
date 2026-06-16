from datetime import UTC, datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base

SYNC_STATUS_SYNCED = "synced"
SYNC_STATUS_PENDING_EXCEL = "pending_excel"
SYNC_STATUS_FAILED_EXCEL = "failed_excel"
SYNC_STATUSES = (
    SYNC_STATUS_SYNCED,
    SYNC_STATUS_PENDING_EXCEL,
    SYNC_STATUS_FAILED_EXCEL,
)


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class TourContext(Base):
    __tablename__ = "tour_contexts"
    __table_args__ = (
        Index(
            "ux_tour_contexts_client_request_id",
            "client_request_id",
            unique=True,
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    client_recorded_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )
    date: Mapped[str] = mapped_column(String(32), nullable=False)
    ambient_temp: Mapped[str] = mapped_column(String(64), nullable=False)
    production_engineer: Mapped[str] = mapped_column(String(255), nullable=False)
    shift_chief: Mapped[str] = mapped_column(String(255), nullable=False)
    shift: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    entries: Mapped[list[Entry]] = relationship(back_populates="tour_context")


class Entry(Base):
    __tablename__ = "entries"
    __table_args__ = (
        CheckConstraint(
            "sync_status IN ('synced', 'pending_excel', 'failed_excel')",
            name="ck_entries_sync_status",
        ),
        Index("ix_entries_sync_status", "sync_status"),
        Index("ix_entries_tour_context_id", "tour_context_id"),
        Index("ix_entries_created_at", "created_at"),
        Index("ux_entries_client_request_id", "client_request_id", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    client_recorded_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )
    tour_context_id: Mapped[int | None] = mapped_column(
        ForeignKey("tour_contexts.id", ondelete="SET NULL"),
        nullable=True,
    )
    col_a: Mapped[str | None] = mapped_column(Text, nullable=True)
    col_b: Mapped[str | None] = mapped_column(Text, nullable=True)
    col_c: Mapped[str | None] = mapped_column(Text, nullable=True)
    col_d: Mapped[str | None] = mapped_column(Text, nullable=True)
    col_e: Mapped[str | None] = mapped_column(Text, nullable=True)
    col_f: Mapped[str | None] = mapped_column(Text, nullable=True)
    col_g: Mapped[str | None] = mapped_column(Text, nullable=True)
    col_h: Mapped[str | None] = mapped_column(Text, nullable=True)
    col_i: Mapped[str | None] = mapped_column(Text, nullable=True)
    col_j: Mapped[str | None] = mapped_column(Text, nullable=True)
    col_k: Mapped[str | None] = mapped_column(Text, nullable=True)
    col_l: Mapped[str | None] = mapped_column(Text, nullable=True)
    col_m: Mapped[str | None] = mapped_column(Text, nullable=True)
    col_n: Mapped[str | None] = mapped_column(Text, nullable=True)
    col_o: Mapped[str | None] = mapped_column(Text, nullable=True)
    col_p: Mapped[str | None] = mapped_column(Text, nullable=True)
    col_q: Mapped[str | None] = mapped_column(Text, nullable=True)
    col_r: Mapped[str | None] = mapped_column(Text, nullable=True)
    col_s: Mapped[str | None] = mapped_column(Text, nullable=True)
    col_t: Mapped[str | None] = mapped_column(Text, nullable=True)
    col_u: Mapped[str | None] = mapped_column(Text, nullable=True)
    col_v: Mapped[str | None] = mapped_column(Text, nullable=True)
    col_w: Mapped[str | None] = mapped_column(Text, nullable=True)
    col_x: Mapped[str | None] = mapped_column(Text, nullable=True)
    col_y: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    mold_info: Mapped[str | None] = mapped_column(Text, nullable=True)
    sync_status: Mapped[str] = mapped_column(
        String(32),
        default=SYNC_STATUS_PENDING_EXCEL,
        server_default=SYNC_STATUS_PENDING_EXCEL,
        nullable=False,
    )
    excel_row_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )
    synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    tour_context: Mapped[TourContext | None] = relationship(back_populates="entries")


class AuxiliarySystemsSubmission(Base):
    __tablename__ = "auxiliary_systems_submissions"
    __table_args__ = (
        CheckConstraint(
            "sync_status IN ('synced', 'pending_excel', 'failed_excel')",
            name="ck_auxiliary_systems_submissions_sync_status",
        ),
        Index(
            "ix_auxiliary_systems_submissions_sync_status",
            "sync_status",
        ),
        Index(
            "ix_auxiliary_systems_submissions_recorded_date",
            "recorded_date",
        ),
        Index(
            "ix_auxiliary_systems_submissions_created_at",
            "created_at",
        ),
        Index(
            "ux_auxiliary_systems_submissions_client_request_id",
            "client_request_id",
            unique=True,
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    client_recorded_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )
    recorded_date: Mapped[str] = mapped_column(String(32), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    sync_status: Mapped[str] = mapped_column(
        String(32),
        default=SYNC_STATUS_PENDING_EXCEL,
        server_default=SYNC_STATUS_PENDING_EXCEL,
        nullable=False,
    )
    excel_start_row: Mapped[int | None] = mapped_column(Integer, nullable=True)
    excel_end_row: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )
    synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
