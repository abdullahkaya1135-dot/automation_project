from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_refactored_routers_delegate_session_work_to_services():
    for router_name in ("entries.py", "auxiliary.py", "bootstrap.py", "health.py"):
        source = (PROJECT_ROOT / "app" / "routers" / router_name).read_text(
            encoding="utf-8"
        )

        assert "create_session" not in source
        assert "commit_session" not in source
        assert "session.add" not in source
        assert "attempt_excel_append" not in source
        assert "attempt_auxiliary_excel_append" not in source


def test_ifs_router_delegates_payload_assembly_to_use_cases():
    source = (PROJECT_ROOT / "app" / "routers" / "ifs.py").read_text(
        encoding="utf-8"
    )

    assert "fetch_" not in source
    assert "serialize_" not in source
    assert "find_u1_return_candidates" not in source
    assert "return_candidate_count" not in source


def test_ifs_materials_delegates_row_normalization_and_concurrency_helpers():
    source = (PROJECT_ROOT / "app" / "modules" / "ifs" / "materials.py").read_text(
        encoding="utf-8"
    )

    assert "material_rows" in source
    assert "concurrency" in source
    assert "asyncio.Semaphore" not in source
    assert "seen_keys" not in source
    assert "LineItemNo" not in source


def test_production_planning_reader_delegates_spreadsheet_xml_mechanics():
    source = (
        PROJECT_ROOT / "app" / "modules" / "production_planning" / "reader.py"
    ).read_text(encoding="utf-8")

    assert "spreadsheet_xml" in source
    assert "posixpath" not in source
    assert "REL_NS" not in source
    assert "MAIN_NS" not in source
    assert "workbook.xml.rels" not in source


def test_pages_router_delegates_role_policy_to_web_permissions():
    source = (PROJECT_ROOT / "app" / "routers" / "pages.py").read_text(
        encoding="utf-8"
    )

    assert "NAV_ITEMS" not in source
    assert "ROLE_LABELS" not in source
    assert "ROLE_ADMIN" not in source
    assert "ROLE_OPERATOR" not in source
    assert "ROLE_UTILITY" not in source
    assert "ROLE_SUPERVISOR" not in source
    assert "ROLE_PLANNING" not in source
    assert "request_role" not in source
    assert "is_request_authenticated" not in source
    assert "default_path_for_role" not in source
    assert "workspace_by_page_id" in source


def test_web_permissions_delegates_navigation_to_workspace_catalog():
    source = (PROJECT_ROOT / "app" / "web" / "permissions.py").read_text(
        encoding="utf-8"
    )

    assert ".workspaces" in source
    assert "nav_items_for_role" in source
    assert "NAV_ITEMS" not in source
    assert "ROLE_OPERATOR" not in source
    assert "ROLE_UTILITY" not in source
    assert "ROLE_SUPERVISOR" not in source
    assert "ROLE_PLANNING" not in source


def test_web_workspaces_owns_role_workspace_catalog():
    source = (PROJECT_ROOT / "app" / "web" / "workspaces.py").read_text(
        encoding="utf-8"
    )

    assert "WORKSPACES" in source
    assert "Workspace(" in source
    assert "nav_items_for_role" in source
    assert "pages/operator.html" in source
    assert "pages/utility.html" in source
    assert "pages/supervisor.html" in source
    assert "pages/planning.html" in source


def test_app_entrypoint_delegates_cache_policy_to_web_module():
    main_source = (PROJECT_ROOT / "app" / "main.py").read_text(encoding="utf-8")
    cache_source = (PROJECT_ROOT / "app" / "web" / "cache_headers.py").read_text(
        encoding="utf-8"
    )

    assert "apply_cache_headers" in main_source
    assert '"/operator"' not in main_source
    assert '"/static/"' not in main_source
    assert "Cache-Control" not in main_source
    assert "WORKSPACES" in cache_source
    assert "UI_NO_STORE_PATHS" in cache_source
    assert "Cache-Control" in cache_source


def test_database_entrypoint_delegates_schema_migrations():
    database_source = (PROJECT_ROOT / "app" / "database.py").read_text(
        encoding="utf-8"
    )
    migrations_source = (PROJECT_ROOT / "app" / "db" / "migrations.py").read_text(
        encoding="utf-8"
    )

    assert "ensure_schema_migrations" in database_source
    assert "entries_canonical_fields_v2" not in database_source
    assert "ALTER TABLE" not in database_source
    assert "CREATE UNIQUE INDEX" not in database_source
    assert "entries_canonical_fields_v2" in migrations_source
    assert "ALTER TABLE" in migrations_source
    assert "CREATE UNIQUE INDEX" in migrations_source


