from pathlib import Path

from app.features.production_planning.service import MachinePlanningRow
from app.integrations.ifs.client import IFSClientError
from tests.routes.helpers import _tour_context


def test_ifs_stock_endpoint_returns_u1_hm02_stock(client, monkeypatch):
    async def fake_fetch(_settings):
        return [
            {
                "Contract": "S01",
                "PartNo": "HM-02-A",
                "PartNoRef": {"Description": "Raw Material"},
                "LocationNo": "U1",
                "LotBatchNo": "L1",
                "AvailableQty": 12.5,
                "QtyOnhand": 15,
                "UoM": "kg",
                "ObjId": "obj-1",
            }
        ]

    monkeypatch.setattr("app.features.ifs.api.fetch_u1_hm02_stock", fake_fetch)

    response = client.get("/api/ifs/u1-hm02-stock")

    assert response.status_code == 200
    assert response.json() == {
        "stock_count": 1,
        "stock": [
            {
                "contract": "S01",
                "part_no": "HM-02-A",
                "material_name": "Raw Material",
                "location_no": "U1",
                "lot_batch_no": "L1",
                "available_qty": 12.5,
                "qty_onhand": 15,
                "uom": "kg",
                "obj_id": "obj-1",
                "configuration_id": None,
                "serial_no": None,
                "eng_chg_level": None,
                "waiv_dev_rej_no": None,
                "activity_seq": None,
                "handling_unit_id": None,
            }
        ],
    }


def test_ifs_package_label_checklist_endpoint_returns_summary_and_rows(
    client,
    monkeypatch,
):
    async def fake_fetch(_settings):
        return {
            "summary": {
                "generated_at": "2026-06-24T08:00:00+03:00",
                "stock_count": 1,
                "row_count": 1,
                "job_order_count": 1,
                "operation_count": 1,
                "matched_count": 1,
                "part_matched_count": 1,
                "job_order_matched_count": 0,
                "ambiguous_count": 0,
                "not_found_count": 0,
                "missing_job_order_count": 0,
                "match_status_counts": {"matched": 1},
            },
            "rows": [
                {
                    "contract": "S01",
                    "part_no": "MM-CAP001",
                    "part_description": "Cap 1",
                    "location_no": "U0101",
                    "qty_onhand": 10,
                    "available_qty": 8,
                    "uom": "PCS",
                    "lot_batch_no": "2579-L1",
                    "serial_no": "*",
                    "receipt_date": "2026-06-24T05:00:00Z",
                    "handling_unit_id": "HU-1",
                    "configuration_id": "*",
                    "eng_chg_level": "1",
                    "waiv_dev_rej_no": "*",
                    "activity_seq": 0,
                    "obj_id": "OBJ-1",
                    "job_order": "2579",
                    "machine_code": "M-10",
                    "work_center_no": "WC-1",
                    "operation_no": 20,
                    "operation_part_no": "MM-CAP001",
                    "operation_part_description": "Cap 1",
                    "operation_match_status": "matched",
                    "operation_ambiguous": False,
                    "operation_match_count": 1,
                }
            ],
        }

    monkeypatch.setattr(
        "app.features.ifs.api.fetch_package_label_checklist",
        fake_fetch,
    )

    response = client.get("/api/ifs/package-label-checklist")

    assert response.status_code == 200
    assert response.json() == {
        "summary": {
            "generated_at": "2026-06-24T08:00:00+03:00",
            "stock_count": 1,
            "row_count": 1,
            "job_order_count": 1,
            "operation_count": 1,
            "matched_count": 1,
            "part_matched_count": 1,
            "job_order_matched_count": 0,
            "ambiguous_count": 0,
            "not_found_count": 0,
            "missing_job_order_count": 0,
            "match_status_counts": {"matched": 1},
        },
        "rows": [
            {
                "contract": "S01",
                "part_no": "MM-CAP001",
                "part_description": "Cap 1",
                "location_no": "U0101",
                "qty_onhand": 10,
                "available_qty": 8,
                "uom": "PCS",
                "lot_batch_no": "2579-L1",
                "serial_no": "*",
                "receipt_date": "2026-06-24T05:00:00Z",
                "handling_unit_id": "HU-1",
                "configuration_id": "*",
                "eng_chg_level": "1",
                "waiv_dev_rej_no": "*",
                "activity_seq": 0,
                "obj_id": "OBJ-1",
                "job_order": "2579",
                "machine_code": "M-10",
                "work_center_no": "WC-1",
                "operation_no": 20,
                "operation_part_no": "MM-CAP001",
                "operation_part_description": "Cap 1",
                "operation_match_status": "matched",
                "operation_ambiguous": False,
                "operation_match_count": 1,
            }
        ],
    }


