from app.shop_order_source import (
    ShopOrderSourceError,
    extract_shop_order_options,
    shop_order_source_payload,
)


def test_extract_shop_order_options_from_odata_payload():
    options = extract_shop_order_options(
        """
        {
          "value": [
            {"OrderNo": "10", "ResourceId": "2"},
            {"OrderNo": "10", "ResourceId": "2"},
            {"OrderNo": "9", "ResourceId": "10"},
            {"OrderNo": "", "ResourceId": "11"},
            {"OrderNo": "12", "ResourceId": null}
          ]
        }
        """
    )

    assert [(option.order_no, option.resource_id) for option in options] == [
        ("10", "2"),
        ("9", "10"),
    ]


def test_extract_shop_order_options_from_embedded_json():
    options = extract_shop_order_options(
        '<html><body>{"value":[{"OrderNo":"WO-1","ResourceId":"M-01"}]}</body></html>'
    )

    assert [(option.order_no, option.resource_id) for option in options] == [
        ("WO-1", "M-01"),
    ]


def test_extract_shop_order_options_rejects_missing_value_list():
    try:
        extract_shop_order_options('{"value": {"OrderNo": "WO-1"}}')
    except ShopOrderSourceError as exc:
        assert "value listesi" in str(exc)
    else:
        raise AssertionError("Expected ShopOrderSourceError")


def test_shop_order_source_payload_reports_missing_file(tmp_path):
    payload = shop_order_source_payload(str(tmp_path / "missing.txt"))

    assert payload["available"] is False
    assert payload["operation_count"] == 0
    assert "bulunamadı" in payload["last_error"]
