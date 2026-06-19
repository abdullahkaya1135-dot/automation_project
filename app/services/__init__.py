"""Shared service adapters used across feature packages.

Feature-specific workflow code should stay under ``app.features``. This package
keeps cross-feature adapters and helpers whose import paths need to remain
stable while larger service-boundary moves happen in batches.
"""

__all__ = (
    "excel_service",
    "excel_write_lock",
    "shop_order_source",
    "workbook_utils",
)
