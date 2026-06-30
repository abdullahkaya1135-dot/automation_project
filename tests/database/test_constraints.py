import pytest

from app.core.database import (
    DatabaseCommitError,
    create_session,
    init_db,
    session_scope,
)
from app.models import (
    SYNC_STATUS_PENDING_EXCEL,
    AmountControlShift,
    Entry,
    Machine,
    MachineBreakdown,
    ProductionLossLabelEvent,
    TourContext,
)

from .helpers import sqlite_settings


def test_production_loss_label_event_persists(tmp_path):
    settings = sqlite_settings(tmp_path)
    init_db(settings)

    with session_scope(settings) as session:
        machine = session.query(Machine).filter_by(machine_code="101").one()
        session.add(
            ProductionLossLabelEvent(
                result_key="label-row-1",
                report_id="REPORT-1",
                print_job_id="PRINT-1",
                record_date="2026-06-17",
                shift="08.00-16.00",
                machine_code=machine.machine_code,
                job_order="WO-1",
                part_no="PET-35",
                product_description="PET 28MM 35GR",
                quantity=120,
                package_id="PKG-1",
                lot_batch_no="LOT-1",
                raw_xml="<LabelId>label-row-1</LabelId>",
            )
        )

    with create_session(settings) as session:
        label_event = session.query(ProductionLossLabelEvent).one()
        assert label_event.result_key == "label-row-1"
        assert label_event.report_id == "REPORT-1"
        assert label_event.machine_code == "101"
        assert label_event.job_order == "WO-1"
        assert label_event.shift == "08.00-16.00"
        assert label_event.part_no == "PET-35"
        assert label_event.quantity == 120
        assert label_event.lot_batch_no == "LOT-1"


def test_machine_breakdown_persists_with_machine_and_entry_links(tmp_path):
    settings = sqlite_settings(tmp_path)
    init_db(settings)

    with session_scope(settings) as session:
        machine = session.query(Machine).filter_by(machine_code="101").one()
        context = TourContext(
            date="2026-06-17",
            ambient_temp="24",
            production_engineer="Barış Çetik",
            shift_chief="Selman",
            shift="08.00-16.00",
        )
        entry = Entry(
            tour_context=context,
            col_a="17.06.2026",
            col_f="101",
            col_g="Product 101",
            sync_status=SYNC_STATUS_PENDING_EXCEL,
        )
        session.add(
            MachineBreakdown(
                machine=machine,
                entry=entry,
                produced_product="Product 101",
                stop_reason="Hydraulic pressure fault",
                duration_minutes=45,
            )
        )

    with create_session(settings) as session:
        breakdown = session.query(MachineBreakdown).one()
        assert breakdown.machine.machine_code == "101"
        assert breakdown.entry is not None
        assert breakdown.produced_product == "Product 101"
        assert breakdown.stop_reason == "Hydraulic pressure fault"
        assert breakdown.duration_minutes == 45


def test_machine_breakdown_rejects_invalid_machine_and_duration(tmp_path):
    settings = sqlite_settings(tmp_path)
    init_db(settings)

    with create_session(settings) as session:
        machine_id = session.query(Machine.id).filter_by(machine_code="101").scalar()

    with pytest.raises(DatabaseCommitError), session_scope(settings) as session:
        session.add(
            MachineBreakdown(
                machine_id=machine_id,
                produced_product="Product 101",
                stop_reason="",
                duration_minutes=15,
            )
        )

    with pytest.raises(DatabaseCommitError), session_scope(settings) as session:
        session.add(
            MachineBreakdown(
                machine_id=machine_id,
                produced_product="",
                stop_reason="Hydraulic pressure fault",
                duration_minutes=15,
            )
        )

    with pytest.raises(DatabaseCommitError), session_scope(settings) as session:
        session.add(
            MachineBreakdown(
                machine_id=machine_id,
                produced_product="Product 101",
                stop_reason="Hydraulic pressure fault",
                duration_minutes=0,
            )
        )

    with pytest.raises(DatabaseCommitError), session_scope(settings) as session:
        session.add(
            MachineBreakdown(
                machine_id=999_999,
                produced_product="Product 101",
                stop_reason="Hydraulic pressure fault",
                duration_minutes=15,
            )
        )


def test_machine_breakdown_allows_paper_minimum_standalone_record(tmp_path):
    settings = sqlite_settings(tmp_path)
    init_db(settings)

    with session_scope(settings) as session:
        machine = session.query(Machine).filter_by(machine_code="101").one()
        session.add(
            MachineBreakdown(
                machine=machine,
                record_date="2026-06-17",
                shift="24.00-08.00",
                stop_reason="Hydraulic pressure fault",
                duration_minutes=45,
            )
        )

    with create_session(settings) as session:
        breakdown = session.query(MachineBreakdown).one()
        assert breakdown.machine.machine_code == "101"
        assert breakdown.record_date == "2026-06-17"
        assert breakdown.shift == "24.00-08.00"
        assert breakdown.job_order is None
        assert breakdown.produced_product is None
        assert breakdown.stop_reason == "Hydraulic pressure fault"


