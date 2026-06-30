# Refactoring Plan

Generated: 2026-06-30

This plan is based on a full repository review using the maximum concurrent
subagents available in this environment. Six agents could run at once; after
the initial six finished, two additional agents reviewed the remaining
script/artifact and repository-hygiene slices. The review was read-only except
for creating this plan.

## Review Coverage

| Agent | Area reviewed |
| --- | --- |
| Heisenberg | `app/main.py`, `app/models.py`, core, domain, integrations, web, auth, health, bootstrap |
| Beauvoir | Process entries, auxiliary systems, amount control, breakdowns, shift manager |
| Linnaeus | Cycle reports, production loss, production planning, IFS APIs/checks, shared services |
| Turing | Browser JavaScript modules, service worker, manifest |
| Planck | Templates and stylesheet |
| Ampere | Tests, pytest config, requirements, CI |
| Noether | `scripts/`, `cycle_time_analysis_work/`, `worker_cycle_report/` |
| Jason | README, docs, data, outputs, logs, local certs, root artifacts |

## Main Hotspots

The most urgent mixed-purpose files are:

| File | Main problem |
| --- | --- |
| `app/integrations/ifs/client.py` | OAuth, HTTP retry, OData builders, archive XML parsing, inventory, operations, label workflows, material checks, production-loss queries, and production-planning coupling in one 3k+ line client. |
| `app/features/production_loss/service.py` | Report orchestration, IFS fetch/cache, process metadata, breakdown allocation, loss math, DB persistence, serialization, and workbook output in one large service. |
| `tests/test_api_routes.py` | API behavior, DB persistence, page rendering, service worker, JS/CSS source assertions, and report flows in one suite. |
| `tests/test_ifs_client.py` | IFS config compatibility, raw URL contracts, stock, operations, materials, labels, return candidates, and serializers in one suite. |
| `app/static/js/modules/render.js` | Rendering for entries, reports, IFS checks, production loss, print areas, and compatibility adapters in one renderer. |
| `app/static/js/modules/main-page.js` | App routing, bootstrap hydration, offline refresh, form submits, report actions, retry flows, and page wiring in one module. |
| `app/core/database.py` | Engine/session setup, schema creation, hand-written migrations, seed data, repairs, and cycle-table seeding together. |
| `app/models.py` | Shared, feature-owned, and report/cache ORM models plus sync constants in one central module. |
| `app/static/js/modules/offline.js` | Service-worker registration, IndexedDB, outbox sync, UI status, exports, bootstrap cache, and server retry flushing together. |
| `app/features/auxiliary_systems/workbook.py` | Field schema, header checks, row building, workbook IO, style copy, append/match, backup, and health checks together. |
| `app/features/shift_manager/service.py` | IFS fetches, production-planning parsing, normalization, matching, payload shaping, and informed-state compatibility together. |
| `app/features/cycle_reports/service.py` | Process DB reads, IFS fetch, cycle-table reads, matching, workbook writing, filesystem output, and shared product parsing together. |
| `app/static/css/app.css` | Tokens, shell, forms, dashboard, tables, feature reports, print CSS, and responsive nav in one stylesheet. |
| `outputs/**`, `data/**`, `runtime-logs/**` | Source-like scripts, generated reports, private runtime data, logs, local dependencies, and large artifacts are mixed. |

## Refactoring Principles

1. Preserve behavior first. Every extraction should keep public imports or add
   compatibility facades until callers and tests are moved.
2. Split tests and fixtures before risky production refactors. Large files are
   currently acting as accidental integration tests; make that coverage easier
   to trust first.
3. Keep generated/runtime data out of source boundaries. Promote reusable
   scripts before ignoring or archiving output folders.
4. Prefer pure extraction before architectural rewrites. Move parsers,
   normalizers, serializers, row builders, and calculations first.
5. Preserve frontend IDs, route paths, request/response shapes, and Excel
   columns during early phases.
6. Run focused tests after every phase and the full suite before removing
   compatibility shims.

## Logical Sequence

The order below minimizes dependency conflicts. Some tasks inside a phase can
run in parallel, but phases should generally be completed in order.

