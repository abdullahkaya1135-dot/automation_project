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

from .core.database import Base

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


class MachineCycleTableRow(Base):
    __tablename__ = "machine_cycle_table_rows"
    __table_args__ = (
        CheckConstraint(
            "source_row_number > 1",
            name="ck_machine_cycle_table_rows_source_row_number",
        ),
        Index(
            "ux_machine_cycle_table_rows_source_row_number",
            "source_row_number",
            unique=True,
        ),
        Index("ix_machine_cycle_table_rows_lookup", "col_b", "col_c", "col_d"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    col_a: Mapped[str | None] = mapped_column(Text, nullable=True)
    col_b: Mapped[str | None] = mapped_column(Text, nullable=True)
    col_c: Mapped[str | None] = mapped_column(Text, nullable=True)
    col_d: Mapped[str | None] = mapped_column(Text, nullable=True)
    col_e: Mapped[str | None] = mapped_column(Text, nullable=True)
    col_g: Mapped[str | None] = mapped_column(Text, nullable=True)
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


class ProductionLossReport(Base):
    __tablename__ = "production_loss_reports"
    __table_args__ = (
        CheckConstraint(
            "date_from <= date_to",
            name="ck_production_loss_reports_date_range",
        ),
        CheckConstraint("row_count >= 0", name="ck_production_loss_reports_row_count"),
        CheckConstraint(
            "warning_count >= 0",
            name="ck_production_loss_reports_warning_count",
        ),
        Index(
            "ix_production_loss_reports_date_range",
            "date_from",
            "date_to",
        ),
        Index("ix_production_loss_reports_generated_at", "generated_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date_from: Mapped[str] = mapped_column(String(10), nullable=False)
    date_to: Mapped[str] = mapped_column(String(10), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now,
        nullable=False,
    )
    output_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    row_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    warning_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    source_summary_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
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

    rows: Mapped[list[ProductionLossReportRow]] = relationship(
        back_populates="report",
        cascade="all, delete-orphan",
    )


class ProductionLossReportRow(Base):
    __tablename__ = "production_loss_report_rows"
    __table_args__ = (
        CheckConstraint(
            "shift_2400_0800_quantity >= 0",
            name="ck_production_loss_rows_shift_2400",
        ),
        CheckConstraint(
            "shift_0800_1600_quantity >= 0",
            name="ck_production_loss_rows_shift_0800",
        ),
        CheckConstraint(
            "shift_1600_2400_quantity >= 0",
            name="ck_production_loss_rows_shift_1600",
        ),
        CheckConstraint(
            "shift_2400_0800_actual_quantity >= 0",
            name="ck_production_loss_rows_shift_2400_actual",
        ),
        CheckConstraint(
            "shift_0800_1600_actual_quantity >= 0",
            name="ck_production_loss_rows_shift_0800_actual",
        ),
        CheckConstraint(
            "shift_1600_2400_actual_quantity >= 0",
            name="ck_production_loss_rows_shift_1600_actual",
        ),
        CheckConstraint(
            "daily_total_quantity >= 0",
            name="ck_production_loss_rows_daily_total",
        ),
        CheckConstraint(
            "local_breakdown_minutes >= 0",
            name="ck_production_loss_rows_breakdown_minutes",
        ),
        Index("ix_production_loss_rows_report_id", "report_id"),
        Index(
            "ix_production_loss_rows_lookup",
            "record_date",
            "machine_code",
            "job_order",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_id: Mapped[int] = mapped_column(
        ForeignKey("production_loss_reports.id", ondelete="CASCADE"),
        nullable=False,
    )
    record_date: Mapped[str] = mapped_column(String(10), nullable=False)
    machine_id: Mapped[int | None] = mapped_column(
        ForeignKey("machines.id", ondelete="SET NULL"),
        nullable=True,
    )
    machine_code: Mapped[str] = mapped_column(String(16), nullable=False)
    machine_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    job_order: Mapped[str] = mapped_column(Text, nullable=False)
    lot_batch_no: Mapped[str | None] = mapped_column(Text, nullable=True)
    product_no: Mapped[str | None] = mapped_column(Text, nullable=True)
    product_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    gram: Mapped[str | None] = mapped_column(Text, nullable=True)
    active_cavities: Mapped[str | None] = mapped_column(Text, nullable=True)
    cycle_time_seconds: Mapped[str | None] = mapped_column(Text, nullable=True)
    shift_2400_0800_quantity: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    shift_0800_1600_quantity: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    shift_1600_2400_quantity: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    daily_total_quantity: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    shift_2400_0800_actual_quantity: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        nullable=False,
    )
    shift_2400_0800_machine_minutes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    shift_2400_0800_optimum_quantity: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    shift_2400_0800_loss_quantity: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    shift_0800_1600_actual_quantity: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        nullable=False,
    )
    shift_0800_1600_machine_minutes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    shift_0800_1600_optimum_quantity: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    shift_0800_1600_loss_quantity: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    shift_1600_2400_actual_quantity: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        nullable=False,
    )
    shift_1600_2400_machine_minutes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    shift_1600_2400_optimum_quantity: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    shift_1600_2400_loss_quantity: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    net_machine_minutes: Mapped[str | None] = mapped_column(Text, nullable=True)
    gross_elapsed_minutes: Mapped[str | None] = mapped_column(Text, nullable=True)
    gross_start_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    gross_finish_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    optimum_net_quantity: Mapped[str | None] = mapped_column(Text, nullable=True)
    production_loss_net: Mapped[str | None] = mapped_column(Text, nullable=True)
    optimum_gross_quantity: Mapped[str | None] = mapped_column(Text, nullable=True)
    production_loss_gross: Mapped[str | None] = mapped_column(Text, nullable=True)
    break_loss_quantity: Mapped[str | None] = mapped_column(Text, nullable=True)
    local_breakdown_minutes: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    warnings: Mapped[str | None] = mapped_column(Text, nullable=True)
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

    report: Mapped[ProductionLossReport] = relationship(back_populates="rows")
    machine: Mapped[Machine | None] = relationship()


class ProductionLossIfsActual(Base):
    __tablename__ = "production_loss_ifs_actuals"
    __table_args__ = (
        CheckConstraint(
            "trim(job_order) <> ''",
            name="ck_production_loss_ifs_actuals_job_order",
        ),
        CheckConstraint(
            "machine_code IS NULL OR trim(machine_code) <> ''",
            name="ck_production_loss_ifs_actuals_machine_code",
        ),
        Index(
            "ux_production_loss_ifs_actuals_order_machine",
            "job_order",
            "machine_code",
            unique=True,
        ),
        Index(
            "ix_production_loss_ifs_actuals_updated",
            "source_updated_at",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_order: Mapped[str] = mapped_column(Text, nullable=False)
    machine_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    release_no: Mapped[str | None] = mapped_column(Text, nullable=True)
    sequence_no: Mapped[str | None] = mapped_column(Text, nullable=True)
    operation_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    work_center_no: Mapped[str | None] = mapped_column(Text, nullable=True)
    part_no: Mapped[str | None] = mapped_column(Text, nullable=True)
    part_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    actual_start_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    actual_finish_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    net_machine_minutes: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_quantity: Mapped[str | None] = mapped_column(Text, nullable=True)
    scrap_quantity: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(64), default="ifs", nullable=False)
    raw_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now,
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


class ProductionLossLabelEvent(Base):
    __tablename__ = "production_loss_label_events"
    __table_args__ = (
        CheckConstraint(
            "trim(result_key) <> ''",
            name="ck_production_loss_label_events_result_key",
        ),
        CheckConstraint(
            "trim(record_date) <> ''",
            name="ck_production_loss_label_events_record_date",
        ),
        CheckConstraint(
            "shift IN ('24.00-08.00', '08.00-16.00', '16.00-24.00')",
            name="ck_production_loss_label_events_shift",
        ),
        CheckConstraint(
            "trim(machine_code) <> ''",
            name="ck_production_loss_label_events_machine_code",
        ),
        CheckConstraint(
            "trim(job_order) <> ''",
            name="ck_production_loss_label_events_job_order",
        ),
        CheckConstraint(
            "quantity >= 0",
            name="ck_production_loss_label_events_quantity",
        ),
        Index(
            "ux_production_loss_label_events_result_key",
            "result_key",
            unique=True,
        ),
        Index(
            "ix_production_loss_label_events_lookup",
            "record_date",
            "machine_code",
            "job_order",
            "shift",
        ),
        Index(
            "ix_production_loss_label_events_archive_time",
            "archive_exec_time",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    result_key: Mapped[str] = mapped_column(Text, nullable=False)
    report_id: Mapped[str] = mapped_column(Text, nullable=False)
    print_job_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    archive_exec_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    label_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    record_date: Mapped[str] = mapped_column(String(10), nullable=False)
    shift: Mapped[str] = mapped_column(String(16), nullable=False)
    machine_code: Mapped[str] = mapped_column(String(16), nullable=False)
    job_order: Mapped[str] = mapped_column(Text, nullable=False)
    part_no: Mapped[str | None] = mapped_column(Text, nullable=True)
    product_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    quantity: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        nullable=False,
    )
    package_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    lot_batch_no: Mapped[str | None] = mapped_column(Text, nullable=True)
    pallet_no: Mapped[str | None] = mapped_column(Text, nullable=True)
    sequence_no: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_xml: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now,
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


class ShiftManagerNotification(Base):
    __tablename__ = "shift_manager_notifications"
    __table_args__ = (
        Index(
            "ux_shift_manager_notifications_order_pair",
            "machine_code",
            "current_order_no",
            "next_order_no",
            unique=True,
        ),
        Index("ix_shift_manager_notifications_machine_code", "machine_code"),
        Index("ix_shift_manager_notifications_updated_at", "updated_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    machine_code: Mapped[str] = mapped_column(String(16), nullable=False)
    current_order_no: Mapped[str] = mapped_column(Text, nullable=False)
    next_order_no: Mapped[str] = mapped_column(Text, nullable=False)
    informed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="0",
        nullable=False,
    )
    informed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
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


class MachineBreakdown(Base):
    __tablename__ = "machine_breakdowns"
    __table_args__ = (
        CheckConstraint(
            "client_request_id IS NULL OR trim(client_request_id) <> ''",
            name="ck_machine_breakdowns_client_request_id",
        ),
        CheckConstraint(
            "record_date IS NULL OR trim(record_date) <> ''",
            name="ck_machine_breakdowns_record_date",
        ),
        CheckConstraint(
            "shift IS NULL OR shift IN ('24.00-08.00', '08.00-16.00', '16.00-24.00')",
            name="ck_machine_breakdowns_shift",
        ),
        CheckConstraint(
            "job_order IS NULL OR trim(job_order) <> ''",
            name="ck_machine_breakdowns_job_order",
        ),
        CheckConstraint(
            "produced_product IS NULL OR trim(produced_product) <> ''",
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
        Index(
            "ix_machine_breakdowns_record_lookup",
            "record_date",
            "machine_id",
            "shift",
        ),
        Index("ix_machine_breakdowns_stopped_at", "stopped_at"),
        Index("ix_machine_breakdowns_created_at", "created_at"),
        Index(
            "ux_machine_breakdowns_client_request_id",
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
    record_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    shift: Mapped[str | None] = mapped_column(String(16), nullable=True)
    job_order: Mapped[str | None] = mapped_column(Text, nullable=True)
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
    produced_product: Mapped[str | None] = mapped_column(Text, nullable=True)
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