def test_ifs_label_material_availability_endpoint_returns_monitor_payload(
    client,
    monkeypatch,
):
    async def fake_fetch(_settings):
        return {
            "summary": {
                "generated_at": "2026-06-29T10:00:00+03:00",
                "monitor_only": True,
                "material_prefixes": ["HM", "YM"],
                "active_operation_status": "InProcess",
                "u1_location": "U1",
                "blocking_stock_field": "AvailableQty",
                "demand_field": "QtyRemainingToReserve",
                "material_qty_available_reference_field": "QtyAvailable",
                "source_operation_count": 2,
                "operation_count": 2,
                "checked_row_count": 1,
                "blocked_row_count": 1,
                "part_count": 1,
                "blocked_part_count": 1,
                "stock_row_count": 1,
                "stock_part_count": 1,
                "status_counts": {"blocked_insufficient_u1_available": 1},
                "blocked_parts": ["HM-A"],
            },
            "part_summaries": [
                {
                    "part_no": "HM-A",
                    "u1_demand_qty_remaining_to_reserve": 13,
                    "u1_available_qty": 10,
                    "u1_qty_onhand": 20,
                    "u1_shortage_qty": 3,
                    "is_blocked": True,
                }
            ],
            "stock_rows": [
                {
                    "contract": "S01",
                    "part_no": "HM-A",
                    "material_name": "Material A",
                    "location_no": "U1",
                    "available_qty": 10,
                    "qty_onhand": 20,
                }
            ],
            "checked_rows": [
                {
                    "order_no": "2615",
                    "release_no": "*",
                    "sequence_no": "*",
                    "line_item_no": 1,
                    "operation_no": 10,
                    "part_no": "HM-A",
                    "issue_to_location": "U1",
                    "qty_remaining_to_reserve": 13,
                    "qty_available": 100,
                    "material_qty_available_reference": 100,
                    "status": "blocked_insufficient_u1_available",
                    "is_blocked": True,
                    "hard_check_applicable": True,
                    "u1_available_qty": 10,
                    "u1_demand_qty_remaining_to_reserve": 13,
                    "u1_shortage_qty": 3,
                }
            ],
            "blocked_rows": [
                {
                    "order_no": "2615",
                    "release_no": "*",
                    "sequence_no": "*",
                    "line_item_no": 1,
                    "operation_no": 10,
                    "part_no": "HM-A",
                    "issue_to_location": "U1",
                    "qty_remaining_to_reserve": 13,
                    "qty_available": 100,
                    "material_qty_available_reference": 100,
                    "status": "blocked_insufficient_u1_available",
                    "is_blocked": True,
                    "hard_check_applicable": True,
                    "u1_available_qty": 10,
                    "u1_demand_qty_remaining_to_reserve": 13,
                    "u1_shortage_qty": 3,
                }
            ],
        }

    monkeypatch.setattr(
        "app.features.ifs.api.fetch_label_material_availability",
        fake_fetch,
    )

    response = client.get("/api/ifs/label-material-availability")

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["monitor_only"] is True
    assert payload["summary"]["material_prefixes"] == ["HM", "YM"]
    assert payload["summary"]["blocking_stock_field"] == "AvailableQty"
    assert payload["summary"]["blocked_row_count"] == 1
    assert payload["checked_rows"][0]["material_qty_available_reference"] == 100
    assert payload["blocked_rows"][0]["part_no"] == "HM-A"