## Phase 1 - Test Harness And Safety Baseline

Goal: make the current behavior cheaper to verify before splitting large
production modules.

Files needing attention:

- `tests/conftest.py`
- `tests/test_api_routes.py`
- `tests/test_database_model.py`
- `tests/test_ifs_client.py`
- `tests/test_production_loss_service.py`
- `tests/test_excel_service.py`
- `tests/test_cycle_report_service.py`
- `tests/test_cycle_time_analysis_comparison.py`
- `tests/test_shared_request_page_utils.py`
- `tests/test_shift_manager_ui_wiring.py`
- `requirements.txt`
- `requirements-dev.txt`
- `tests/.gitkeep`

Subagent work packages:

1. Test Fixtures Agent
   - Add shared settings factories, authenticated `TestClient` helpers,
     workbook fixtures, legacy SQLite builders, and IFS mock transport helpers.
   - Keep existing test behavior intact.
   - Acceptance: existing tests can import the new helpers without changing
     assertions.

2. Route Suite Split Agent
   - Split `tests/test_api_routes.py` into feature route suites plus `tests/web/`
     and `tests/static/`.
   - Preserve all existing assertions first; do not rewrite behavior checks
     while moving them.
   - Acceptance: moved tests pass and failures identify one feature area.

3. Database Suite Split Agent
   - Split `tests/test_database_model.py` into schema, seed data, migrations,
     constraints, and session-scope suites.
   - Extract reusable legacy DB setup to support later migration refactors.
   - Acceptance: migration and seed failures are isolated by suite.

4. IFS Test Split Agent
   - Split `tests/test_ifs_client.py` under `tests/integrations/ifs/` by
     transport/OData, archive labels, inventory/materials, operations, and return
     candidates.
   - Add common request recorder helpers.
   - Acceptance: future `app.integrations.ifs` module splits can update one
     focused test file at a time.

5. Report/Excel Test Split Agent
   - Split production-loss, cycle-report, and Excel-service tests into pure
     normalizer/calculation suites, DB-backed suites, and workbook-output suites.
   - Acceptance: pure logic tests run without app DB, IFS, or real workbooks.

6. Dependency/CI Agent
   - Move `pytest` out of runtime requirements if it is only needed for tests.
   - Keep `ruff`, `mypy`, and CI config aligned with the new test layout.
   - Remove obsolete `tests/.gitkeep` after test files exist in the directory.

Verification:

- `python -m pytest`
- `python -m ruff check .`
- Focused test commands for each split suite.

## Phase 2 - Repository Hygiene And Artifact Boundaries

Goal: separate source, generated outputs, private runtime data, and operational
evidence before moving reusable tools.

Files and directories needing attention:

- `outputs/**`
- `data/**`
- `logs/**`
- `runtime-logs/**`
- root `*.har`
- root `*.log`
- `local-certs/**`
- `phone-test/**`
- `docs/README.md`
- `docs/ENDPOINT_INVENTORY.md`
- `docs/IFS_QUICK_REPORT_AND_MACHINE_TIME_HANDOFF.md`
- `docs/app-development-syllabus.md`
- `.gitignore`
- `README.md`
- `.env.example`

Subagent work packages:

1. Output Classification Agent
   - Identify tracked files under `outputs/` that are generated data versus
     reusable scripts.
   - Preserve only sanitized fixtures needed by tests.
   - Move reusable scripts such as `outputs/ifs_inventory_join_export/fetch_ifs_join_data.py`
     and workbook builders into `scripts/ifs/` or `tools/reports/`.

2. Artifact Ignore Agent
   - Broaden `.gitignore` for regenerated output evidence, caches, local
     `node_modules`, HAR captures, logs, and report previews.
   - Do not delete live data or local certs.

3. Runtime Data Agent
   - Document how to move `data/process_entries.sqlite3`, workbook backups, and
     IFS experiment data to an external or `var/` location.
   - Keep `.gitkeep` scaffolding where the app expects default directories.

