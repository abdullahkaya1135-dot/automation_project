# Endpoint Inventory

Generated from a read-only audit of backend route files, frontend fetch usage, and
tests. Routes are registered centrally in `app/main.py`.

## Shared Behavior

- Protected API routes use the signed `process_session` cookie set by
  `POST /api/login`.
- The frontend fetch wrapper is `app/static/js/api.js::apiJson`, which sends
  `credentials: "same-origin"`, parses JSON, and redirects `401` to `/login`.
- Protected APIs return `401 {"detail": "Oturum acmaniz gerekiyor."}` when the
  session is missing or invalid.
- Most create endpoints are idempotent through `client_request_id`: first
  request returns `201`, replay returns `200` and `idempotent_replay: true`.
- IFS upstream errors map to `502`; IFS configuration/planning errors map to
  `503`.
- Shift Manager derives the remaining package/pallet count from IFS
  `RemainingQty / InventoryPartRef.Cf_Palet_Ici_Miktar`; `RemainingQty` itself
  is the remaining piece quantity.

## Classification

### Used By The Browser App

- `POST /api/login`
- `GET /api/bootstrap`
- `POST /api/tour-context`
- `POST /api/entries`
- `GET /api/entries`
- `POST /api/sync/retry`
- `POST /api/auxiliary-systems/submissions`
- `GET /api/auxiliary-systems/submissions`
- `POST /api/auxiliary-systems/sync/retry`
- `POST /api/amount-control/shifts`
- `GET /api/amount-control/shifts`
- `POST /api/breakdowns`
- `GET /api/breakdowns`
- `POST /api/cycle-report/today`
- `POST /api/production-loss-reports`
- `GET /api/ifs/package-label-checklist`
- `GET /api/ifs/missing-production-starts`
- `GET /api/ifs/whatsapp-status-message`
- `GET /api/ifs/u1-return-candidates`
- `GET /api/shift-manager/near-complete`
- `PUT /api/shift-manager/notifications`
- page/static/PWA routes

### API-Only Or Diagnostic Today

- `GET /health`
- `GET /api/amount-control/shifts/{shift_id}`
- `GET /api/breakdowns/{breakdown_id}`
- `GET /api/production-loss-reports`
- `GET /api/production-loss-reports/{report_id}`
- `GET /api/ifs/u1-hm02-stock`
- `GET /api/ifs/pet-ongoing-operations`
- `GET /api/ifs/used-hm02-materials`

### Shift Manager

These endpoints support the reports-page Shift Manager handoff check.

- `GET /api/shift-manager/near-complete`
- `PUT /api/shift-manager/notifications`

### Likely Stale Or Reserved

- `GET /api/tour-context/defaults`: `GET /api/bootstrap` already returns
  `current_tour_timing`, and no current frontend/tests/scripts call this route.
- `docs/app-development-syllabus.md` references `POST /api/package-label/check`,
  but no such route exists; the live route is
  `GET /api/ifs/package-label-checklist`.

## Auth And Bootstrap

### `POST /api/login`

- Handler: `app/features/auth/api.py::api_login`
- Auth: public
- Used by: `app/static/js/modules/login.js`, tests, manual acceptance script
- Related: sets cookie needed by all protected API/page routes

Request:

```json
{"pin": "1234"}
```

Success response:

```json
{"ok": true}
```

Failure response:

```json
{"detail": "PIN gecersiz."}
```

Notes:

- Success sets `process_session` cookie.
- There is no logout endpoint.

### `GET /api/bootstrap`

- Handler: `app/features/bootstrap/api.py::bootstrap`
- Auth: required
- Used by: app startup, all main pages, IndexedDB bootstrap cache, service worker
  network-first cache
- Related: supplies data used by process entry, auxiliary, amount-control,
  breakdown, and reports pages

Request: no body or query.

Representative response:

```json
{
  "excel": {"available": true, "database_backed": true, "last_error": null},
  "auxiliary_systems": {
    "form_available": true,
    "target_available": true,
    "form_error": null,
    "target_error": null
  },
  "shop_order_source": {
    "available": true,
    "source": "ifs-token",
    "last_error": null,
    "operation_count": 2,
    "order_count": 2,
    "resource_count": 2,
    "options": [
      {
        "order_no": "WO-1",
        "resource_id": "101",
        "release_no": "*",
        "sequence_no": "*",
        "operation_no": 10,
        "part_no": "MM-PET0001",
        "part_description": "Bottle 28MM 6GR"
      }
    ]
  },
  "current_tour_timing": {
    "date": "08.06.2026",
    "shift": "08.00-16.00",
    "timezone": "Europe/Istanbul",
    "generated_at": "2026-06-08T09:15:00+03:00"
  },
  "current_auxiliary_date": "08.06.2026",
  "machines": [
    {"id": 1, "machine_code": "101", "hall_number": 1, "hall_name": "Hall 1", "display_order": 1}
  ],
  "production_engineers": [
    {"id": 1, "full_name": "Baris Cetik", "display_order": 1}
  ],
  "latest_tour_context": null,
  "last_sync_error": null,
  "last_auxiliary_sync_error": null
}
```

Notes:

- If IFS shop-order loading fails, response still returns `200`; only
  `shop_order_source.available` becomes `false`.
- `excel.available` is currently always true because process data is database
  backed.

### `GET /api/tour-context/defaults`

- Handler: `app/features/bootstrap/api.py::tour_context_defaults`
- Auth: required
- Used by: no current browser/test/script caller found
- Related: overlaps with `/api/bootstrap.current_tour_timing`

Request: no body or query.

Response:

```json
{
  "date": "26.06.2026",
  "shift": "08.00-16.00",
  "timezone": "Europe/Istanbul",
  "generated_at": "2026-06-26T11:30:00+03:00"
}
```

Notes:

- Likely stale or reserved for future direct timing refresh.

### `GET /health`

- Handler: `app/features/health/api.py::health`
- Auth: public
- Used by: tests, README/manual checks; not browser UI
- Related: overlaps with bootstrap for SQLite/auxiliary/sync health

Request: no body or query.

Response:

```json
{
  "status": "ok",
  "sqlite": {"ok": true, "error": ""},
  "process_data": {"ok": true, "database_backed": true, "error": null},
  "auxiliary_systems": {
    "form_ok": true,
    "target_ok": true,
    "form_error": null,
    "target_error": null
  },
  "excel_write_lock": {
    "locked": false,
    "waiting": 0,
    "active_operation": null,
    "total_acquired": 0
  },
  "last_sync_error": null,
  "last_auxiliary_sync_error": null
}
```

Notes:

- Does not check IFS availability.
- `status` is `ok` only when SQLite and auxiliary target are OK.

## Process Entry Endpoints

### `POST /api/tour-context`

- Handler: `app/features/process_entries/api.py::create_tour_context`
- Auth: required
- Used by: process page offline outbox, `tour-context.js`, tests
- Related: `/api/bootstrap` returns `latest_tour_context`

Request:

```json
{
  "client_request_id": "tour-client-request-1",
  "client_recorded_at": "2026-06-08T15:55:00+03:00",
  "ambient_temp": "24,5",
  "production_engineer": "Baris Cetik",
  "shift_chief": "Selman"
}
```

Response:

```json
{
  "id": 12,
  "tour_context": {
    "id": 12,
    "client_request_id": "tour-client-request-1",
    "client_recorded_at": "2026-06-08T12:55:00Z",
    "date": "08.06.2026",
    "ambient_temp": "24,5",
    "production_engineer": "Baris Cetik",
    "shift_chief": "Selman",
    "shift": "08.00-16.00",
    "created_at": "2026-06-08T12:55:01Z",
    "updated_at": "2026-06-08T12:55:01Z"
  }
}
```

Notes:

- `ambient_temp`, `production_engineer`, and `shift_chief` are required.
- `date` and `shift` are accepted but effectively client hints; server
  recomputes them from `client_recorded_at` or request time.
- Unknown shift chief returns `422`.

### `POST /api/entries`

- Handler: `app/features/process_entries/api.py::create_entry`
- Auth: required
- Used by: process page offline outbox
- Related: created rows are later listed by `GET /api/entries` and synced by
  `POST /api/sync/retry`

Request:

```json
{
  "tour_context_id": 12,
  "payload_schema_version": 2,
  "payload": {
    "col_f": "101",
    "col_g": "Product 101",
    "col_h": "WO-1",
    "col_j": "16",
    "col_k": "12",
    "col_l": "12,5",
    "col_x": "270x3,276x2,275"
  },
  "status": "ok",
  "client_request_id": "entry-client-request-1",
  "client_recorded_at": "2026-06-08T09:20:00+03:00"
}
```

Response:

```json
{
  "saved_locally": true,
  "saved_to_database": true,
  "synced_to_excel": false,
  "entry": {
    "id": 34,
    "client_request_id": "entry-client-request-1",
    "tour_context_id": 12,
    "payload": {
      "col_f": "101",
      "col_h": "WO-1",
      "col_l": "12,5",
      "col_x": "270-270-270-276-276-275"
    },
    "process_date": "2026-06-08",
    "machine_code": "101",
    "sync_status": "pending_excel",
    "excel_row_number": null,
    "last_error": null
  }
}
```

Notes:

- `tour_context_id`, machine `col_f`, and work order `col_h` are required.
- Temperature shorthand is expanded by both browser and server.
- POST only saves to DB and queues Excel sync; Excel write is done by
  `/api/sync/retry`.

### `GET /api/entries`

- Handler: `app/features/process_entries/api.py::list_entries`
- Auth: required
- Used by: reports page recent/pending lists and Excel pending count

Query:

- `sync_status=synced|pending_excel|failed_excel`
- `limit`, default `50`, max `200`
- `sort=process|recent`, default `process`

Example:

```json
GET /api/entries?sync_status=pending_excel&limit=50
```

Response:

```json
{
  "entries": [
    {
      "id": 34,
      "payload": {"col_f": "101", "col_h": "WO-1", "col_j": "16", "col_k": "12", "col_l": "12,5"},
      "process_date": "2026-06-08",
      "machine_code": "101",
      "sync_status": "pending_excel",
      "excel_row_number": null,
      "last_error": null,
      "submitted_at": "2026-06-08T06:20:00Z"
    }
  ]
}
```

### `POST /api/sync/retry`

- Handler: `app/features/process_entries/api.py::retry_sync`
- Auth: required
- Used by: reports page "Excel'e aktar" button

Request:

```json
POST /api/sync/retry?process_date=2026-06-08
```

Response:

```json
{
  "attempted": 2,
  "synced": 2,
  "failed": 0,
  "remaining": 0,
  "stopped_on_error": false,
  "results": [
    {"entry_id": 34, "success": true, "sync_status": "synced", "excel_row_number": 2, "last_error": null}
  ],
  "process_date": "2026-06-08",
  "database_backed": true
}
```

Notes:

- `process_date` is optional in backend but required by current UI.
- Offline outbox auto-flush currently retries auxiliary Excel sync only; process
  Excel sync remains a reports-page action.

## Auxiliary Systems

### `POST /api/auxiliary-systems/submissions`

- Handler: `app/features/auxiliary_systems/api.py::create_auxiliary_systems_submission`
- Auth: required
- Used by: auxiliary page offline outbox

Request:

```json
{
  "recorded_date": "2026-06-08",
  "client_request_id": "aux-1",
  "client_recorded_at": "2026-06-08T09:25:00+03:00",
  "payload": {
    "tower_frequency": "50",
    "tower_set_pressure": "3,6",
    "oil_cooling_water_tank_checked": true
  }
}
```

Response:

```json
{
  "saved_locally": true,
  "synced_to_excel": true,
  "submission": {
    "id": 1,
    "client_request_id": "aux-1",
    "recorded_date": "08.06.2026",
    "payload": {"tower_frequency": "50", "tower_set_pressure": "3,6"},
    "sync_status": "synced",
    "excel_start_row": 2,
    "excel_end_row": 16,
    "last_error": null
  }
}
```

Notes:

- Browser requires at least one measurement field. Server accepts the payload
  even if only checkboxes are present.

### `GET /api/auxiliary-systems/submissions`

- Handler: `app/features/auxiliary_systems/api.py::list_auxiliary_systems_submissions`
- Auth: required
- Used by: auxiliary page list and Excel pending count

Query:

- `sync_status=synced|pending_excel|failed_excel`
- `limit`, default `50`, max `200`

Response:

```json
{"submissions": [{"id": 1, "recorded_date": "08.06.2026", "sync_status": "synced"}]}
```

### `POST /api/auxiliary-systems/sync/retry`

- Handler: `app/features/auxiliary_systems/api.py::retry_auxiliary_systems_sync`
- Auth: required
- Used by: auxiliary retry button and offline outbox flush

Request: no body or query.

Response:

```json
{
  "attempted": 1,
  "synced": 1,
  "failed": 0,
  "remaining": 0,
  "stopped_on_error": false,
  "results": [
    {"submission_id": 1, "success": true, "sync_status": "synced", "excel_start_row": 2, "excel_end_row": 16, "last_error": null}
  ]
}
```

## Amount Control

### `POST /api/amount-control/shifts`

- Handler: `app/features/amount_control/api.py::create_amount_control_shift`
- Auth: required
- Used by: amount-control page offline outbox

Request:

```json
{
  "record_date": "2026-06-08",
  "machine_code": "101",
  "job_order": "WO-1",
  "shift": "08.00-16.00",
  "worker_names": "Operator One, Operator Two",
  "produced_quantity": 1200,
  "breakdowns": [
    {"produced_product": "Product 101", "stop_reason": "Mold change", "duration_minutes": 30}
  ],
  "client_request_id": "amount-1"
}
```

Response:

```json
{
  "id": 1,
  "saved_locally": true,
  "shift": {
    "id": 1,
    "record_date": "2026-06-08",
    "machine_code": "101",
    "job_order": "WO-1",
    "shift": "08.00-16.00",
    "worker_names": "Operator One, Operator Two",
    "produced_quantity": 1200,
    "breakdowns": [
      {"id": 2, "machine_code": "101", "amount_control_shift_id": 1, "stop_reason": "Mold change", "duration_minutes": 30}
    ]
  },
  "idempotent_replay": false
}
```

Notes:

- Browser currently builds three requests, one per shift.
- Duplicate `(record_date, machine, job_order, shift)` returns `409`.
- Unknown machine or invalid payload returns `422`.
- JS supports nested breakdown rows, but the current template does not expose
  add-breakdown controls, so visible UI submits `breakdowns: []`.

### `GET /api/amount-control/shifts`

- Handler: `app/features/amount_control/api.py::list_amount_control_shifts`
- Auth: required
- Used by: amount-control history list

Example:

```json
GET /api/amount-control/shifts?record_date=2026-06-08&machine_code=101&job_order=WO-1
```

Response:

```json
{"shifts": [{"id": 1, "machine_code": "101", "job_order": "WO-1", "shift": "08.00-16.00"}]}
```

### `GET /api/amount-control/shifts/{shift_id}`

- Handler: `app/features/amount_control/api.py::get_amount_control_shift`
- Auth: required
- Used by: tests only, no current browser caller

Response:

```json
{"id": 1, "machine_code": "101", "job_order": "WO-1", "breakdowns": []}
```

Missing ID returns `404`.

## Breakdowns

### `POST /api/breakdowns`

- Handler: `app/features/breakdowns/api.py::create_breakdown`
- Auth: required
- Used by: breakdown page offline outbox