def test_ifs_operations_endpoint_returns_pet_ongoing_operations(client, monkeypatch):
    async def fake_fetch(_settings):
        return [
            {
                "OrderNo": "2615",
                "ReleaseNo": "*",
                "SequenceNo": "*",
                "OperationNo": 10,
                "Contract": "S01",
                "WorkCenterNo": "SP25",
                "PartNo": "MM-PET0048-12-024Y-025",
                "PartNoDesc": "Bottle",
                "PreferredResourceId": "135",
                "OperationNoDesc": "Run",
                "RemainingQty": 42,
            }
        ]

    monkeypatch.setattr(
        "app.features.ifs.api.fetch_pet_ongoing_operations",
        fake_fetch,
    )

    response = client.get("/api/ifs/pet-ongoing-operations")

    assert response.status_code == 200
    assert response.json() == {
        "operation_count": 1,
        "operations": [
            {
                "order_no": "2615",
                "release_no": "*",
                "sequence_no": "*",
                "operation_no": 10,
                "contract": "S01",
                "work_center_no": "SP25",
                "part_no": "MM-PET0048-12-024Y-025",
                "part_description": "Bottle",
                "preferred_resource_id": "135",
                "operation_description": "Run",
                "remaining_qty": 42,
            }
        ],
    }


def test_ifs_whatsapp_status_message_endpoint_returns_copy_ready_message(
    client,
    monkeypatch,
):
    async def fake_fetch(_settings):
        return [
            {"PreferredResourceId": "101"},
            {"PreferredResourceId": "302"},
            {"PreferredResourceId": "210"},
        ]

    monkeypatch.setattr(
        "app.features.ifs.api.fetch_pet_ongoing_operations",
        fake_fetch,
    )

    response = client.get("/api/ifs/whatsapp-status-message")

    assert response.status_code == 200
    payload = response.json()
    assert payload["hall_numbers"] == [1, 2, 3, 4]
    assert payload["active_ifs_machine_count"] == 3
    assert payload["machine_count"] == 47
    assert payload["halls"][0]["hall_number"] == 1
    assert payload["halls"][0]["machines"][0] == {
        "machine_code": "101",
        "hall_number": 1,
        "hall_name": "Hole 1",
        "is_active": True,
        "status": "Üretim",
    }
    assert "Salon 3\n302 Üretim\n303 Kapalı" in payload["message"]
    assert "Salon 4\n202 Kapalı" in payload["message"]
    assert "210 Üretim" in payload["message"]
    assert payload["message"].count("IFS kontrolleri yapılmıştır.") == 4


def test_ifs_whatsapp_status_message_endpoint_returns_ifs_error(
    client,
    monkeypatch,
):
    async def fake_fetch(_settings):
        raise IFSClientError("IFS unavailable")

    monkeypatch.setattr(
        "app.features.ifs.api.fetch_pet_ongoing_operations",
        fake_fetch,
    )

    response = client.get("/api/ifs/whatsapp-status-message")

    assert response.status_code == 502
    assert "IFS unavailable" in response.json()["detail"]