4. Ops Script Agent
   - Promote reusable scripts hidden in `runtime-logs/` to `scripts/ops/` with
     parameters.
   - Leave logs ignored and disposable.

5. Docs Taxonomy Agent
   - Split docs into current, research, archive, and optional personal-learning
     areas.
   - Mark generated snapshots such as `docs/ENDPOINT_INVENTORY.md` with
     provenance, or add a generator/check.

6. Config Docs Agent
   - Make `.env.example` the canonical setup list.
   - Update README so it does not drift from `.env.example`.
   - Remove local absolute HAR/output paths from docs and replace them with
     sanitized summaries.

Verification:

- `git status --short` should clearly show only intentional source/doc moves.
- `rg` should not find private absolute paths in current docs.
- Any promoted script has a CLI help path and a minimal dry-run test.

## Phase 3 - Core Model, Config, Request, And Database Boundaries

Goal: reduce central coupling before feature services are split.

Files needing attention:

- `app/models.py`
- `app/core/database.py`
- `app/core/config.py`
- `app/core/security.py`
- `app/domain/request_settings.py`
- `app/domain/request_values.py`
- `app/web/pages.py`
- `app/main.py`
- `app/features/bootstrap/api.py`
- `app/features/health/api.py`

Subagent work packages:

1. ORM Boundary Agent
   - Keep `app.models` as a compatibility facade.
   - Move shared models such as `Machine`, `MachineGroup`, `ProductionEngineer`,
     `utc_now`, and sync status constants into shared modules.
   - Move feature-owned ORM classes into their feature packages in small groups.
   - Preserve SQLAlchemy relationship resolution using string relationships or
     compatibility imports.

2. Migration/Seed Agent
   - Leave engine/session helpers, `Base`, commit helpers, and health checks in
     `app/core/database.py`.
   - Move hand-written migrations and seed functions into `core/migrations.py`
     plus feature migration modules.
   - Preserve the current `init_db` order until migration tests prove parity.

3. Settings Agent
   - Add grouped settings sections or sub-dataclasses for app, DB, process Excel,
     auxiliary systems, reports, IFS, labels, and production planning.
   - Keep compatibility properties on `Settings` until callers are moved.

4. Security/Request Agent
   - Move pure cookie/token crypto to a core module.
   - Move `LoginRequest`, auth dependencies, and HTTP exception mapping into
     `features/auth`.
   - Move request settings out of `app/domain` into `app/web/request_context.py`
     or `app/core/request_settings.py`.

5. Domain Validation Agent
   - Replace direct `HTTPException` raises in domain request parsing with domain
     validation errors.
   - Map those errors in API adapters.
   - Move sync status constants away from ORM model layout.

6. Web Assets Agent
   - Split `app/web/pages.py` into page route metadata, asset URLs/versioning,
     service-worker injection, and page rendering.
   - Keep constants re-exported for tests and `app/main.py` middleware until all
     imports are updated.

7. Bootstrap/Health Agent
   - Move cross-feature payload/probe assembly from route modules into
     `features/bootstrap/service.py` and `features/health/service.py`.
   - Keep routes thin.

Verification:

- `python -m pytest tests/test_database_model.py tests/test_auth.py tests/test_config.py`
- Existing imports from `app.models` still work until shims are removed.
- Startup creates/updates the same SQLite schema as before.

## Phase 4 - IFS And External Integration Boundary

Goal: split transport and feature workflows so IFS changes do not touch every
feature.

Files needing attention:

- `app/integrations/ifs/client.py`
- `app/features/ifs/api.py`
- `app/features/ifs_checks/service.py`
- `app/features/production_planning/service.py`
- `app/services/shop_order_source.py`
- `scripts/experiment_ifs_past_job_order_machine_product.py`
- `scripts/check_ifs_product_prefixes.py`

Subagent work packages:

1. IFS Transport Agent
   - Extract OAuth/token handling, HTTP retry, paging, and `_get_all` style
     helpers into `app/integrations/ifs/transport.py`.
   - Keep `client.py` facade exports for test compatibility.

