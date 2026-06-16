import pytest
from pydantic import ValidationError

from app.schemas import OfflineBulkSyncRequest, ProcessEntryBulkRecord


def test_offline_bulk_entry_record_validates_process_body_model():
    request = OfflineBulkSyncRequest.model_validate(
        {
            "records": [
                {
                    "type": "entry",
                    "client_request_id": "entry-1",
                    "depends_on_client_request_id": "tour-1",
                    "body": {
                        "client_request_id": "entry-1",
                        "payload_schema_version": 2,
                        "payload": {
                            "col_f": "M-01",
                            "col_h": "WO-01",
                        },
                    },
                }
            ]
        }
    )

    record = request.records[0]
    assert isinstance(record, ProcessEntryBulkRecord)
    assert record.body.client_request_id == "entry-1"
    assert record.body.payload == {
        "col_f": "M-01",
        "col_h": "WO-01",
    }


def test_offline_bulk_record_discriminator_validates_type_specific_body():
    with pytest.raises(ValidationError):
        OfflineBulkSyncRequest.model_validate(
            {
                "records": [
                    {
                        "type": "tour_context",
                        "client_request_id": "tour-1",
                        "body": {
                            "client_request_id": "tour-1",
                        },
                    }
                ]
            }
        )