def test_auth_service_delegates_role_policy_and_session_cookie_mechanics():
    source = (PROJECT_ROOT / "app" / "modules" / "auth" / "service.py").read_text(
        encoding="utf-8"
    )

    assert ".roles" in source
    assert ".session" in source
    assert "compare_digest" not in source
    assert "json.loads" not in source
    assert "base64" not in source
    assert "hmac" not in source


def test_reports_router_delegates_report_assembly_to_use_cases():
    source = (PROJECT_ROOT / "app" / "routers" / "reports.py").read_text(
        encoding="utf-8"
    )

    assert "shifts" not in source
    assert "create_cycle_report" not in source


def test_cycle_report_service_delegates_sources_builder_and_writer():
    source = (
        PROJECT_ROOT / "app" / "modules" / "reports" / "cycle_report_service.py"
    ).read_text(encoding="utf-8")

    assert "cycle_sources" in source
    assert "cycle_builder" in source
    assert "cycle_writer" in source
    assert "load_workbook" not in source
    assert "Workbook(" not in source
    assert "worksheet." not in source


def test_offline_service_delegates_record_processing_excel_and_response():
    source = (PROJECT_ROOT / "app" / "modules" / "offline" / "service.py").read_text(
        encoding="utf-8"
    )

    assert "process_offline_records" in source
    assert "sync_offline_excel_targets" in source
    assert "offline_bulk_response" in source
    assert "save_tour_context" not in source
    assert "save_process_entry" not in source
    assert "append_entries_to_workbook" not in source
    assert "sync_auxiliary_submissions_batch" not in source


def test_offline_records_delegate_envelope_and_dependency_resolution():
    source = (PROJECT_ROOT / "app" / "modules" / "offline" / "records.py").read_text(
        encoding="utf-8"
    )

    assert ".envelope" in source
    assert ".dependencies" in source
    assert "process_offline_records" in source
    assert "client_request_id alanlari" not in source
    assert "get_tour_context_by_client_request_id" not in source
    assert "depends_on_client_request_id" not in source


def test_offline_envelope_owns_client_id_and_timestamp_normalization():
    source = (PROJECT_ROOT / "app" / "modules" / "offline" / "envelope.py").read_text(
        encoding="utf-8"
    )

    assert "body_for_record" in source
    assert "client_request_id alanlari eslesmiyor" in source
    assert "client_recorded_at" in source
    assert "save_process_entry" not in source
    assert "save_tour_context" not in source


def test_offline_bulk_schema_uses_discriminated_record_models():
    source = (PROJECT_ROOT / "app" / "schemas.py").read_text(encoding="utf-8")
    envelope_source = (
        PROJECT_ROOT / "app" / "modules" / "offline" / "envelope.py"
    ).read_text(encoding="utf-8")

    assert "class ProcessEntryBulkRecord" in source
    assert "class TourContextBulkRecord" in source
    assert "class AuxiliarySubmissionBulkRecord" in source
    assert 'Field(discriminator="type")' in source
    assert "body: dict[str, Any]" not in source
    assert "model_dump" in envelope_source


def test_offline_dependencies_own_entry_context_resolution():
    source = (
        PROJECT_ROOT / "app" / "modules" / "offline" / "dependencies.py"
    ).read_text(encoding="utf-8")

    assert "resolve_entry_dependency" in source
    assert "depends_on_client_request_id" in source
    assert "get_tour_context_by_client_request_id" in source
    assert "Bagimli tur bilgisi bulunamadi" in source
    assert "save_process_entry" not in source


def test_process_entry_sync_delegates_status_and_result_shapes():
    source = (
        PROJECT_ROOT / "app" / "modules" / "sync" / "process_entry_sync.py"
    ).read_text(encoding="utf-8")

    assert "process_entry_results" in source
    assert "mark_process_entry_sync_failed" in source
    assert "mark_process_entry_synced" in source
    assert "retry_summary" in source
    assert "utc_now" not in source
    assert '"entry_id": entry.id' not in source