2. OData/URL Agent
   - Extract OData quoting, key formatting, filters, projection URLs, and path
     builders into `app/integrations/ifs/odata.py`.
   - Preserve exact URL strings covered by tests.

3. Archive/Label Agent
   - Extract archive document reads, XML parsing, label report parsing, and label
     stock row normalization into focused modules.
   - Add tests around sanitized XML/JSON fixtures.

4. Inventory/Operations Agent
   - Extract stock/inventory client functions and shop-order/operation client
     functions into `inventory.py` and `operations.py`.
   - Move historical-operation helpers out of the experiment script into public
     integration APIs.

5. Feature Workflow Agent
   - Move package-label checklist, label-material availability, return-candidate
     orchestration, and production-loss query orchestration out of the raw IFS
     client and into feature services.

6. IFS API Agent
   - Split `app/features/ifs/api.py` serializers from route handlers.
   - Move planning-first-job and IFS-check composition into feature services.
   - Optionally split the router by stock, operations, checks, materials, and
     returns after serializers are stable.

7. Planning Workbook Agent
   - Split `production_planning/service.py` into models, workbook locator,
     XLSX streaming, visible-order parsing, and machine-row parsing.
   - Keep public wrapper functions stable for IFS and shift-manager callers.

8. IFS Checks Agent
   - Split `ifs_checks/service.py` into DTOs, operation keys, machine repository,
     missing-start checks, WhatsApp formatting, and planning-first-job status
     classification.

Verification:

- `python -m pytest tests/integrations/ifs tests/test_ifs_checks_service.py tests/test_production_planning.py`
- Exact OData URL tests remain green.
- No feature module imports private IFS helpers unless still behind a documented
  compatibility facade.

## Phase 5 - Excel, Workbook, And Sync Foundation

Goal: separate generic workbook IO from process/auxiliary workbook schemas and
make sync code easier to test.

Files needing attention:

- `app/services/excel_service.py`
- `app/services/workbook_utils.py`
- `app/services/excel_write_lock.py`
- `app/features/process_entries/workbook.py`
- `app/features/process_entries/sync.py`
- `app/features/process_entries/payloads.py`
- `app/features/process_entries/excel_import.py`
- `app/features/auxiliary_systems/domain.py`
- `app/features/auxiliary_systems/workbook.py`
- `app/features/auxiliary_systems/sync.py`
- `app/features/auxiliary_systems/api.py`

Subagent work packages:

1. Generic Workbook Agent
   - Keep generic workbook open/save/errors/backups in `app/services`.
   - Move process A:Y header schema and Turkish header validation into
     `features/process_entries`.
   - Keep compatibility exports until callers are migrated.

2. Workbook Utilities Agent
   - Split `workbook_utils.py` into cell helpers, header normalization, and
     backup file helpers.
   - Preserve re-exports during the transition.

3. Process Row Agent
   - Split process workbook row normalization/building from workbook IO and
     existing-row matching.
   - Keep append functions stable while row builder tests are added.

4. Process Sync Agent
   - Split process sync serializers, sync status queries, single append, and
     retry/bulk retry services.
   - Keep API response payloads unchanged.

5. Process Payload Agent
   - Split legacy payload detection, legacy field migration, temperature
     shorthand expansion, machine-section blanking, context merge, and required
     field validation.
   - Move engineer alias/display rules out of generic normalization.

6. Process Import Agent
   - Split Excel reader/parser from DB import persistence and deduplication.
   - Reuse the same row normalization as process workbook append.

7. Auxiliary Field Agent
   - Move auxiliary field names and row specs out of workbook layout into a
     shared `fields.py`.
   - Make domain and workbook code depend on field metadata, not each other.

8. Auxiliary Workbook Agent
   - Split auxiliary workbook code into fields, headers, row builder, IO,
     append service, style copy, and health check.

9. Auxiliary Sync/API Agent
   - Extract submission command service, serializers, and retry service.
   - Keep API routes as request/response adapters.

Verification:

- `python -m pytest tests/test_excel_service.py tests/test_auxiliary_systems_service.py tests/test_process_excel_import.py`
- Test workbook outputs match existing row values, sync status transitions, and
  backup behavior.

