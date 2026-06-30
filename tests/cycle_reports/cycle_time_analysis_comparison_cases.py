from decimal import Decimal

from app.features.cycle_reports.service import CycleTableEntry, normalize_machine_group
from cycle_time_analysis_work.analyze_cycle_times import (
    compare_with_db_optimum,
    resolve_exact_optimum,
)


def _summary(machine_code="175", agiz=28, gramaj=35, recommendation=15):
    return {
        "machine_code": machine_code,
        "ağız": agiz,
        "gramaj": gramaj,
        "recommended_cycle_sec": recommendation,
    }


def _exact_entry(machine_no, group, neck, gram, cycle, source_row=1):
    return {
        "source_row_number": source_row,
        "machine_no": str(machine_no),
        "machine_group": normalize_machine_group(group),
        "neck": Decimal(str(neck)),
        "gram": Decimal(str(gram)),
        "cycle": Decimal(str(cycle)),
    }


def _lookup_entry(machine_no, group, neck, gram, cycle):
    return CycleTableEntry(
        machine_no=str(machine_no),
        machine_group_key=normalize_machine_group(group),
        neck_diameter=Decimal(str(neck)),
        gram=Decimal(str(gram)),
        estimated_cycle_time=Decimal(str(cycle)),
    )


def _context(*, machine_groups=None, exact_entries=None, lookup_entries=None):
    return {
        "machine_groups": machine_groups or {"175": normalize_machine_group("70DPH")},
        "exact_entries": exact_entries or {},
        "lookup_entries": lookup_entries or {},
        "cycle_table_row_count": 0,
    }


def test_compare_with_db_optimum_matches_exact_machine_group_agiz_and_gramaj():
    key = (normalize_machine_group("70DPH"), Decimal("28"), Decimal("35"))
    result = compare_with_db_optimum(
        _summary(recommendation=15),
        _context(
            exact_entries={
                key: [_exact_entry(175, "DPH70", 28, 35, 14, source_row=96)]
            }
        ),
    )

    assert result["machine_group"] == "DPH70"
    assert result["db_optimum_match_status"] == "exact_match"
    assert result["db_optimum_cycle_sec"] == 14.0
    assert result["db_optimum_delta_sec"] == 1.0


def test_resolve_exact_optimum_uses_machine_when_group_key_has_conflicting_cycles():
    optimum, status, _ = resolve_exact_optimum(
        [
            _exact_entry(161, "PF6/2", 28, 45, 24, source_row=15),
            _exact_entry(162, "PF6/2", 28, 45, 21, source_row=16),
        ],
        "162",
    )

    assert optimum == Decimal("21")
    assert status == "exact_machine_resolved"


def test_compare_with_db_optimum_reports_ambiguity_when_machine_cannot_resolve():
    key = (normalize_machine_group("PF6/2"), Decimal("28"), Decimal("45"))
    result = compare_with_db_optimum(
        _summary(machine_code="163", agiz=28, gramaj=45),
        _context(
            machine_groups={"163": normalize_machine_group("PF6/2")},
            exact_entries={
                key: [
                    _exact_entry(161, "PF6/2", 28, 45, 24, source_row=15),
                    _exact_entry(162, "PF6/2", 28, 45, 21, source_row=16),
                ]
            },
        ),
    )

    assert result["db_optimum_match_status"] == "exact_ambiguous"
    assert result["db_optimum_cycle_sec"] is None


def test_compare_with_db_optimum_keeps_nearest_lookup_diagnostic_only():
    lookup_key = (normalize_machine_group("70DPH"), Decimal("28"), Decimal("35"))
    result = compare_with_db_optimum(
        _summary(agiz=30, gramaj=35, recommendation=16),
        _context(
            lookup_entries={
                lookup_key: [_lookup_entry(175, "DPH70", 28, 35, 14)]
            }
        ),
    )

    assert result["db_optimum_match_status"] == "no_exact_match"
    assert result["db_optimum_cycle_sec"] is None
    assert result["diagnostic_optimum_cycle_sec"] == 14.0
    assert result["diagnostic_match_status"] == "app_lookup_match"


def test_compare_with_db_optimum_reports_missing_machine_group():
    result = compare_with_db_optimum(
        _summary(machine_code="999"),
        _context(machine_groups={}),
    )

    assert result["db_optimum_match_status"] == "machine_group_missing"
    assert result["db_optimum_cycle_sec"] is None
