from datetime import datetime
from pathlib import Path

from app.config import Settings
from app.database import create_session, init_db
from app.features.ifs_checks.service import (
    missing_production_starts_from_operations,
    whatsapp_status_message_from_operations,
)
from app.models import Entry


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        excel_path=str(tmp_path / "process.xlsx"),
        app_pin="1234",
        sqlite_path=str(tmp_path / "process_entries.sqlite3"),
        backup_dir=str(tmp_path / "backups"),
        cycle_table_path=str(tmp_path / "missing-cycle-table.xlsx"),
    )


def _entry(
    machine_code: str,
    *,
    cycle_time: str | None,
    work_order: str = "WO",
    product: str = "Product",
    submitted_at: datetime | None = None,
) -> Entry:
    return Entry(
        col_a="08.06.2026",
        col_f=machine_code,
        col_g=product,
        col_h=work_order,
        col_l=cycle_time,
        process_date="2026-06-08",
        machine_code=machine_code,
        sync_status="synced",
        submitted_at=submitted_at,
    )


def test_missing_production_starts_lists_hall_3_4_working_machines_absent_from_ifs(
    tmp_path,
):
    settings = _settings(tmp_path)
    init_db(settings)
    with create_session(settings) as session:
        session.add_all(
            [
                _entry(
                    "302",
                    cycle_time="12,5",
                    work_order="WO-OLD",
                    product="Product Old",
                    submitted_at=datetime(2026, 6, 8, 9, 0),
                ),
                _entry(
                    "302",
                    cycle_time="13,4",
                    work_order="WO-NEW",
                    product="Product New",
                    submitted_at=datetime(2026, 6, 8, 10, 30),
                ),
                _entry("303", cycle_time="11.2", work_order="WO-303"),
                _entry("101", cycle_time="10", work_order="WO-HALL-1"),
                _entry("202", cycle_time="", work_order="WO-BLANK"),
                _entry("205", cycle_time="abc", work_order="WO-BAD"),
            ]
        )
        session.commit()

    summary = missing_production_starts_from_operations(
        settings,
        "2026-06-08",
        [{"PreferredResourceId": "M-303"}],
    )

    assert summary.working_machine_count == 2
    assert summary.active_ifs_machine_count == 1
    assert summary.missing_count == 1
    assert [row.machine_code for row in summary.machines] == ["302"]
    row = summary.machines[0]
    assert row.hall_number == 3
    assert row.latest_work_order == "WO-NEW"
    assert row.latest_product == "Product New"
    assert row.latest_cycle_time == "13,4"
    assert row.latest_submitted_at == datetime(2026, 6, 8, 10, 30)
    assert row.entry_count == 2


def test_missing_production_starts_returns_empty_when_working_machine_exists_in_ifs(
    tmp_path,
):
    settings = _settings(tmp_path)
    init_db(settings)
    with create_session(settings) as session:
        session.add(_entry("401", cycle_time="18", work_order="WO-401"))
        session.commit()

    summary = missing_production_starts_from_operations(
        settings,
        "08.06.2026",
        [{"PreferredResourceId": "401"}],
    )

    assert summary.process_date == "2026-06-08"
    assert summary.working_machine_count == 1
    assert summary.missing_count == 0
    assert summary.machines == []


def test_whatsapp_status_message_uses_hall_order_and_ifs_active_machines(tmp_path):
    settings = _settings(tmp_path)
    init_db(settings)

    summary = whatsapp_status_message_from_operations(
        settings,
        [
            {"PreferredResourceId": "302"},
            {"PreferredResourceId": "M-210"},
        ],
    )

    assert summary.hall_numbers == (3, 4)
    assert summary.active_ifs_machine_count == 2
    assert summary.machine_count == 20
    assert [hall.hall_number for hall in summary.halls] == [3, 4]
    assert [machine.machine_code for machine in summary.halls[0].machines[:3]] == [
        "302",
        "303",
        "401",
    ]
    assert summary.message == (
        "Salon 3\n"
        "302 Üretim\n"
        "303 Kapalı\n"
        "401 Kapalı\n"
        "402 Kapalı\n"
        "404 Kapalı\n"
        "405 Kapalı\n"
        "501 Kapalı\n"
        "502 Kapalı\n"
        "503 Kapalı\n"
        "505 Kapalı\n"
        "506 Kapalı\n"
        "\n"
        "IFS kontrolleri yapılmıştır.\n"
        "\n"
        "Salon 4\n"
        "202 Kapalı\n"
        "205 Kapalı\n"
        "206 Kapalı\n"
        "207 Kapalı\n"
        "209 Kapalı\n"
        "210 Üretim\n"
        "212 Kapalı\n"
        "213 Kapalı\n"
        "301 Kapalı\n"
        "\n"
        "IFS kontrolleri yapılmıştır."
    )