## Phase 6 - Feature API And Domain Service Splits

Goal: keep route handlers thin and move business workflows into command/query
services.

Files needing attention:

- `app/features/process_entries/api.py`
- `app/features/process_entries/service.py`
- `app/features/amount_control/api.py`
- `app/features/amount_control/domain.py`
- `app/features/amount_control/service.py`
- `app/features/breakdowns/api.py`
- `app/features/breakdowns/domain.py`
- `app/features/breakdowns/service.py`
- `app/features/shift_manager/api.py`
- `app/features/shift_manager/service.py`

Subagent work packages:

1. Process API Agent
   - Move create tour context, create entry, idempotency lookup, list queries,
     shift timing, and metadata application into command/query services.
   - Keep route handlers thin.

2. Shared Machine Validation Agent
   - Extract shared record date, shift, ISO datetime, stopped/resumed ordering,
     machine lookup, and idempotency helpers used by amount control and
     breakdowns.

3. Amount Control Agent
   - Move duplicate business-key checks, ORM construction, child breakdown
     construction, commits, and serialization into services.
   - Split bootstrap machine options from amount-control serializers.

4. Breakdowns Agent
   - Move create/list/detail workflows out of routes.
   - Split serializers from process-entry-derived context option queries.

5. Shift Manager Backend Agent
   - Stabilize the service payload contract.
   - Split IFS source, planning source, normalizers, matcher, payload shaping,
     and informed-state compatibility.

6. Shift Manager API Agent
   - Remove dynamic compatibility probing from routes after the service contract
     is stable.
   - Move notification repository/service, response coercion, and row-key join
     logic out of the API module.

Verification:

- `python -m pytest tests/test_api_routes.py tests/test_shift_manager_service.py tests/test_shift_manager_api.py`
- Route-level tests assert HTTP behavior; service tests assert business rules.

## Phase 7 - Reporting, Cycle Analysis, And Production Loss

Goal: isolate calculations, data sources, repositories, and workbook output for
large report workflows.

Files needing attention:

- `app/features/production_loss/service.py`
- `app/features/cycle_reports/service.py`
- `app/features/cycle_reports/seed.py`
- `cycle_time_analysis_work/analyze_cycle_times.py`
- `cycle_time_analysis_work/build_cycle_time_report.mjs`
- `worker_cycle_report/draft_20260624_104611/build_cycle_report.py`
- `scripts/forecast_cycle_times_from_process_entries.py`

Subagent work packages:

1. Shared Product/Cycle Domain Agent
   - Move `parse_part_description`, machine-group normalization, cycle/product
     parsing, statistics, and optimum-comparison logic into shared domain
     modules.
   - Update production loss, cycle reports, and scripts to import from the new
     public location.

2. Cycle Report Agent
   - Split cycle report DB row reads, IFS operation source, cycle-table loader,
     matcher, report row builder, and workbook writer.
   - Remove direct `asyncio.run` from pure matching paths where possible.

3. Cycle Seed Agent
   - Share cycle-table workbook row parsing between service and seed logic.
   - Isolate destructive seed persistence in a repository function.
   - Keep `seed_cycle_table_from_workbook` as a stable wrapper while database
     code is migrating.

4. Production Loss Normalizer Agent
   - Extract label-stock normalization, operation-history fallback,
     IFS-actual normalization, process metadata reads, and breakdown allocation.

5. Production Loss Calculation Agent
   - Extract loss math and warnings into pure functions with targeted tests.
   - Ensure workbook output is not written inside an uncommitted DB transaction
     path unless intentionally documented.

6. Production Loss Repository/Output Agent
   - Split DB persistence/cache reads from serialization and workbook writing.
   - Add focused tests for snapshot persistence and workbook output.

7. Cycle Analysis Script Agent
   - Promote reusable analysis logic from `cycle_time_analysis_work/analyze_cycle_times.py`
     into app modules or `tools/`.
   - Keep the script as a thin CLI.