def test_process_entry_batch_sync_shared_by_retry_and_offline_paths():
    retry_source = (
        PROJECT_ROOT / "app" / "modules" / "sync" / "process_entry_sync.py"
    ).read_text(encoding="utf-8")
    offline_source = (
        PROJECT_ROOT / "app" / "modules" / "offline" / "excel_sync.py"
    ).read_text(encoding="utf-8")

    assert "def sync_process_entries_batch" in retry_source
    assert "sync_process_entries_batch" in offline_source
    assert "append_entries_to_workbook" not in offline_source
    assert "mark_process_entry_sync_failed" not in offline_source
    assert "mark_process_entry_synced" not in offline_source


def test_retry_services_share_summary_shape():
    process_source = (
        PROJECT_ROOT / "app" / "modules" / "sync" / "process_entry_sync.py"
    ).read_text(encoding="utf-8")
    auxiliary_source = (
        PROJECT_ROOT / "app" / "modules" / "auxiliary_systems" / "sync_service.py"
    ).read_text(encoding="utf-8")
    shared_source = (
        PROJECT_ROOT / "app" / "modules" / "sync" / "retry_results.py"
    ).read_text(encoding="utf-8")

    assert ".retry_results" in process_source
    assert "sync.retry_results" in auxiliary_source
    assert "def retry_summary" not in (
        PROJECT_ROOT / "app" / "modules" / "sync" / "process_entry_results.py"
    ).read_text(encoding="utf-8")
    assert "def retry_summary" not in (
        PROJECT_ROOT / "app" / "modules" / "auxiliary_systems" / "sync_results.py"
    ).read_text(encoding="utf-8")
    assert "stopped_on_error" in shared_source
    assert '"results": results' in shared_source


def test_offline_excel_sync_uses_process_entry_status_helpers():
    source = (
        PROJECT_ROOT / "app" / "modules" / "offline" / "excel_sync.py"
    ).read_text(encoding="utf-8")

    assert "sync_process_entries_batch" in source
    assert "entry.sync_status =" not in source
    assert "utc_now" not in source


def test_auxiliary_domain_uses_field_module_not_workbook_io():
    domain_source = (
        PROJECT_ROOT / "app" / "domain" / "auxiliary_payloads.py"
    ).read_text(encoding="utf-8")
    field_definition_source = (
        PROJECT_ROOT / "app" / "modules" / "bootstrap" / "field_definitions.py"
    ).read_text(encoding="utf-8")

    assert "auxiliary_systems.fields" in domain_source
    assert "auxiliary_systems.fields" in field_definition_source
    assert "workbook_service" not in domain_source
    assert "workbook_service" not in field_definition_source


def test_entry_payloads_delegate_temperature_shorthand_expansion():
    source = (PROJECT_ROOT / "app" / "domain" / "entry_payloads.py").read_text(
        encoding="utf-8"
    )
    temperature_source = (
        PROJECT_ROOT / "app" / "domain" / "entry_temperature.py"
    ).read_text(encoding="utf-8")

    assert "entry_temperature" in source
    assert "expand_temperature_shorthand_fields" in source
    assert "re.compile" not in source
    assert "TEMPERATURE_REPEAT_TOKEN_PATTERN" not in source
    assert "TEMPERATURE_REPEAT_TOKEN_PATTERN" in temperature_source
    assert "expand_temperature_shorthand" in temperature_source


def test_auxiliary_workbook_service_delegates_file_io_to_workbook_io():
    source = (
        PROJECT_ROOT / "app" / "modules" / "auxiliary_systems" / "workbook_service.py"
    ).read_text(encoding="utf-8")

    assert "workbook_io" in source
    assert "workbook_append" in source
    assert "load_workbook" not in source
    assert "shutil" not in source
    assert "copyfile" not in source
    assert "backup_filename" not in source


def test_auxiliary_workbook_append_delegates_file_io_to_workbook_io():
    source = (
        PROJECT_ROOT / "app" / "modules" / "auxiliary_systems" / "workbook_append.py"
    ).read_text(encoding="utf-8")

    assert "workbook_io" in source
    assert "workbook_matching" in source
    assert "load_workbook" not in source
    assert "shutil" not in source
    assert "copyfile" not in source
    assert "backup_filename" not in source
    assert "def find_matching_auxiliary_block_in_worksheet" not in source
    assert "auxiliary_row_matches_expected" not in source


def test_auxiliary_workbook_matching_owns_reuse_scan():
    source = (
        PROJECT_ROOT
        / "app"
        / "modules"
        / "auxiliary_systems"
        / "workbook_matching.py"
    ).read_text(encoding="utf-8")

    assert "find_matching_auxiliary_block_in_worksheet" in source
    assert "auxiliary_row_matches_expected" in source
    assert "copy_auxiliary_row_format" not in source
    assert "workbook.save" not in source


