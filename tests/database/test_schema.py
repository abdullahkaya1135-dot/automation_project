from sqlalchemy import inspect

from app.core.database import create_session, init_db

from .helpers import sqlite_settings


def test_sqlite_model_creates_required_tables_and_columns(tmp_path):
    settings = sqlite_settings(tmp_path)

    init_db(settings)

    with create_session(settings) as session:
        inspector = inspect(session.get_bind())
        table_names = set(inspector.get_table_names())
        entry_columns = {column["name"] for column in inspector.get_columns("entries")}
        machine_columns = {
            column["name"] for column in inspector.get_columns("machines")
        }
        machine_group_columns = {
            column["name"] for column in inspector.get_columns("machine_groups")
        }
        machine_group_machine_columns = {
            column["name"] for column in inspector.get_columns("machine_group_machines")
        }
        production_engineer_columns = {
            column["name"] for column in inspector.get_columns("production_engineers")
        }
        cycle_table_columns = {
            column["name"]
            for column in inspector.get_columns("machine_cycle_table_rows")
        }
        breakdown_columns = {
            column["name"] for column in inspector.get_columns("machine_breakdowns")
        }
        amount_control_columns = {
            column["name"] for column in inspector.get_columns("amount_control_shifts")
        }
        production_loss_report_columns = {
            column["name"]
            for column in inspector.get_columns("production_loss_reports")
        }
        production_loss_row_columns = {
            column["name"]
            for column in inspector.get_columns("production_loss_report_rows")
        }
        production_loss_ifs_columns = {
            column["name"]
            for column in inspector.get_columns("production_loss_ifs_actuals")
        }
        production_loss_label_event_columns = {
            column["name"]
            for column in inspector.get_columns("production_loss_label_events")
        }
        amount_control_foreign_keys = inspector.get_foreign_keys(
            "amount_control_shifts"
        )
        amount_control_check_constraints = {
            constraint["name"]
            for constraint in inspector.get_check_constraints("amount_control_shifts")
        }
        amount_control_indexes = {
            index["name"] for index in inspector.get_indexes("amount_control_shifts")
        }
        breakdown_foreign_keys = inspector.get_foreign_keys("machine_breakdowns")
        breakdown_indexes = {
            index["name"] for index in inspector.get_indexes("machine_breakdowns")
        }
        production_loss_row_foreign_keys = inspector.get_foreign_keys(
            "production_loss_report_rows"
        )
        production_loss_label_event_check_constraints = {
            constraint["name"]
            for constraint in inspector.get_check_constraints(
                "production_loss_label_events"
            )
        }
        production_loss_label_event_indexes = {
            index["name"]
            for index in inspector.get_indexes("production_loss_label_events")
        }
        breakdown_check_constraints = {
            constraint["name"]
            for constraint in inspector.get_check_constraints("machine_breakdowns")
        }

    assert table_names >= {
        "tour_contexts",
        "entries",
        "machines",
        "machine_groups",
        "machine_group_machines",
        "machine_cycle_table_rows",
        "production_engineers",
        "machine_breakdowns",
        "amount_control_shifts",
        "production_loss_reports",
        "production_loss_report_rows",
        "production_loss_ifs_actuals",
        "production_loss_label_events",
    }
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
    assert {
        "id",
        "machine_code",
        "hall_number",
        "hall_name",
        "display_order",
        "created_at",
        "updated_at",
    } <= machine_columns
    assert {
        "id",
        "group_name",
        "display_order",
        "created_at",
        "updated_at",
    } <= machine_group_columns
    assert {
        "machine_group_id",
        "machine_id",
        "created_at",
        "updated_at",
    } <= machine_group_machine_columns
    assert {
        "id",
        "full_name",
        "display_order",
        "active",
        "created_at",
        "updated_at",
    } <= production_engineer_columns
    assert {
        "id",
        "source_row_number",
        "col_a",
        "col_b",
        "col_c",
        "col_d",
        "col_e",
        "col_g",
        "created_at",
        "updated_at",
    } <= cycle_table_columns
    assert {
        "process_date",
        "machine_code",
        "production_engineer_id",
    } <= entry_columns
    assert {
        "id",
        "client_request_id",
        "client_recorded_at",
        "record_date",
        "shift",
        "job_order",
        "machine_id",
        "entry_id",
        "amount_control_shift_id",
        "produced_product",
        "stop_reason",
        "duration_minutes",
        "stopped_at",
        "resumed_at",
        "created_at",
        "updated_at",
    } <= breakdown_columns
    assert {
        "id",
        "client_request_id",
        "client_recorded_at",
        "record_date",
        "machine_id",
        "job_order",
        "shift",
        "worker_names",
        "produced_quantity",
        "created_at",
        "updated_at",
    } <= amount_control_columns
    assert {
        "id",
        "date_from",
        "date_to",
        "generated_at",
        "output_path",
        "row_count",
        "warning_count",
        "source_summary_json",
        "created_at",
        "updated_at",
    } <= production_loss_report_columns
    assert {
        "id",
        "report_id",
        "record_date",
        "machine_id",
        "machine_code",
        "machine_name",
        "job_order",
        "lot_batch_no",
        "product_no",
        "product_description",
        "gram",
        "active_cavities",
        "cycle_time_seconds",
        "shift_2400_0800_quantity",
        "shift_2400_0800_actual_quantity",
        "shift_2400_0800_machine_minutes",
        "shift_2400_0800_optimum_quantity",
        "shift_2400_0800_loss_quantity",
        "shift_0800_1600_quantity",
        "shift_0800_1600_actual_quantity",
        "shift_0800_1600_machine_minutes",
        "shift_0800_1600_optimum_quantity",
        "shift_0800_1600_loss_quantity",
        "shift_1600_2400_quantity",
        "shift_1600_2400_actual_quantity",
        "shift_1600_2400_machine_minutes",
        "shift_1600_2400_optimum_quantity",
        "shift_1600_2400_loss_quantity",
        "daily_total_quantity",
        "net_machine_minutes",
        "gross_elapsed_minutes",
        "gross_start_at",
        "gross_finish_at",
        "optimum_net_quantity",
        "production_loss_net",
        "optimum_gross_quantity",
        "production_loss_gross",
        "break_loss_quantity",
        "local_breakdown_minutes",
        "warnings",
    } <= production_loss_row_columns
    assert {
        "id",
        "job_order",
        "machine_code",
        "work_center_no",
        "part_no",
        "part_description",
        "actual_start_at",
        "actual_finish_at",
        "net_machine_minutes",
        "raw_json",
        "source_updated_at",
    } <= production_loss_ifs_columns
    assert {
        "id",
        "result_key",
        "report_id",
        "print_job_id",
        "archive_exec_time",
        "label_time",
        "record_date",
        "shift",
        "machine_code",
        "job_order",
        "part_no",
        "product_description",
        "quantity",
        "package_id",
        "lot_batch_no",
        "pallet_no",
        "sequence_no",
        "raw_xml",
        "source_updated_at",
        "created_at",
        "updated_at",
    } <= production_loss_label_event_columns
    assert {
        (
            tuple(foreign_key["constrained_columns"]),
            foreign_key["referred_table"],
            tuple(foreign_key["referred_columns"]),
            foreign_key["options"].get("ondelete"),
        )
        for foreign_key in amount_control_foreign_keys
    } >= {
        (("machine_id",), "machines", ("id",), "RESTRICT"),
    }
    assert {
        "ck_amount_control_shifts_record_date",
        "ck_amount_control_shifts_job_order",
        "ck_amount_control_shifts_shift",
        "ck_amount_control_shifts_worker_names",
        "ck_amount_control_shifts_produced_quantity",
    } <= amount_control_check_constraints
    assert {
        "ix_amount_control_shifts_record_date",
        "ix_amount_control_shifts_machine_id",
        "ix_amount_control_shifts_created_at",
        "ux_amount_control_shifts_client_request_id",
        "ux_amount_control_shifts_business_key",
    } <= amount_control_indexes
    assert {
        (
            tuple(foreign_key["constrained_columns"]),
            foreign_key["referred_table"],
            tuple(foreign_key["referred_columns"]),
            foreign_key["options"].get("ondelete"),
        )
        for foreign_key in breakdown_foreign_keys
    } >= {
        (("machine_id",), "machines", ("id",), "RESTRICT"),
        (("entry_id",), "entries", ("id",), "SET NULL"),
        (
            ("amount_control_shift_id",),
            "amount_control_shifts",
            ("id",),
            "SET NULL",
        ),
    }
    assert {
        (
            tuple(foreign_key["constrained_columns"]),
            foreign_key["referred_table"],
            tuple(foreign_key["referred_columns"]),
            foreign_key["options"].get("ondelete"),
        )
        for foreign_key in production_loss_row_foreign_keys
    } >= {
        (
            ("report_id",),
            "production_loss_reports",
            ("id",),
            "CASCADE",
        ),
        (("machine_id",), "machines", ("id",), "SET NULL"),
    }
    assert {
        "ck_production_loss_label_events_result_key",
        "ck_production_loss_label_events_record_date",
        "ck_production_loss_label_events_shift",
        "ck_production_loss_label_events_machine_code",
        "ck_production_loss_label_events_job_order",
        "ck_production_loss_label_events_quantity",
    } <= production_loss_label_event_check_constraints
    assert {
        "ux_production_loss_label_events_result_key",
        "ix_production_loss_label_events_lookup",
        "ix_production_loss_label_events_archive_time",
    } <= production_loss_label_event_indexes
    assert {
        "ck_machine_breakdowns_client_request_id",
        "ck_machine_breakdowns_record_date",
        "ck_machine_breakdowns_shift",
        "ck_machine_breakdowns_job_order",
        "ck_machine_breakdowns_produced_product",
        "ck_machine_breakdowns_stop_reason",
        "ck_machine_breakdowns_duration_minutes",
        "ck_machine_breakdowns_stop_time_order",
    } <= breakdown_check_constraints
    assert {
        "ux_machine_breakdowns_client_request_id",
        "ix_machine_breakdowns_record_lookup",
    } <= breakdown_indexes