8. Forecast Script Agent
   - Refactor `scripts/forecast_cycle_times_from_process_entries.py` onto the
     promoted IFS historical-operation helpers and shared cycle analysis logic.
   - Separate DB/IFS reads from forecast-rule functions and output writers.

9. Draft Report Agent
   - Decide whether `worker_cycle_report/draft_20260624_104611/build_cycle_report.py`
     is archived evidence or reusable code.
   - If reusable, move the code into shared cycle-analysis helpers; otherwise
     archive the full draft directory.

10. Node Report Builder Agent
   - Decide whether the `.mjs` workbook builder remains.
   - If yes, add CLI args, a package manifest/lockfile, and project-relative
     output paths.
   - If no, replace with the Python workbook stack.

Verification:

- `python -m pytest tests/test_cycle_report_service.py tests/test_cycle_time_analysis_comparison.py tests/test_production_loss_service.py`
- Generated workbook/report fixtures match current behavior where required.

## Phase 8 - Template Structure Before Frontend Split

Goal: clarify markup boundaries while preserving selectors and IDs used by JS
and tests.

Files needing attention:

- `app/templates/pages/reports.html`
- `app/templates/pages/login.html`
- `app/templates/pages/process.html`
- `app/templates/partials/main_header.html`
- `app/templates/partials/dashboard_section.html`
- `app/templates/partials/tour_context_section.html`
- `app/templates/partials/machine_entry_section.html`
- `app/templates/partials/auxiliary_systems_section.html`
- `app/templates/partials/amount_control_section.html`
- `app/templates/partials/entry_lists_sections.html`
- report action partials under `app/templates/partials/*section.html`

Subagent work packages:

1. Report Page Agent
   - Group `reports.html` into sync, production, IFS/check, and print-area
     subpartials.
   - Preserve all existing feature IDs and ordering.

2. Shell/Auth Agent
   - Introduce a shared base or auth shell so login does not duplicate the full
     HTML document/head structure.

3. Navigation Agent
   - Render nav and dashboard cards from page metadata instead of duplicating
     URLs/labels in templates and `app/web/pages.py`.
   - Split header navigation from live status pills.

4. Process Workflow Agent
   - Wrap tour context and machine entry into an explicit process-entry workflow
     partial.
   - Preserve `#tour-context-*` and `#entry-form` IDs.

5. Field Metadata Agent
   - Introduce field metadata/Jinja macros for process and auxiliary repeated
     input rows.
   - Keep submitted field names stable until backend schema migration is planned.

6. Amount Control Markup Agent
   - Render the three shift fieldsets from metadata/macros.
   - Decide whether missing dynamic breakdown hooks should be added or unused
     JS/CSS should be removed.

7. Generic Report Section Agent
   - Introduce a generic report action section macro/component.
   - Rename generic `ifs-results`/`ifs-summary` style concepts only after adding
     compatibility aliases.

Verification:

- Rendered page tests still find all existing IDs and controls.
- Service worker shell asset list still includes all required templates/assets.

## Phase 9 - Frontend JavaScript Split

Goal: split browser behavior by feature and make pure payload/model logic
testable.

Files needing attention:

- `app/static/js/modules/main-page.js`
- `app/static/js/modules/render.js`
- `app/static/js/modules/offline.js`
- `app/static/js/modules/shift-manager.js`
- `app/static/js/modules/bootstrap-options.js`
- `app/static/js/modules/shop-orders.js`
- `app/static/js/modules/payloads.js`
- `app/static/js/modules/amount-control.js`
- `app/static/js/modules/breakdowns.js`
- `app/static/js/modules/package-label-checklist.js`
- `app/static/js/modules/ifs-return.js`
- `app/static/js/modules/ifs-planning-first-job.js`
- `app/static/js/modules/label-material-availability.js`
- `app/static/js/modules/constants.js`
- `app/static/js/modules/utils.js`

Subagent work packages:

1. JS Test Agent
   - Add focused JS unit/DOM test capability if the project will keep splitting
     browser modules.
   - Start with pure payload, shop-order, offline queue, and renderer model tests.

