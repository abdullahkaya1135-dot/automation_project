# ruff: noqa: F401
from .shared_request_page_utils_cases import (
    test_client_recorded_datetime_rejects_invalid_iso_value,
    test_client_recorded_datetime_uses_request_timezone,
    test_optional_bool_accepts_empty_and_common_form_values,
    test_recorded_date_text_leaves_non_iso_values_unchanged,
    test_request_timezone_falls_back_to_fixed_istanbul_offset,
    test_settings_from_request_initializes_once_and_caches,
    test_settings_from_request_reuses_existing_app_state,
    test_shift_chief_canonicalizes_known_options_case_insensitively,
    test_shift_for_request_time_covers_full_day_edges,
    test_stored_client_recorded_at_accepts_utc_value_without_offset_change,
    test_stored_client_recorded_at_preserves_none,
    test_stored_client_recorded_at_strips_timezone_after_utc_conversion,
    test_tour_timing_for_datetime_formats_date_shift_timezone_and_generated_at,
)
