# ruff: noqa: F401
from .production_loss_service_cases import (
    test_normalize_ifs_actual_rows_uses_realized_operation_statistics_fields,
    test_normalize_inventory_label_rows_dedupes_stock_journey_by_physical_label,
    test_normalize_inventory_label_rows_uses_receipt_date_for_record_date_and_shift,
    test_normalize_operation_history_rows_uses_local_time_for_date_and_shift,
)