2. Shop Order Adapter Agent
   - Unify shop-order normalization/product label logic from
     `bootstrap-options.js` and `shop-orders.js` into a pure adapter.
   - Keep process, amount-control, and breakdown flows using canonical option
     objects.

3. Payload Agent
   - Make payload builders deterministic by passing explicit form/state objects.
   - Remove direct dependence on `selectedShopOrderOption()` from
     `entryRequestBody`.

4. Renderer Model Agent
   - Move package-label counts/statuses, label-material data shaping, and
     response compatibility adapters out of `render.js`.
   - Keep render functions consuming normalized models.

5. Renderer Split Agent
   - Split `render.js` by feature: entry lists, auxiliary, amount control,
     breakdowns, package labels, label material availability, production loss,
     IFS return, and print areas.

6. Report Action Agent
   - Introduce a small `runReportAction` helper for repeated button/message/API/
     render/error behavior in IFS/report action modules.

7. Offline Agent
   - Split `offline.js` into IndexedDB repository, outbox sync engine,
     bootstrap cache, offline panel UI, and export helpers.
   - Inject UI callbacks into sync code.

8. Page Controller Agent
   - Split `main-page.js` into process, auxiliary, amount-control, breakdowns,
     reports, and bootstrap coordinator modules.

9. Shift Manager Frontend Agent
   - Split `shift-manager.js` into API/controller, model/adapters, renderer, and
     notification mutation modules.
   - Coordinate response names with backend Phase 6.

10. Amount/Breakdown Frontend Agent
   - Split amount-control payload builder from DOM controller and dynamic
     breakdown-row UI.
   - Split standalone breakdown form, context API, options, and payload builder.

11. Constants/Utils Agent
   - Split domain constants beside feature modules.
   - Split utilities into DOM, format, string, ID, and download helpers after
     larger modules are stable.

Verification:

- Existing page behavior works in browser smoke tests.
- JS unit tests cover pure model/payload/offline queue behavior.
- `tests/test_shared_request_page_utils.py` no longer relies only on brittle
  source substring checks.

## Phase 10 - CSS Split

Goal: split presentation after templates and JS selectors are stable.

Files needing attention:

- `app/static/css/app.css`
- template classes renamed during Phase 8

Subagent work packages:

1. CSS Layer Agent
   - Split the stylesheet into base tokens, shell/layout, forms, buttons,
     tables, reports, print, and feature-specific sections/files.
   - Preserve class names initially.

2. Print CSS Agent
   - Isolate package-label, IFS return, and report print styles.
   - Add print-focused smoke checks where feasible.

3. Responsive Layout Agent
   - Revisit nav grid assumptions after nav/card metadata is centralized.
   - Keep mobile layouts stable.

4. CSS Test Agent
   - Replace broad string assertions with selector/component smoke checks where
     possible.

Verification:

- Rendered pages do not lose expected styles.
- Print areas still render with intended selectors.
- Asset versioning and service worker shell URLs are updated intentionally.

## Phase 11 - Script, Ops, And Documentation Consolidation

Goal: make local tools reproducible and docs trustworthy after source
boundaries are stable.

Files needing attention:

- `scripts/experiment_ifs_past_job_order_machine_product.py`
- `scripts/forecast_cycle_times_from_process_entries.py`
- `scripts/export_entbus_hourly_electricity.ps1`
- `scripts/export_entbus_region_energy_hourly.ps1`
- `scripts/create_https_cert.ps1`
- `scripts/manual_acceptance_check.py`
- `scripts/check_ifs_product_prefixes.py`
- `cycle_time_analysis_work/*`
- `worker_cycle_report/*`
- `outputs/ifs_return_candidates_quick_report.sql`
- current docs under `docs/`

Subagent work packages:

1. IFS Experiment Promotion Agent
   - Promote operation-history fetch/normalize/dedupe/enrich logic from the
     experiment script to public integration modules.
   - Keep the old script as a thin CLI wrapper or archive it.

2. Forecast CLI Agent
   - Separate DB reads, IFS joins, forecast rules, JSON export, and workbook
     export in the forecast script.
   - Use public app modules only.