def test_amount_control_shift_enforces_business_rules(tmp_path):
    settings = sqlite_settings(tmp_path)
    init_db(settings)

    with create_session(settings) as session:
        machine_id = session.query(Machine.id).filter_by(machine_code="101").scalar()

    with session_scope(settings) as session:
        session.add(
            AmountControlShift(
                record_date="2026-06-17",
                machine_id=machine_id,
                job_order="WO-1",
                shift="08.00-16.00",
                worker_names="Operator One",
                produced_quantity=1200,
            )
        )

    invalid_rows = [
        {
            "job_order": "",
            "shift": "08.00-16.00",
            "worker_names": "Operator One",
            "produced_quantity": 1,
        },
        {
            "job_order": "WO-2",
            "shift": "00.00-08.00",
            "worker_names": "Operator One",
            "produced_quantity": 1,
        },
        {
            "job_order": "WO-2",
            "shift": "08.00-16.00",
            "worker_names": " ",
            "produced_quantity": 1,
        },
        {
            "job_order": "WO-2",
            "shift": "08.00-16.00",
            "worker_names": "Operator One",
            "produced_quantity": -1,
        },
    ]
    for row in invalid_rows:
        with pytest.raises(DatabaseCommitError), session_scope(settings) as session:
            session.add(
                AmountControlShift(
                    record_date="2026-06-17",
                    machine_id=machine_id,
                    **row,
                )
            )

    with pytest.raises(DatabaseCommitError), session_scope(settings) as session:
        session.add(
            AmountControlShift(
                record_date="2026-06-17",
                machine_id=999_999,
                job_order="WO-2",
                shift="08.00-16.00",
                worker_names="Operator One",
                produced_quantity=1,
            )
        )

    with pytest.raises(DatabaseCommitError), session_scope(settings) as session:
        session.add(
            AmountControlShift(
                record_date="2026-06-17",
                machine_id=machine_id,
                job_order="WO-1",
                shift="08.00-16.00",
                worker_names="Operator Two",
                produced_quantity=900,
            )
        )


def test_machine_breakdowns_link_to_amount_control_shift(tmp_path):
    settings = sqlite_settings(tmp_path)
    init_db(settings)

    with session_scope(settings) as session:
        machine = session.query(Machine).filter_by(machine_code="101").one()
        amount_shift = AmountControlShift(
            record_date="2026-06-17",
            machine=machine,
            job_order="WO-1",
            shift="08.00-16.00",
            worker_names="Operator One, Operator Two",
            produced_quantity=1200,
        )
        session.add_all(
            [
                amount_shift,
                MachineBreakdown(
                    machine=machine,
                    amount_control_shift=amount_shift,
                    produced_product="Product 101",
                    stop_reason="Hydraulic pressure fault",
                    duration_minutes=45,
                ),
                MachineBreakdown(
                    machine=machine,
                    amount_control_shift=amount_shift,
                    produced_product="Product 101",
                    stop_reason="Mold change",
                    duration_minutes=30,
                ),
            ]
        )

    with create_session(settings) as session:
        amount_shift = session.query(AmountControlShift).one()
        assert amount_shift.machine.machine_code == "101"
        assert len(amount_shift.machine_breakdowns) == 2
        assert {
            breakdown.stop_reason for breakdown in amount_shift.machine_breakdowns
        } == {"Hydraulic pressure fault", "Mold change"}


def test_deleting_amount_control_shift_nulls_breakdown_link(tmp_path):
    settings = sqlite_settings(tmp_path)
    init_db(settings)

    with session_scope(settings) as session:
        machine = session.query(Machine).filter_by(machine_code="101").one()
        amount_shift = AmountControlShift(
            record_date="2026-06-17",
            machine=machine,
            job_order="WO-1",
            shift="08.00-16.00",
            worker_names="Operator One",
            produced_quantity=1200,
        )
        session.add(amount_shift)
        session.flush()
        session.add(
            MachineBreakdown(
                machine=machine,
                amount_control_shift_id=amount_shift.id,
                produced_product="Product 101",
                stop_reason="Hydraulic pressure fault",
                duration_minutes=45,
            )
        )

    with session_scope(settings) as session:
        amount_shift = session.query(AmountControlShift).one()
        session.delete(amount_shift)

    with create_session(settings) as session:
        breakdown = session.query(MachineBreakdown).one()
        assert breakdown.amount_control_shift_id is None
