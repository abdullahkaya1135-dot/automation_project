# Architecture

## Current Shape

The app is a FastAPI LAN MVP with SQLite-first persistence and Excel as a sync
target. The current structure is partly feature-oriented:

```text
app/
  config.py
  db/
  database.py
  domain/
  modules/
  routers/
  shared/
  static/
  templates/
  web/
```

## Request Flow

Routes should stay thin:

- Parse typed request schemas.
- Resolve request settings.
- Call module services for use cases.
- Serialize service results.

Services own persistence and sync behavior:

- `modules/tour_context/service.py` saves/replays tour contexts.
- `modules/process_entry/service.py` saves/replays process entries.
- `modules/auxiliary_systems/submission_service.py` saves/replays auxiliary
  submissions.
- `modules/sync/process_entry_sync.py` syncs pending process entries to Excel.
- `modules/auxiliary_systems/sync_service.py` syncs pending auxiliary
  submissions.
- Excel service modules own workbook shape, backup, row detection, and append
  behavior.

Domain modules own request normalization and field rules. They should not know
about FastAPI `Request` objects.

## Role Workspaces

Authentication code lives under `app/modules/auth/`. Role constants, PIN
parsing, and default workspace paths live in `roles.py`; signed session-cookie
mechanics live in `session.py`; `service.py` keeps the stable auth facade and
FastAPI dependency. Authentication is lightweight and PIN based.
`APP_ROLE_PINS` maps PINs to these MVP roles:

```text
operator: tour context, machine entry, phone sync
utility: auxiliary systems form and recent submissions
supervisor: pending/failed Excel sync, retry controls, recent records
planning: cycle report and IFS U1 return candidates
admin: all workspaces
```

`APP_PIN` remains supported as an admin fallback for older deployments.

Page templates are split by role:

```text
app/templates/pages/operator.html
app/templates/pages/utility.html
app/templates/pages/supervisor.html
app/templates/pages/planning.html
```

Frontend JavaScript is dispatched by `data-page` and page-specific modules under
`app/static/js/modules/pages/`.
The role workspace catalog lives in `app/web/workspaces.py`; it defines each
workspace's role, path, template, and navigation item. `app/web/permissions.py`
uses that catalog while focusing on session/role access checks.

Feature modules should stay purpose-sized. For example, shop-order UI behavior is
split under `app/static/js/modules/shop-orders/` into dropdown orchestration,
source status, machine-section visibility, normalization, state, and raw-material
prefill modules.

Backend feature slices are moving under `app/modules/`. Tour-context service and
repository code now live in `app/modules/tour_context/`. Process-entry service,
repository, and Excel mapper code now live in `app/modules/process_entry/`. The
older layer-first service/repository/adapter compatibility shims were removed;
tests and scripts should import purpose-based feature modules directly.
Process-entry serialization lives in `app/modules/sync/serializers.py`.
Process workbook file access, A:Y header validation, backup creation, and
reachability checks live in `app/modules/process_entry/workbook_io.py`.
Reusable-row scans live in `app/modules/process_entry/workbook_matching.py`.
Unlocked append/write/save mechanics live in
`app/modules/process_entry/workbook_append.py`; `workbook_service.py` keeps the
locked public facade.
Auxiliary submission save, retry/sync, and repository code now live in
`app/modules/auxiliary_systems/`. Auxiliary field constants live in
`fields.py`, the 15-row workbook payload mapper lives in `row_builder.py`, and
file access, header validation, backup creation, and row-format copying live in
`workbook_io.py`. `workbook_matching.py` owns reusable-block scans,
`workbook_append.py` owns append and block writing, `workbook_types.py` holds
workbook submission/result dataclasses, and `workbook_service.py` keeps the
locked public facade.
Auxiliary submission API serialization lives in `serializers.py`, sync result
state transitions and retry summaries live in `sync_results.py`, and
`sync_service.py` coordinates Excel append attempts and retry selection.
Production planning workbook resolution and lightweight reader code now live in
`app/modules/production_planning/`. Workbook candidate resolution lives in
`resolver.py`, XML spreadsheet mechanics live in `spreadsheet_xml.py`, order
dataclasses live in `types.py`, and `reader.py` extracts visible planning order
tokens from column A.
IFS planning/material integration lives in `app/modules/ifs/`: OData path
construction, HTTP pagination, stock, operations, materials, and return-candidate
comparison are split by responsibility. Material row normalization and
deduplication live in `material_rows.py`, bounded async fan-out lives in
`concurrency.py`, and `materials.py` coordinates the HM-02 material fetch
workflows.
Cycle report generation now lives in `app/modules/reports/`: source workbook,
cycle-table, and IFS reads are in `cycle_sources.py`; matching/report-row
assembly is in `cycle_builder.py`; output workbook formatting is in
`cycle_writer.py`; `cycle_report_service.py` orchestrates the use case and keeps
stable exports.
Shop-order source shaping now lives in `app/modules/shop_orders/`.
Offline bulk-sync code now lives in `app/modules/offline/`, keeping the router
as a thin HTTP adapter. `envelope.py` normalizes phone outbox envelopes,
`dependencies.py` resolves entry dependencies on tour contexts, `records.py`
saves phone outbox records to SQLite, `excel_sync.py` batches process and
auxiliary Excel writes after the SQLite commit, `response.py` serializes
per-record outbox results, and `service.py` orchestrates the use case.
SQLite engine/session setup remains in `app/database.py`; startup schema
migrations and legacy table/column cleanup live in `app/db/migrations.py`.
Frontend offline outbox code mirrors that split under
`app/static/js/modules/offline/`: `outbox-records.js` owns IndexedDB record
state transitions, `outbox-upload.js` owns the bulk-sync request and server
result application, `outbox-results.js` owns UI hydration from server results,
and `outbox-sync.js` remains the orchestration entrypoint.

CSS follows the same shape. Templates load `app/static/css/app.css` as the stable
entrypoint, and that file imports tokens, base, layout, component, page, print,
and responsive styles. When adding a CSS import, also add it to the service-worker
shell cache.

## Field Definitions

The backend owns process-entry and auxiliary payload field lists. `/api/bootstrap`
includes `field_definitions`, and `/api/field-definitions` exposes the same
payload for direct checks. Frontend payload builders hydrate their field lists
from this bootstrap data, so Python domain constants remain the source of truth
for process entry schema version, temperature-repeat fields, auxiliary
measurement fields, and auxiliary checkbox fields.

## Remaining Cleanup Direction

The long-term target is a feature-first backend:

```text
app/modules/
  auth/
  tour_context/
  process_entry/
  auxiliary_systems/
  sync/
  ifs/
  production_planning/
  reports/
```

Move in small slices. Keep compatibility imports where needed, keep tests green,
delete stale compatibility shims once references are moved to feature modules,
and avoid mixing behavior changes with large file moves.