Request:

```json
{
  "record_date": "2026-06-08",
  "machine_code": "101",
  "shift": "00.00-08.00",
  "reason": "Hydraulic pressure fault",
  "duration_minutes": 45,
  "job_order": "WO-1",
  "produced_product": "Product 101",
  "client_request_id": "breakdown-1"
}
```

Response:

```json
{
  "id": 1,
  "saved_locally": true,
  "breakdown": {
    "id": 1,
    "record_date": "2026-06-08",
    "machine_code": "101",
    "job_order": "WO-1",
    "shift": "24.00-08.00",
    "produced_product": "Product 101",
    "reason": "Hydraulic pressure fault",
    "stop_reason": "Hydraulic pressure fault",
    "duration_minutes": 45
  },
  "idempotent_replay": false
}
```

Notes:

- UI sends `00.00-08.00`; backend normalizes to `24.00-08.00`.
- API accepts `stopped_at` and `resumed_at`; current template does not submit
  them.

### `GET /api/breakdowns`

- Handler: `app/features/breakdowns/api.py::list_breakdowns`
- Auth: required
- Used by: breakdown history list

Example:

```json
GET /api/breakdowns?record_date=2026-06-08&machine_code=101&shift=00:00-08:00&job_order=WO-1
```

Response:

```json
{"breakdowns": [{"id": 1, "machine_code": "101", "reason": "Hydraulic pressure fault"}]}
```

Notes:

- Frontend list code still has an `items` fallback, but backend returns
  `breakdowns`.

### `GET /api/breakdowns/{breakdown_id}`

- Handler: `app/features/breakdowns/api.py::get_breakdown`
- Auth: required
- Used by: tests only, no current browser caller

Missing ID returns `404`.

## Reports

### `POST /api/cycle-report/today`

- Handler: `app/features/cycle_reports/api.py::create_today_cycle_report`
- Auth: required
- Used by: reports page cycle-report button

Request: no body or query. Report date is server "today" in configured timezone.

Response:

```json
{
  "output_path": "C:\\tmp\\reports\\08.06.2026 Cycle Report.xlsx",
  "row_count": 1,
  "matched_count": 1,
  "warning_count": 0,
  "date": "2026-06-08"
}
```

Notes:

- Returns `404` when no rows exist for today.
- Returns `422` for cycle report generation errors.
- No API exists to request a non-today cycle report.

### `POST /api/production-loss-reports`

- Handler: `app/features/production_loss/api.py::create_report`
- Auth: required
- Used by: reports page production-loss form

Request:

```json
{
  "date_from": "2026-06-08",
  "date_to": "2026-06-08",
  "refresh_ifs": true,
  "refresh_labels": true
}
```

Response:

```json
{
  "id": 1,
  "date_from": "2026-06-08",
  "date_to": "2026-06-08",
  "output_path": "C:\\tmp\\reports\\2026-06-08_2026-06-08 Production Loss 1.xlsx",
  "row_count": 1,
  "warning_count": 1,
  "generated_at": "2026-06-08T12:00:00Z",
  "source_summary": {
    "quantity_source": "ifs-operation-history",
    "ifs_refreshed": true,
    "ifs_error": null,
    "ifs_actual_count": 2,
    "realized_cycle_valid_count": 1,
    "realized_cycle_skipped_count": 1
  },
  "rows": [
    {
      "id": 1,
      "record_date": "2026-06-08",
      "machine_code": "101",
      "job_order": "WO-1",
      "product_description": "PET 28MM 6GR",
      "daily_total_quantity": 100,
      "cycle_time_seconds": "15",
      "net_machine_minutes": "60",
      "production_loss_net": "140",
      "production_loss_gross": "140"
    }
  ]
}
```

Notes:

- `refresh_labels` is in the API schema, but UI always sends `true`.
- `refresh_ifs` is user-controlled by the UI checkbox.
- POST creates a persisted DB snapshot and XLSX.

