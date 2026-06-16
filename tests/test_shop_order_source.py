from app.modules.shop_orders.source import (
    ifs_shop_order_source_payload,
    shop_order_options_from_ifs_operations,
)


def test_shop_order_options_from_ifs_operations_maps_fields_and_deduplicates():
    options = shop_order_options_from_ifs_operations(
        [
            {
                "OrderNo": "2615",
                "ReleaseNo": "*",
                "SequenceNo": "*",
                "OperationNo": 10,
                "PartNo": "MM-PET0001",
                "PreferredResourceId": "135",
                "WorkCenterNo": "SP25",
                "PartNoDesc": "Bottle",
            },
            {
                "OrderNo": "2615",
                "PreferredResourceId": "135",
                "OperationNo": 10,
            },
            {
                "OrderNo": "2616",
                "ReleaseNo": "*",
                "SequenceNo": "*",
                "OperationNo": 20,
                "PartNo": "MM-PET0002",
                "PreferredResourceId": "136",
                "WorkCenterNo": "SP26",
                "PartNoDesc": "Bottle 2",
            },
        ]
    )

    assert [(option.order_no, option.resource_id) for option in options] == [
        ("2615", "135"),
        ("2616", "136"),
    ]
    assert options[0].release_no == "*"
    assert options[0].sequence_no == "*"
    assert options[0].operation_no == 10
    assert options[0].part_no == "MM-PET0001"
    assert options[0].work_center_no == "SP25"
    assert options[0].part_description == "Bottle"


def test_ifs_shop_order_source_payload_uses_token_source_shape():
    payload = ifs_shop_order_source_payload(
        [
            {
                "OrderNo": "2615",
                "PreferredResourceId": "135",
                "ReleaseNo": "*",
                "SequenceNo": "*",
                "OperationNo": 10,
                "PartNo": "MM-PET0001",
                "PartNoDesc": "Bottle",
            },
            {
                "OrderNo": "2616",
                "PreferredResourceId": "136",
                "ReleaseNo": "*",
                "SequenceNo": "*",
                "OperationNo": 20,
                "PartNo": "MM-PET0002",
                "PartNoDesc": "Bottle 2",
            },
        ]
    )

    assert payload["available"] is True
    assert payload["source"] == "ifs-token"
    assert payload["operation_count"] == 2
    assert payload["order_count"] == 2
    assert payload["resource_count"] == 2
    assert payload["options"] == [
        {
            "order_no": "2615",
            "resource_id": "135",
            "release_no": "*",
            "sequence_no": "*",
            "operation_no": 10,
            "part_no": "MM-PET0001",
            "part_description": "Bottle",
        },
        {
            "order_no": "2616",
            "resource_id": "136",
            "release_no": "*",
            "sequence_no": "*",
            "operation_no": 20,
            "part_no": "MM-PET0002",
            "part_description": "Bottle 2",
        },
    ]


def test_shop_order_options_keep_multiple_operations_for_same_machine_order():
    payload = ifs_shop_order_source_payload(
        [
            {
                "OrderNo": "2615",
                "PreferredResourceId": "135",
                "ReleaseNo": "*",
                "SequenceNo": "*",
                "OperationNo": 10,
            },
            {
                "OrderNo": "2615",
                "PreferredResourceId": "135",
                "ReleaseNo": "*",
                "SequenceNo": "*",
                "OperationNo": 20,
            },
        ]
    )

    assert payload["operation_count"] == 2
    assert [option["operation_no"] for option in payload["options"]] == [10, 20]
