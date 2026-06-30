from sqlalchemy import text

from app.core.database import create_session, init_db
from app.models import (
    Machine,
    MachineCycleTableRow,
    MachineGroup,
    MachineGroupMachine,
    ProductionEngineer,
)

from .helpers import create_cycle_seed_workbook, sqlite_settings


def test_init_db_seeds_production_engineers(tmp_path):
    settings = sqlite_settings(tmp_path)

    init_db(settings)
    init_db(settings)

    with create_session(settings) as session:
        engineers = (
            session.query(ProductionEngineer)
            .order_by(ProductionEngineer.display_order)
            .all()
        )

    assert [engineer.full_name for engineer in engineers] == [
        "Barış Çetik",
        "Abdullah Kaya",
        "Fevzi Kılınç",
    ]
    assert [engineer.active for engineer in engineers] == [True, True, True]


def test_init_db_seeds_factory_machines_by_hall(tmp_path):
    settings = sqlite_settings(tmp_path)

    init_db(settings)
    init_db(settings)

    with create_session(settings) as session:
        machines = (
            session.query(Machine)
            .order_by(Machine.hall_number, Machine.display_order)
            .all()
        )

    assert len(machines) == 47
    assert {
        hall_number: sum(
            1 for machine in machines if machine.hall_number == hall_number
        )
        for hall_number in range(1, 5)
    } == {1: 15, 2: 12, 3: 11, 4: 9}
    assert [
        machine.machine_code for machine in machines if machine.hall_number == 1
    ] == [
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
    ]
    assert [
        machine.machine_code for machine in machines if machine.hall_number == 2
    ] == [
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
    ]
    assert [
        machine.machine_code for machine in machines if machine.hall_number == 3
    ] == [
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
    ]
    assert [
        machine.machine_code for machine in machines if machine.hall_number == 4
    ] == [
        "202",
        "205",
        "206",
        "207",
        "209",
        "210",
        "212",
        "213",
        "301",
    ]


def test_init_db_seeds_machine_groups_from_joined_machines(tmp_path):
    settings = sqlite_settings(tmp_path)

    init_db(settings)
    init_db(settings)

    with create_session(settings) as session:
        group_names = [
            name
            for (name,) in session.query(MachineGroup.group_name)
            .order_by(MachineGroup.display_order)
            .all()
        ]
        link_count = session.query(MachineGroupMachine).count()

    assert group_names == [
        "SP25",
        "SP80",
        "PF6/2",
        "PF8/4",
        "50MB",
        "12M",
        "DPH70",
        "ENJK.",
        "PREFORM",
        "PET \u015e\u0130\u015e.",
        "UNILOY",
        "5L\u0130K",
        "\u0130LA\u00c7",
    ]
    assert link_count == 47

    with create_session(settings) as session:
        session.add(
            Machine(
                machine_code="141",
                hall_number=2,
                hall_name="Hole 2",
                display_order=13,
            )
        )
        session.commit()

    init_db(settings)

    with create_session(settings) as session:
        group_names = [
            name
            for (name,) in session.query(MachineGroup.group_name)
            .order_by(MachineGroup.display_order)
            .all()
        ]
        group_links = session.execute(
            text(
                "SELECT mg.group_name, m.machine_code "
                "FROM machine_groups mg "
                "INNER JOIN machine_group_machines mgm "
                "ON mgm.machine_group_id = mg.id "
                "INNER JOIN machines m ON m.id = mgm.machine_id "
                "ORDER BY mg.display_order, m.machine_code"
            )
        ).all()

    assert group_names == [
        "SP25",
        "SP80",
        "PF4/1",
        "PF6/2",
        "PF8/4",
        "50MB",
        "12M",
        "DPH70",
        "ENJK.",
        "PREFORM",
        "PET \u015e\u0130\u015e.",
        "UNILOY",
        "5L\u0130K",
        "\u0130LA\u00c7",
    ]
    assert len(group_links) == 48
    assert ("PF4/1", "141") in group_links


def test_init_db_seeds_machine_cycle_table_rows_from_workbook(tmp_path):
    cycle_table_path = tmp_path / "cycle.xlsx"
    create_cycle_seed_workbook(cycle_table_path)
    settings = sqlite_settings(
        tmp_path,
        cycle_table_path=str(cycle_table_path),
    )

    init_db(settings)
    init_db(settings)

    with create_session(settings) as session:
        rows = (
            session.query(MachineCycleTableRow)
            .order_by(MachineCycleTableRow.source_row_number)
            .all()
        )

    assert len(rows) == 2
    assert [
        (
            row.source_row_number,
            row.col_a,
            row.col_b,
            row.col_c,
            row.col_d,
            row.col_e,
            row.col_g,
        )
        for row in rows
    ] == [
        (2, "174", "DPH70", "28", "35", "MOLD-A", "14"),
        (3, "174", "DPH70", "28", "40", "MOLD-B", "16"),
    ]