3. ENTBUS Agent
   - Extract duplicated PowerShell SOAP/date/decimal/output logic into a shared
     PowerShell module, or port both exporters to a common Python implementation.

4. HTTPS Cert Agent
   - Replace custom DER/PEM encoding with built-in .NET private-key export where
     feasible.
   - Split certificate generation from trust installation and keep README
     commands aligned.

5. Diagnostics Agent
   - Move one-off diagnostic/profiling scripts to `scripts/diagnostics` with
     explicit CLI args, or archive them with the analysis evidence.

6. Quick Report SQL Agent
   - Decide whether `outputs/ifs_return_candidates_quick_report.sql` is an
     operational template or a dated research artifact.
   - If operational, generate its planning-order input from current data instead
     of hard-coded dated rows.

7. Endpoint Docs Agent
   - Either archive `docs/ENDPOINT_INVENTORY.md` as a dated snapshot or add a
     generator/CI check against route definitions and frontend fetch usage.

8. Documentation Agent
   - Update README, docs index, IFS docs, backup/restore docs, and ops docs after
     the code/module moves are complete.

Verification:

- Promoted scripts have help text and do not depend on absolute local paths.
- Docs link checks pass.
- No current docs require raw HAR files or private local output paths.

## Files That Need No Direct Refactor Now

These files were reviewed and are acceptable as-is or only need incidental
import updates during related phases:

- `app/main.py`
- `app/core/paths.py`
- `app/domain/shifts.py`
- feature `__init__.py` files
- feature schema files unless tied to service extraction
- model re-export wrappers while compatibility facades are needed
- `app/services/excel_write_lock.py`
- `app/services/text_normalization.py`
- `app/static/js/app.js`
- `app/static/js/api.js`
- `app/static/js/modules/dates.js`
- `app/static/js/modules/login.js`
- `app/static/js/modules/lists.js`
- `app/static/js/modules/temperature.js`
- `app/static/js/modules/tour-context.js`
- `app/static/service-worker.js` after web asset boundaries are split
- `app/static/manifest.webmanifest`
- focused scripts such as `scripts/import_process_excel.py`,
  `scripts/start_https_server.ps1`, `scripts/check_ifs_product_prefixes.py`,
  and `scripts/manual_acceptance_check.py`

## Cross-Cutting Risks

1. Mojibake appears in several source constants and labels. Fixing it should be
   a deliberate encoding cleanup with tests, not mixed into behavior refactors.
2. The current worktree already has unrelated modified files. Future refactor
   branches should isolate one phase at a time.
3. Several tests monkeypatch private functions. Extract compatibility wrappers
   before moving those functions.
4. IFS/HAR/runtime data may contain private business or credential-adjacent
   information. Sanitize before turning any artifact into a fixture.
5. Frontend route/template IDs are heavily coupled to JS. Preserve IDs until the
   relevant JS controller split is complete.
6. Excel schemas are operational contracts. Keep submitted field names and Excel
   columns stable until a separate data migration is planned.

## Recommended Parallel Execution Model

Use up to six subagents per phase:

1. One integration owner coordinates the phase and owns compatibility facades.
2. Four domain agents perform disjoint file-scope extractions.
3. One verification agent updates or moves tests and runs focused checks.

For code-changing phases, every subagent should own a disjoint write scope. The
integration owner should merge only after focused tests pass for that scope.

## Completion Criteria

The refactor program is complete when:

1. No production module above 800 lines mixes unrelated IO, parsing, persistence,
   and rendering/calculation concerns.
2. Raw IFS transport/OData logic is not mixed with feature workflows.
3. Route handlers mainly validate/authenticate and call services.
4. Generic workbook services contain no process-specific schema rules.
5. Frontend page controllers, renderers, payload builders, and offline storage
   are separate.
6. `outputs/`, `data/`, logs, HAR files, local certs, and generated dependency
   trees are clearly ignored, archived, or promoted into source locations.
7. Test files are organized by feature/layer and do not depend on broad
   substring checks as primary coverage.
8. Full test and lint checks pass after compatibility shims are removed.
