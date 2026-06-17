from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
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


class Machine(Base):
    __tablename__ = "machines"
    __table_args__ = (
        CheckConstraint("hall_number BETWEEN 1 AND 4", name="ck_machines_hall_number"),
        CheckConstraint("machine_code <> ''", name="ck_machines_machine_code"),
        Index("ix_machines_hall_display_order", "hall_number", "display_order"),
        Index("ux_machines_machine_code", "machine_code", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    machine_code: Mapped[str] = mapped_column(String(16), nullable=False)
    hall_number: Mapped[int] = mapped_column(Integer, nullable=False)
    hall_name: Mapped[str] = mapped_column(String(32), nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)
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

    group_links: Mapped[list[MachineGroupMachine]] = relationship(
        back_populates="machine",
    )
    breakdowns: Mapped[list[MachineBreakdown]] = relationship(
        back_populates="machine",
    )
    amount_control_shifts: Mapped[list[AmountControlShift]] = relationship(
        back_populates="machine",
    )


class MachineGroup(Base):
    __tablename__ = "machine_groups"
    __table_args__ = (
        CheckConstraint("group_name <> ''", name="ck_machine_groups_group_name"),
        Index("ux_machine_groups_group_name", "group_name", unique=True),
        Index("ix_machine_groups_display_order", "display_order"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_name: Mapped[str] = mapped_column(String(64), nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)
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

    machine_links: Mapped[list[MachineGroupMachine]] = relationship(
        back_populates="machine_group",
        cascade="all, delete-orphan",
    )


class MachineGroupMachine(Base):
    __tablename__ = "machine_group_machines"
    __table_args__ = (
        Index("ux_machine_group_machines_machine_id", "machine_id", unique=True),
        Index("ix_machine_group_machines_group_id", "machine_group_id"),
    )

    machine_group_id: Mapped[int] = mapped_column(
        ForeignKey("machine_groups.id", ondelete="CASCADE"),
        primary_key=True,
    )
    machine_id: Mapped[int] = mapped_column(
        ForeignKey("machines.id", ondelete="CASCADE"),
        primary_key=True,
    )
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

    machine_group: Mapped[MachineGroup] = relationship(
        back_populates="machine_links",
    )
    machine: Mapped[Machine] = relationship(back_populates="group_links")


class ProductionEngineer(Base):
    __tablename__ = "production_engineers"
    __table_args__ = (
        CheckConstraint("full_name <> ''", name="ck_production_engineers_full_name"),
        Index("ux_production_engineers_full_name", "full_name", unique=True),
        Index("ix_production_engineers_display_order", "display_order"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)
    active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="1",
        nullable=False,
    )
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

    entries: Mapped[list[Entry]] = relationship(back_populates="production_engineer")


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
        Index(
            "ix_entries_process_order",
            "process_date",
            "machine_code",
            "production_engineer_id",
            "id",
        ),
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
    process_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    machine_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    production_engineer_id: Mapped[int | None] = mapped_column(
        ForeignKey("production_engineers.id", ondelete="SET NULL"),
        nullable=True,
    )
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
    production_engineer: Mapped[ProductionEngineer | None] = relationship(
        back_populates="entries",
    )
    machine_breakdowns: Mapped[list[MachineBreakdown]] = relationship(
        back_populates="entry",
    )


class AmountControlShift(Base):
    __tablename__ = "amount_control_shifts"
    __table_args__ = (
        CheckConstraint(
            "trim(record_date) <> ''",
            name="ck_amount_control_shifts_record_date",
        ),
        CheckConstraint(
            "trim(job_order) <> ''",
            name="ck_amount_control_shifts_job_order",
        ),
        CheckConstraint(
            "shift IN ('24.00-08.00', '08.00-16.00', '16.00-24.00')",
            name="ck_amount_control_shifts_shift",
        ),
        CheckConstraint(
            "trim(worker_names) <> ''",
            name="ck_amount_control_shifts_worker_names",
        ),
        CheckConstraint(
            "produced_quantity >= 0",
            name="ck_amount_control_shifts_produced_quantity",
        ),
        Index("ix_amount_control_shifts_record_date", "record_date"),
        Index("ix_amount_control_shifts_machine_id", "machine_id"),
        Index("ix_amount_control_shifts_created_at", "created_at"),
        Index(
            "ux_amount_control_shifts_client_request_id",
            "client_request_id",
            unique=True,
        ),
        Index(
            "ux_amount_control_shifts_business_key",
            "record_date",
            "machine_id",
            "job_order",
            "shift",
            unique=True,
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    client_recorded_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )
    record_date: Mapped[str] = mapped_column(String(10), nullable=False)
    machine_id: Mapped[int] = mapped_column(
        ForeignKey("machines.id", ondelete="RESTRICT"),
        nullable=False,
    )
    job_order: Mapped[str] = mapped_column(Text, nullable=False)
    shift: Mapped[str] = mapped_column(String(16), nullable=False)
    worker_names: Mapped[str] = mapped_column(Text, nullable=False)
    produced_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
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

    machine: Mapped[Machine] = relationship(back_populates="amount_control_shifts")
    machine_breakdowns: Mapped[list[MachineBreakdown]] = relationship(
        back_populates="amount_control_shift",
    )


class MachineBreakdown(Base):
    __tablename__ = "machine_breakdowns"
    __table_args__ = (
        CheckConstraint(
            "trim(produced_product) <> ''",
            name="ck_machine_breakdowns_produced_product",
        ),
        CheckConstraint(
            "trim(stop_reason) <> ''",
            name="ck_machine_breakdowns_stop_reason",
        ),
        CheckConstraint(
            "duration_minutes > 0",
            name="ck_machine_breakdowns_duration_minutes",
        ),
        CheckConstraint(
            "stopped_at IS NULL OR resumed_at IS NULL OR resumed_at >= stopped_at",
            name="ck_machine_breakdowns_stop_time_order",
        ),
        Index("ix_machine_breakdowns_machine_id", "machine_id"),
        Index("ix_machine_breakdowns_entry_id", "entry_id"),
        Index(
            "ix_machine_breakdowns_amount_control_shift_id",
            "amount_control_shift_id",
        ),
        Index("ix_machine_breakdowns_stopped_at", "stopped_at"),
        Index("ix_machine_breakdowns_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    machine_id: Mapped[int] = mapped_column(
        ForeignKey("machines.id", ondelete="RESTRICT"),
        nullable=False,
    )
    entry_id: Mapped[int | None] = mapped_column(
        ForeignKey("entries.id", ondelete="SET NULL"),
        nullable=True,
    )
    amount_control_shift_id: Mapped[int | None] = mapped_column(
        ForeignKey("amount_control_shifts.id", ondelete="SET NULL"),
        nullable=True,
    )
    produced_product: Mapped[str] = mapped_column(Text, nullable=False)
    stop_reason: Mapped[str] = mapped_column(Text, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resumed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
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

    machine: Mapped[Machine] = relationship(back_populates="breakdowns")
    entry: Mapped[Entry | None] = relationship(back_populates="machine_breakdowns")
    amount_control_shift: Mapped[AmountControlShift | None] = relationship(
        back_populates="machine_breakdowns",
    )


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