### `GET /api/production-loss-reports`

- Handler: `app/features/production_loss/api.py::list_reports`
- Auth: required
- Used by: tests only, no current browser caller

Query:

- `limit`, default `20`, min `1`, max `100`

Response:

```json
{"reports": [{"id": 1, "date_from": "2026-06-08", "date_to": "2026-06-08", "row_count": 1, "warning_count": 1}]}
```

### `GET /api/production-loss-reports/{report_id}`

- Handler: `app/features/production_loss/api.py::get_report`
- Auth: required
- Used by: tests only, no current browser caller

Response shape: same summary fields as list, plus `rows`. Missing ID returns:

```json
{"detail": "Production loss report not found."}
```

## IFS Endpoints

### `GET /api/ifs/u1-hm02-stock`

- Handler: `app/features/ifs/api.py::ifs_u1_hm02_stock`
- Auth: required
- Used by: tests only, no current browser caller
- Related: underlying client function is reused by return-candidate logic

Response:

```json
{
  "stock_count": 1,
  "stock": [
    {
      "contract": "S01",
      "part_no": "HM-02-A",
      "material_name": "Raw Material",
      "location_no": "U1",
      "lot_batch_no": "L1",
      "available_qty": 12.5,
      "qty_onhand": 15,
      "uom": "kg",
      "obj_id": "obj-1",
      "handling_unit_id": null
    }
  ]
}
```

### `GET /api/ifs/package-label-checklist`

- Handler: `app/features/ifs/api.py::ifs_package_label_checklist`
- Auth: required
- Used by: reports page package-label checklist widget

Response:

```json
{
  "summary": {
    "generated_at": "2026-06-24T08:00:00+03:00",
    "stock_count": 1,
    "row_count": 1,
    "job_order_count": 1,
    "operation_count": 1,
    "matched_count": 1,
    "match_status_counts": {"matched": 1}
  },
  "rows": [
    {
      "part_no": "MM-CAP001",
      "part_description": "Cap 1",
      "location_no": "U0101",
      "handling_unit_id": "HU-1",
      "job_order": "2579",
      "machine_code": "M-10",
      "operation_match_status": "matched",
      "archive_label_match_status": "matched_by_package_id",
      "operation_match_count": 1
    }
  ]
}
```

Notes:

- Current docs route list omits this live endpoint.
- Renderer supports some older label status fields that current rows may not
  emit.

### `GET /api/ifs/pet-ongoing-operations`

- Handler: `app/features/ifs/api.py::ifs_pet_ongoing_operations`
- Auth: required
- Used by: tests only, no current browser caller
- Related: same underlying fetch is used by bootstrap, cycle report, WhatsApp,
  and missing-production flows

Response:

```json
{
  "operation_count": 1,
  "operations": [
    {
      "order_no": "2615",
      "release_no": "*",
      "sequence_no": "*",
      "operation_no": 10,
      "contract": "S01",
      "work_center_no": "SP25",
      "part_no": "MM-PET0048",
      "part_description": "Bottle",
      "preferred_resource_id": "135",
      "operation_description": "Run",
      "remaining_qty": 42
    }
  ]
}
```

### `GET /api/shift-manager/near-complete`

- Handler: `app/features/shift_manager/api.py::near_complete_orders`
- Auth: required
- Used by: reports page Shift Manager widget
- Related: reads active PET operations from IFS and the latest production
  planning workbook to identify the next planned job for the same machine

Query:

- `threshold`, default `3`, min `0`, max `1000`

Request: no body. The primary inputs are IFS active operations and the configured
production planning workbook.

Representative response:

```json
{
  "summary": {
    "generated_at": "2026-06-27T22:30:00+03:00",
    "threshold": 3,
    "active_operation_count": 1,
    "active_machine_count": 1,
    "near_complete_count": 1,
    "next_job_found_count": 1,
    "missing_plan_count": 0,
    "planning_source_name": "27.06.2026 CIZELGE 1.xlsx",
    "row_count": 1,
    "informed_count": 0,
    "uninformed_count": 1
  },
  "rows": [
    {
      "machine_code": "135",
      "current_order_no": "SO-LOW",
      "current_product_no": "MM-PET-SO-LOW",
      "current_product_description": "Product SO-LOW",
      "remaining_quantity": 200,
      "package_pallet_size": 100,
      "remaining_packages": 2,
      "remaining_package_pallet_count": 2,
      "next_order_no": "SO-NEXT",
      "next_product_no": "MM-PET-SO-NEXT",
      "next_mold": "Mold A",
      "planning_sheet_name": "Plan",
      "planning_row_number": 12,
      "planning_match_found": true,
      "status": "next_found",
      "informed": false,
      "informed_at": null,
      "notification_id": null
    }
  ]
}
```

Notes:

- `remaining_quantity` is the raw IFS `RemainingQty` piece quantity.
- `package_pallet_size` is `InventoryPartRef.Cf_Palet_Ici_Miktar` from
  `ShopFloorWorkbenchHandling.GetOperations`.
- `remaining_packages` / `remaining_package_pallet_count` is calculated as
  `remaining_quantity / package_pallet_size`.
- A row becomes actionable when the calculated package/pallet count is
  `<= threshold`.
- IFS resource `PKT` is excluded before summary counts and row generation.
- The current order is matched against visible production planning rows; the
  next visible order for the same machine is returned as the next job.
- If the current order is missing from the plan, return the current operation
  with a warning/status and no `next_order_no`.
- If the current order is the last visible order for the machine, return the
  current operation with a no-next-job status and no `next_order_no`.
- Persisted informed state from the notification upsert is applied on every
  fetch so the UI checkbox survives refreshes.

### `PUT /api/shift-manager/notifications`

- Handler: `app/features/shift_manager/api.py::upsert_notification`
- Auth: required
- Used by: reports page Shift Manager checkbox
- Related: `GET /api/shift-manager/near-complete` applies the persisted state

Request:

```json
{
  "machine_code": "135",
  "current_order_no": "SO-LOW",
  "next_order_no": "SO-NEXT",
  "informed": true
}
```

Response:

```json
{
  "notification": {
    "machine_code": "135",
    "current_order_no": "SO-LOW",
    "next_order_no": "SO-NEXT",
    "informed": true,
    "informed_at": "2026-06-27T19:30:00Z"
  }
}
```

Notes:

- Upsert key should include at least machine, current order, and next order so a
  repeated checkbox submit updates the same notification row.
- Rows without a next job currently cannot be acknowledged because
  `next_order_no` is required by the API schema.

### `GET /api/ifs/missing-production-starts`

- Handler: `app/features/ifs/api.py::ifs_missing_production_starts`
- Auth: required
- Used by: reports page IFS start-check widget

Request:

```json
GET /api/ifs/missing-production-starts?process_date=2026-06-08
```

Response:

```json
{
  "process_date": "2026-06-08",
  "hall_numbers": [1, 2, 3, 4],
  "working_machine_count": 3,
  "active_ifs_machine_count": 2,
  "active_ifs_combination_count": 3,
  "process_combination_count": 3,
  "missing_count": 1,
  "machines": [
    {
      "machine_code": "302",
      "hall_number": 3,
      "hall_name": "Hall 3",
      "latest_work_order": "WO-MISSING",
      "latest_product": "Product Missing",
      "latest_cycle_time": null,
      "latest_submitted_at": null,
      "entry_count": 0
    }
  ]
}
```

### `GET /api/ifs/whatsapp-status-message`

- Handler: `app/features/ifs/api.py::ifs_whatsapp_status_message`
- Auth: required
- Used by: reports page WhatsApp message widget

Response:

```json
{
  "hall_numbers": [1, 2, 3, 4],
  "active_ifs_machine_count": 3,
  "machine_count": 47,
  "halls": [
    {
      "hall_number": 1,
      "hall_name": "Hall 1",
      "machines": [
        {"machine_code": "101", "hall_number": 1, "hall_name": "Hall 1", "is_active": true, "status": "Uretim"}
      ]
    }
  ],
  "message": "Salon 1\n101 Uretim\n..."
}
```

### `GET /api/ifs/used-hm02-materials`

- Handler: `app/features/ifs/api.py::ifs_used_hm02_materials`
- Auth: required
- Used by: tests only, no current browser caller

Response:

```json
{
  "operation_count": 2,
  "used_material_count": 2,
  "used_part_count": 1,
  "used_parts": ["HM-02-01-01-525"],
  "used_hm02_part_count": 1,
  "used_hm02_parts": ["HM-02-01-01-525"],
  "used_materials": [
    {
      "order_no": "2615",
      "operation_no": 10,
      "part_no": "HM-02-01-01-525",
      "issue_to_location": "U1",
      "qty_required": 25.578,
      "qty_available": 100.72,
      "print_unit": "kg",
      "produced_part_no": "MM-PET0048",
      "machine": "135"
    }
  ]
}
```

### `GET /api/ifs/u1-return-candidates`

- Handler: `app/features/ifs/api.py::ifs_u1_return_candidates`
- Auth: required
- Used by: reports page IFS return-candidates widget

Response:

```json
{
  "generated_at": "2026-06-10T14:30:00+03:00",
  "planning_source_name": "plan.xlsx",
  "stock_count": 3,
  "operation_count": 1,
  "active_used_material_count": 1,
  "planning_order_count": 1,
  "planning_operation_count": 1,
  "stopped_operation_count": 1,
  "used_material_count": 3,
  "used_part_count": 3,
  "return_candidate_count": 1,
  "return_candidates": [
    {
      "contract": "S01",
      "part_no": "HM-04-C",
      "material_name": "Candidate Material",
      "location_no": "U1",
      "lot_batch_no": "L1",
      "available_qty": 12.5,
      "qty_onhand": 15,
      "uom": "kg"
    }
  ],
  "used_parts": ["HM-02-A", "HM-03-B", "HM-03-DURAN"],
  "used_materials": [
    {"order_no": "2615", "part_no": "HM-02-A", "machine": "135"}
  ]
}
```

Notes:

- Depends on production planning workbook settings; planning errors can return
  `503`.
- Route intentionally strips `obj_id` from returned candidate rows.

## Page And Static Routes

### Protected Pages

All use `app/web/pages.py::protected_page`. Valid cookie returns HTML; missing
cookie redirects `303` to `/login`. Middleware marks protected pages
`Cache-Control: no-store, max-age=0`.

- `GET /` -> dashboard page
- `GET /process` -> process entry page
- `GET /auxiliary` -> auxiliary systems page
- `GET /amount-control` -> amount control page
- `GET /breakdowns` -> breakdown page
- `GET /reports` -> reports/IFS/sync page
- `GET /login` -> public login page; redirects `303` to `/` if already authed

### `GET /manifest.webmanifest`

- Handler: `app/web/pages.py::manifest`
- Auth: public
- Used by: app shell layout

Response:

```json
{"name": "Mobil Proses Veri Girisi", "short_name": "Proses", "start_url": "/", "scope": "/"}
```

### `GET /service-worker.js`

- Handler: `app/web/pages.py::service_worker`
- Auth: public
- Used by: `offline.js` service worker registration

Response: generated JavaScript with injected `APP_ROUTE_URLS`,
`APP_SHELL_URLS`, and `CACHE_NAME`. Headers include:

```http
Cache-Control: no-cache
Service-Worker-Allowed: /
```

### `GET /static/{asset_path}`

- Handler: FastAPI `StaticFiles` mounted in `app/main.py`
- Auth: public
- Used by: app styles/scripts/modules/manifest icons if any
- Cache: `Cache-Control: public, max-age=3600`

Query `?v=20260626-breakdowns-paper-fields` is cache-busting only.
