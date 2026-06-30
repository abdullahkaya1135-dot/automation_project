from __future__ import annotations

from app.integrations.ifs.client import (
    serialize_material_row,
    serialize_operation_row,
    serialize_package_label_checklist_row,
    serialize_stock_row,
)


def test_serialize_stock_row_uses_api_output_shape():
    payload = serialize_stock_row(
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
    )

    assert payload["contract"] == "S01"
    assert payload["part_no"] == "HM-02-A"
    assert payload["material_name"] == "Raw Material"
    assert payload["location_no"] == "U1"
    assert payload["lot_batch_no"] == "L1"
    assert payload["available_qty"] == 12.5
    assert payload["qty_onhand"] == 15
    assert payload["uom"] == "kg"
    assert payload["obj_id"] == "obj-1"


def test_serialize_package_label_checklist_row_uses_api_output_shape():
    payload = serialize_package_label_checklist_row(
        {
            "Contract": "S01",
            "PartNo": "MM-CAP001",
            "PartNoDesc": "Cap 1",
            "LocationNo": "U0101",
            "QtyOnhand": 10,
            "AvailableQty": 8,
            "UoM": "PCS",
            "LotBatchNo": "2579-L1",
            "SerialNo": "*",
            "ReceiptDate": "2026-06-24T05:00:00Z",
            "HandlingUnitId": 284844,
            "ConfigurationId": "*",
            "EngChgLevel": "1",
            "WaivDevRejNo": "*",
            "ActivitySeq": 0,
            "ObjId": "obj-1",
        }
    )

    assert payload == {
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
        "handling_unit_id": "284844",
        "configuration_id": "*",
        "eng_chg_level": "1",
        "waiv_dev_rej_no": "*",
        "activity_seq": 0,
        "obj_id": "obj-1",
    }


def test_serialize_operation_row_uses_api_output_shape():
    payload = serialize_operation_row(
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
    )

    assert payload == {
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


def test_serialize_material_row_uses_api_output_shape():
    payload = serialize_material_row(
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
        }
    )

    assert payload == {
        "order_no": "2615",
        "release_no": "*",
        "sequence_no": "*",
        "line_item_no": 2,
        "operation_no": 10,
        "part_no": "HM-02-01-01-525",
        "issue_to_location": "U1",
        "qty_required": 25.578,
        "qty_assigned": 0,
        "qty_issued": 0,
        "qty_remaining_to_reserve": 25.578,
        "qty_available": 100.72,
        "print_unit": "kg",
        "produced_part_no": "MM-PET0048-12-024Y-025",
        "machine": "135",
    }