def test_auxiliary_sync_service_delegates_serialization_and_result_shapes():
    source = (
        PROJECT_ROOT / "app" / "modules" / "auxiliary_systems" / "sync_service.py"
    ).read_text(encoding="utf-8")

    assert "serializers" in source
    assert "sync_results" in source
    assert "json.loads" not in source
    assert "payload_json" not in source
    assert "isoformat" not in source


def test_process_workbook_service_delegates_file_io_to_workbook_io():
    source = (
        PROJECT_ROOT / "app" / "modules" / "process_entry" / "workbook_service.py"
    ).read_text(encoding="utf-8")

    assert "workbook_append" in source
    assert "workbook_matching" in source
    assert "serialized_excel_write" in source
    assert "load_workbook" not in source
    assert "shutil" not in source
    assert "copyfile" not in source
    assert "backup_filename" not in source
    assert "open_workbook_sheet" not in source
    assert "workbook.save" not in source
    assert "worksheet.cell" not in source
    assert "def _find_matching_entry_row_unlocked" not in source
    assert "def _row_matches_expected" not in source


def test_process_workbook_append_owns_unlocked_writes():
    source = (
        PROJECT_ROOT / "app" / "modules" / "process_entry" / "workbook_append.py"
    ).read_text(encoding="utf-8")

    assert "workbook_io" in source
    assert "workbook_matching" in source
    assert "append_entries_to_workbook_unlocked" in source
    assert "write_process_entry_row" in source
    assert "save_process_workbook" in source
    assert "serialized_excel_write" not in source
    assert "load_workbook" not in source
    assert "shutil" not in source
    assert "backup_filename" not in source


def test_process_workbook_matching_owns_reuse_scan():
    source = (
        PROJECT_ROOT / "app" / "modules" / "process_entry" / "workbook_matching.py"
    ).read_text(encoding="utf-8")

    assert "find_matching_entry_row" in source
    assert "match_existing_entry_rows_in_worksheet" in source
    assert "row_matches_expected" in source
    assert "workbook.save" not in source
    assert "create_workbook_backup" not in source


def test_process_excel_mapper_delegates_schema_and_value_normalization():
    source = (
        PROJECT_ROOT / "app" / "modules" / "process_entry" / "excel_mapper.py"
    ).read_text(encoding="utf-8")

    assert ".excel_schema" in source
    assert ".excel_values" in source
    assert "get_column_letter" not in source
    assert "re.compile" not in source
    assert "HEADER_KEYWORDS_BY_COLUMN = {" not in source
    assert "PROCESS_ENTRY_ATTRIBUTE_BY_COLUMN = {" not in source


def test_process_workbook_io_uses_excel_schema_without_mapper_dependency():
    source = (
        PROJECT_ROOT / "app" / "modules" / "process_entry" / "workbook_io.py"
    ).read_text(encoding="utf-8")

    assert ".excel_schema" in source
    assert ".excel_mapper" not in source


def test_workbook_io_modules_delegate_last_value_row_scan():
    for relative_path in (
        "app/modules/process_entry/workbook_io.py",
        "app/modules/auxiliary_systems/workbook_io.py",
    ):
        source = (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")

        assert "workbook_rows" in source
        assert "detect_last_value_row_in_columns" in source
        assert 'getattr(worksheet, "_cells", None)' not in source
        assert "iter_rows(" not in source


def test_process_workbook_service_uses_value_helpers_directly():
    source = (
        PROJECT_ROOT / "app" / "modules" / "process_entry" / "workbook_service.py"
    ).read_text(encoding="utf-8")

    assert ".excel_values" in source
    assert "normalize_excel_value as _normalize_excel_value" in source
    assert ".excel_mapper import (" not in source


def test_stale_layer_first_compatibility_shims_are_removed():
    stale_paths = (
        "app/adapters",
        "app/auth.py",
        "app/integrations",
        "app/repositories",
        "app/services",
        "app/services/auxiliary_submission_service.py",
        "app/services/cycle_report_service.py",
        "app/services/excel_service.py",
        "app/services/process_entry_service.py",
        "app/services/production_planning.py",
        "app/services/shop_order_source.py",
        "app/services/sync_service.py",
        "app/services/tour_context_service.py",
    )

    for relative_path in stale_paths:
        assert not (PROJECT_ROOT / relative_path).exists()