def test_ifs_missing_production_starts_endpoint_lists_ifs_combinations_missing_from_db(
    client,
    monkeypatch,
):
    async def fake_fetch(_settings):
        return [
            {"PreferredResourceId": "302", "OrderNo": "WO-302"},
            {"PreferredResourceId": "303", "OrderNo": "WO-303"},
            {
                "PreferredResourceId": "302",
                "OrderNo": "WO-MISSING",
                "PartNoDesc": "Product Missing",
            },
        ]

    monkeypatch.setattr(
        "app.features.ifs.api.fetch_pet_ongoing_operations",
        fake_fetch,
    )
    context_id = _tour_context(client)
    for machine_code in ("302", "303", "101"):
        response = client.post(
            "/api/entries",
            json={
                "tour_context_id": context_id,
                "payload_schema_version": 2,
                "payload": {
                    "col_f": machine_code,
                    "col_g": f"Product {machine_code}",
                    "col_h": f"WO-{machine_code}",
                    "col_l": "12,5",
                },
            },
        )
        assert response.status_code == 201

    response = client.get(
        "/api/ifs/missing-production-starts",
        params={"process_date": "2026-06-08"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["process_date"] == "2026-06-08"
    assert payload["hall_numbers"] == [1, 2, 3, 4]
    assert payload["working_machine_count"] == 3
    assert payload["process_combination_count"] == 3
    assert payload["active_ifs_machine_count"] == 2
    assert payload["active_ifs_combination_count"] == 3
    assert payload["missing_count"] == 1
    assert payload["machines"] == [
        {
            "machine_code": "302",
            "hall_number": 3,
            "hall_name": "Hole 3",
            "latest_work_order": "WO-MISSING",
            "latest_product": "Product Missing",
            "latest_cycle_time": None,
            "latest_submitted_at": None,
            "entry_count": 0,
        }
    ]


def test_ifs_planning_first_job_statuses_endpoint_returns_plan_statuses(
    client,
    monkeypatch,
):
    planning_path = Path("planning.xlsx")

    def fake_resolve_planning_workbook(*_args, **_kwargs):
        return planning_path

    def fake_read_machine_planning_rows(_path):
        return [
            MachinePlanningRow(
                machine_code="302",
                order_no="2615",
                sheet_name="Plan",
                row_number=3,
                sequence_index=0,
                product_no="Product 2615",
                mold="Mold A",
                order_quantity="100",
                cell_value="2615",
                order_tag="1",
            ),
            MachinePlanningRow(
                machine_code="303",
                order_no="2710",
                sheet_name="Plan",
                row_number=4,
                sequence_index=1,
                product_no="Product 2710",
                mold="Mold B",
                order_quantity="80",
                cell_value="2710",
                order_tag="1",
            ),
        ]

    async def fake_fetch_active(_settings):
        return [{"PreferredResourceId": "302", "OrderNo": "2615"}]

    async def fake_fetch_stopped(_settings):
        return [{"PreferredResourceId": "303", "OrderNo": "2710"}]

    monkeypatch.setattr(
        "app.features.ifs.api.resolve_planning_workbook",
        fake_resolve_planning_workbook,
    )
    monkeypatch.setattr(
        "app.features.ifs.api.read_machine_planning_rows",
        fake_read_machine_planning_rows,
    )
    monkeypatch.setattr(
        "app.features.ifs.api.fetch_pet_ongoing_operations",
        fake_fetch_active,
    )
    monkeypatch.setattr(
        "app.features.ifs.api.fetch_pet_stopped_operations",
        fake_fetch_stopped,
    )

    response = client.get("/api/ifs/planning-first-job-statuses")

    assert response.status_code == 200
    payload = response.json()
    assert payload["planning_source_name"] == "planning.xlsx"
    assert payload["planning_row_count"] == 2
    assert payload["first_job_count"] == 2
    assert payload["active_operation_count"] == 1
    assert payload["stopped_operation_count"] == 1
    assert payload["ok_count"] == 1
    assert payload["baslatilacak_count"] == 1
    assert payload["acilacak_count"] == 0
    assert payload["action_count"] == 1
    assert [(row["machine_code"], row["order_no"], row["status"]) for row in payload["rows"]] == [
        ("302", "2615", "ok"),
        ("303", "2710", "baslatilacak"),
    ]


def test_ifs_missing_production_starts_endpoint_returns_ifs_error(
    client,
    monkeypatch,
):
    async def fake_fetch(_settings):
        raise IFSClientError("IFS unavailable")

    monkeypatch.setattr(
        "app.features.ifs.api.fetch_pet_ongoing_operations",
        fake_fetch,
    )

    response = client.get(
        "/api/ifs/missing-production-starts",
        params={"process_date": "2026-06-08"},
    )

    assert response.status_code == 502
    assert "IFS unavailable" in response.json()["detail"]


def test_ifs_used_materials_endpoint_returns_used_hm02_set(client, monkeypatch):
    async def fake_fetch(_settings):
        return {
            "operation_count": 2,
            "used_material_count": 2,
            "used_part_count": 1,
            "used_parts": ["HM-02-01-01-525"],
            "used_hm02_part_count": 1,
            "used_hm02_parts": ["HM-02-01-01-525"],
            "used_materials": [
                {
                    "OrderNo": "2615",
                    "ReleaseNo": "*",
                    "SequenceNo": "*",
                    "LineItemNo": 2,
                    "OperationNo": 10,
                    "PartNo": "HM-02-01-01-525",
                    "IssueToLoc": "U1",
                    "QtyRequired": 25.578,
                    "QtyAssigned": 0,
                    "QtyIssued": 0,
                    "QtyRemainingToReserve": 25.578,
                    "QtyAvailable": 100.72,
                    "PrintUnit": "kg",
                    "SoPartNo": "MM-PET0048-12-024Y-025",
                    "Cf_Tercihedilenkaynak": "135",
                },
                {
                    "OrderNo": "2616",
                    "ReleaseNo": "*",
                    "SequenceNo": "*",
                    "LineItemNo": 4,
                    "OperationNo": 20,
                    "PartNo": "HM-02-01-01-525",
                    "IssueToLoc": "U1",
                    "QtyRequired": 12,
                    "QtyAssigned": 0,
                    "QtyIssued": 0,
                    "QtyRemainingToReserve": 12,
                    "QtyAvailable": 50,
                    "PrintUnit": "kg",
                    "SoPartNo": "MM-PET0001",
                    "Cf_Tercihedilenkaynak": "136",
                },
            ],
        }

    monkeypatch.setattr("app.features.ifs.api.fetch_used_hm02_materials", fake_fetch)

    response = client.get("/api/ifs/used-hm02-materials")

    assert response.status_code == 200
    payload = response.json()
    assert payload["operation_count"] == 2
    assert payload["used_material_count"] == 2
    assert payload["used_part_count"] == 1
    assert payload["used_parts"] == ["HM-02-01-01-525"]
    assert payload["used_hm02_part_count"] == 1
    assert payload["used_hm02_parts"] == ["HM-02-01-01-525"]
    assert [row["part_no"] for row in payload["used_materials"]] == [
        "HM-02-01-01-525",
        "HM-02-01-01-525",
    ]
    assert payload["used_materials"][0]["machine"] == "135"
    assert payload["used_materials"][1]["produced_part_no"] == "MM-PET0001"


def test_ifs_return_candidates_endpoint_returns_unused_u1_stock(client, monkeypatch):
    async def fake_find(_settings):
        return {
            "generated_at": "2026-06-10T14:30:00+03:00",
            "stock_count": 3,
            "operation_count": 1,
            "active_used_material_count": 1,
            "active_used_part_count": 1,
            "active_used_hm02_part_count": 1,
            "planning_order_count": 1,
            "planning_operation_count": 1,
            "planning_used_material_count": 1,
            "planning_used_part_count": 1,
            "planning_used_hm02_part_count": 1,
            "stopped_operation_count": 1,
            "stopped_used_material_count": 1,
            "stopped_used_part_count": 1,
            "stopped_used_hm02_part_count": 1,
            "used_material_count": 3,
            "used_part_count": 3,
            "used_hm02_part_count": 3,
            "return_candidate_count": 1,
            "return_candidates": [
                {
                    "Contract": "S01",
                    "PartNo": "HM-04-C",
                    "PartNoRef": {"Description": "Candidate Material"},
                    "LocationNo": "U1",
                    "LotBatchNo": "L1",
                    "AvailableQty": 12.5,
                    "QtyOnhand": 15,
                    "UoM": "kg",
                    "ObjId": "obj-1",
                },
            ],
            "used_parts": ["HM-02-A", "HM-03-B", "HM-03-DURAN"],
            "used_hm02_parts": ["HM-02-A", "HM-03-B", "HM-03-DURAN"],
            "used_materials": [
                {
                    "OrderNo": "2615",
                    "ReleaseNo": "*",
                    "SequenceNo": "*",
                    "LineItemNo": 2,
                    "OperationNo": 10,
                    "PartNo": "HM-02-A",
                    "IssueToLoc": "U1",
                    "QtyRequired": 25.578,
                    "QtyAssigned": 0,
                    "QtyIssued": 0,
                    "QtyRemainingToReserve": 25.578,
                    "QtyAvailable": 100.72,
                    "PrintUnit": "kg",
                    "SoPartNo": "MM-PET0048-12-024Y-025",
                    "Cf_Tercihedilenkaynak": "135",
                },
                {
                    "OrderNo": "2579",
                    "ReleaseNo": "*",
                    "SequenceNo": "*",
                    "LineItemNo": 3,
                    "OperationNo": 20,
                    "PartNo": "HM-03-B",
                    "IssueToLoc": "U1",
                    "QtyRequired": 10,
                    "QtyAssigned": 0,
                    "QtyIssued": 0,
                    "QtyRemainingToReserve": 10,
                    "QtyAvailable": 40,
                    "PrintUnit": "kg",
                    "SoPartNo": "MM-PET0002",
                    "Cf_Tercihedilenkaynak": "172",
                },
                {
                    "OrderNo": "2616",
                    "ReleaseNo": "*",
                    "SequenceNo": "*",
                    "LineItemNo": 4,
                    "OperationNo": 20,
                    "PartNo": "HM-03-DURAN",
                    "IssueToLoc": "U1",
                    "QtyRequired": 5,
                    "QtyAssigned": 0,
                    "QtyIssued": 0,
                    "QtyRemainingToReserve": 5,
                    "QtyAvailable": 30,
                    "PrintUnit": "kg",
                    "SoPartNo": "MM-PET-DURAN",
                    "Cf_Tercihedilenkaynak": "261",
                },
            ],
        }

    monkeypatch.setattr("app.features.ifs.api.find_u1_return_candidates", fake_find)

    response = client.get("/api/ifs/u1-return-candidates")

    assert response.status_code == 200
    payload = response.json()
    assert payload["generated_at"] == "2026-06-10T14:30:00+03:00"
    assert payload["stock_count"] == 3
    assert payload["operation_count"] == 1
    assert payload["active_used_material_count"] == 1
    assert payload["active_used_part_count"] == 1
    assert payload["active_used_hm02_part_count"] == 1
    assert payload["planning_order_count"] == 1
    assert payload["planning_operation_count"] == 1
    assert payload["planning_used_material_count"] == 1
    assert payload["planning_used_part_count"] == 1
    assert payload["planning_used_hm02_part_count"] == 1
    assert payload["stopped_operation_count"] == 1
    assert payload["stopped_used_material_count"] == 1
    assert payload["stopped_used_part_count"] == 1
    assert payload["stopped_used_hm02_part_count"] == 1
    assert payload["used_material_count"] == 3
    assert payload["used_part_count"] == 3
    assert payload["used_hm02_part_count"] == 3
    assert payload["return_candidate_count"] == 1
    assert payload["used_parts"] == ["HM-02-A", "HM-03-B", "HM-03-DURAN"]
    assert payload["used_hm02_parts"] == ["HM-02-A", "HM-03-B", "HM-03-DURAN"]
    assert [row["lot_batch_no"] for row in payload["return_candidates"]] == [
        "L1",
    ]
    assert [row["part_no"] for row in payload["return_candidates"]] == [
        "HM-04-C",
    ]
    assert [row["material_name"] for row in payload["return_candidates"]] == [
        "Candidate Material",
    ]
    assert all("obj_id" not in row for row in payload["return_candidates"])
    assert payload["used_materials"][0]["part_no"] == "HM-02-A"
    assert payload["used_materials"][0]["machine"] == "135"
    assert payload["used_materials"][1]["part_no"] == "HM-03-B"
    assert payload["used_materials"][2]["order_no"] == "2616"
    assert payload["used_materials"][2]["operation_no"] == 20
    assert payload["used_materials"][2]["part_no"] == "HM-03-DURAN"
