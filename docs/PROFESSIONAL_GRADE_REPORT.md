# Professional Grade Code Audit Report

> Historical note: This audit captures the repository state on 2026-06-11.
> Several findings mention pre-migration module paths and file sizes that are no
> longer current after the first-batch feature/module split. Keep this report as
> historical context; use [../README.md](../README.md) for current layout and
> operation guidance.

Date: 2026-06-11

Scope: FastAPI backend, SQLite persistence, Excel/IFS integrations, Jinja/static mobile UI, tests, docs, repository hygiene, and operational readiness.

## Executive Summary

The app is a solid LAN MVP with a surprisingly strong backend test suite for its size. The core safety decision is good: every submission is saved to SQLite before Excel sync is attempted. Excel access is wrapped with typed errors, header validation, backup creation, and retry support. IFS access is also isolated in a service module and covered with HTTP mock tests.

To make the app professional grade, the biggest work is not adding features. It is hardening reliability, separating concerns, adding a real project/tooling baseline, and reducing operational risk around Excel writes, authentication, configuration, and deployment.

Current verification after initial remediation:

- `python -m pytest`: 60 passed, 1 external Starlette TestClient warning.
- `python -m ruff check .`: passed.
- `python -m mypy app tests`: passed.
- Current worktree is dirty, with many modified files and several important untracked modules/tests.

Initial findings already addressed:

- Serialized Excel writes through a shared in-process write lock.
- Retry idempotency for already-written process rows and auxiliary-system blocks.
- Separate `SESSION_SECRET` for session-cookie signing.
- IFS API routes split out of `app/main.py`.
- Project tooling baseline added with Ruff, mypy, pytest config, dev requirements, and line-ending policy.

## What Is Already Strong

- SQLite-first write path protects operator submissions when Excel is locked or unavailable.
- Excel append validates the workbook shape before writing and avoids `ws.max_row` traps caused by formatting-only rows.
- Backups are created before workbook saves, with retention.
- Tests cover API routes, auth, SQLite model setup, Excel edge cases, IFS pagination/error handling, and cycle-report behavior.
- Frontend avoids `innerHTML` and uses DOM APIs for rendered data, reducing XSS exposure.
- Configuration is environment-driven and `.env` is ignored by Git.
- The README documents setup, operational limitations, manual acceptance, and sync behavior.

## Highest Priority Risks

1. Concurrent Excel writes can corrupt or duplicate data.

The app can receive multiple phone submissions at nearly the same time, but workbook writes are not protected by an application-level lock or queue. Two requests can detect the same next row and then race to save. Professional-grade behavior needs a single-writer queue or a lock around all workbook writes, including process entry and auxiliary-system writes.

Recommended fix:

- Add a central Excel write coordinator.
- Serialize workbook append/retry operations.
- Expose queue status in `/health`.
- Add concurrency tests that submit multiple entries simultaneously and assert unique Excel row numbers.

2. Sync is not idempotent enough for Excel as an external system.

If the Excel save succeeds but the database update fails, the entry can remain pending and later be appended again. Excel is not transactional with SQLite, so this needs explicit recovery design.

Recommended fix:

- Add a sync state machine: `pending`, `syncing`, `synced`, `failed`.
- Store a deterministic payload fingerprint in SQLite.
- Before appending, scan a bounded recent Excel range for the fingerprint-equivalent row where possible.
- Consider writing an app entry ID/fingerprint to a hidden/protected workbook column or a sidecar audit workbook if changing the main workbook is not allowed.

3. Authentication is MVP-level.

`app/auth.py` derives the session signing key from `APP_PIN`, uses a shared PIN, has no rate limiting, no lockout, no operator identity, and sets `secure=False` for the cookie. That is acceptable for a LAN MVP but not professional-grade production.

Recommended fix:

- Add a separate `SESSION_SECRET`.
- Add login rate limiting and audit logs.
- Use HTTPS and set `secure=True`.
- Track operator identity if accountability matters.
- Keep shared PIN only as a temporary fallback.

4. No production deployment model exists.

The README explains running Uvicorn manually, but professional operation needs service management, restart behavior, log retention, backup restore instructions, and health monitoring.

Recommended fix:

- Run as a Windows service or supervised process.
- Add structured logs with rotation.
- Add a `/health` response that separates app, SQLite, Excel process workbook, auxiliary workbook, and IFS status.
- Document backup restore and incident handling.

5. Important current work is not committed.

Git shows a large dirty worktree, including untracked runtime-relevant files:

- `app/auxiliary_systems_service.py`
- `app/auxiliary_systems_sync_service.py`
- `app/ifs_client.py`
- `tests/test_auxiliary_systems_service.py`
- `tests/test_ifs_client.py`

Professional-grade work needs clean, reviewable commits and no accidental loss of untracked files.

Recommended fix:

- Review and stage intentional source/test files.
- Keep `runtime-logs/`, `phone-test/`, local HAR files, and local conversation exports out of commits unless deliberately needed.
- Add `.gitattributes` to normalize line endings and stop CRLF churn warnings.

## Architecture And Code Cleanliness

### Backend module boundaries

`app/main.py` is now 813 lines and owns routing, validation helpers, time/shift logic, request parsing, bootstrap orchestration, and IFS/report endpoints. This is the largest maintainability hotspot.

Recommended target structure:

```text
app/
  api/
    auth_routes.py
    bootstrap_routes.py
    entry_routes.py
    auxiliary_routes.py
    ifs_routes.py
    report_routes.py
    health_routes.py
  domain/
    shifts.py
    entry_payloads.py
    auxiliary_payloads.py
  services/
    excel_writer.py
    sync_queue.py
    ifs_client.py
    reports.py
  schemas/
    requests.py
    responses.py
```

Keep `create_app()` small: settings, middleware, static/templates, router registration.

### Request and response schemas

Only login and tour context use Pydantic models. Most important endpoints accept raw `dict[str, Any]`.

Recommended fix:

- Add Pydantic request models for entry submissions, auxiliary submissions, retry responses, IFS responses, and health.
- Add `response_model=` to routes.
- Reject unknown fields where useful.
- Move Turkish validation messages into centralized constants.

### Opaque Excel column fields

The database and payloads use `col_a`, `col_b`, etc. That is convenient for Excel mapping but makes domain code hard to read.

Recommended fix:

- Use domain names internally, such as `machine`, `work_order`, `actual_cycle_time`, `oven_temperatures`.
- Keep a single mapping layer that converts domain fields to workbook columns.
- Preserve the existing Excel shape externally.

### Duplicate sync/write patterns

`sync_service.py` and `auxiliary_systems_sync_service.py` have similar retry, serialization, and error-update flow. `excel_service.py` and `auxiliary_systems_service.py` also duplicate workbook backup/header/append patterns.

Recommended fix:

- Extract shared workbook backup/prune helpers.
- Extract a common sync-result/update helper.
- Keep workbook-specific row builders separate.

### Frontend size and drift

`app/static/app.js` is 1,415 lines. It contains API calls, form parsing, dropdown logic, status rendering, list rendering, date/shift calculations, text constants, and IFS result tables.

Recommended fix:

- Split by responsibility: `api.js`, `tour-context.js`, `entry-form.js`, `auxiliary-form.js`, `sync-lists.js`, `ifs-return.js`, `dom.js`.
- Generate field definitions from a backend endpoint or shared JSON file to stop Python and JS field lists from drifting.
- Add a simple frontend test layer for pure functions such as temperature shorthand, date formatting, dropdown filtering, and API error parsing.

Concrete drift found:

- `app/shop_order_source.py` returns `source: "ifs-token"`.
- `app/static/app.js` checks `source?.source === "ifs"` when choosing the source label, so the UI can label IFS data as `Dosya` in the status title.

## Security Hardening

Recommended improvements:

- Add `SESSION_SECRET`; do not derive cookie signing from `APP_PIN`.
- Add login rate limiting and temporary lockout after repeated failures.
- Set secure cookies when HTTPS is enabled.
- Add CSRF protection or move to a non-cookie API token model for state-changing API calls.
- Redact IFS response snippets before showing/storing errors. `_raise_for_ifs_status()` includes response body text, which can be useful but may expose sensitive system details.
- Move away from OAuth password grant if IFS supports a better machine-to-machine flow.
- Add secret scanning in CI.
- Add dependency vulnerability scanning.
- Keep HAR captures and runtime logs outside Git and clean them from the workspace when no longer needed.

## Reliability And Operations

Recommended improvements:

- Add a single-writer queue for all Excel mutations.
- Add structured logging with request IDs, entry IDs, sync attempt IDs, and exception classes.
- Add metrics or at least counters for pending entries, failed entries, last successful sync time, IFS fetch time, and Excel save time.
- Add startup checks that fail fast for invalid configuration but do not require Excel to be available before the app can save locally.
- Add a documented backup restore procedure.
- Add a scheduled backup/export of SQLite, not just Excel backups.
- Add timeout and retry configuration for IFS calls through settings.
- Cache IFS bootstrap/shop-order data with a short TTL and show stale-but-usable data when IFS is temporarily unavailable.
- Avoid `asyncio.run()` inside service logic long term; keep async IFS workflows async all the way or isolate them behind a sync adapter.

## Data And Migration Strategy

Current database setup uses `Base.metadata.create_all()` and startup cleanup for a legacy table. That is fine for MVP, but production needs migration history.

Recommended improvements:

- Add Alembic migrations.
- Add schema constraints for fields that the API already treats as required.
- Store dates as real date/datetime values where practical; format only at the Excel/UI boundary.
- Store UTC timestamps as timezone-aware values or make the convention explicit.
- Add audit fields for operator/user once authentication improves.

## Testing Plan To Reach Professional Grade

Keep the existing backend tests. Add these layers:

- Concurrency tests for simultaneous entry submission and retry.
- Duplicate-prevention tests for partial sync failure after Excel save.
- Frontend unit tests for pure JS behavior.
- Playwright smoke tests for login, bootstrap, submit entry, retry sync, and mobile viewport layout.
- Static checks in CI: Ruff, formatter, mypy or pyright, dependency audit.
- Manual acceptance script expansion for auxiliary-system submissions and IFS return-candidate workflow.
- A production-like dry-run test using workbook copies, not live Excel files.

Current warning cleanup:

- FastAPI/Starlette TestClient warning about `httpx` compatibility.
- Deprecated `HTTP_422_UNPROCESSABLE_ENTITY`; switch to `HTTP_422_UNPROCESSABLE_CONTENT`.

## Tooling Baseline

Add:

- `pyproject.toml` for Ruff, formatter, pytest, and typing config.
- Pinned dependencies via `requirements.in` + compiled `requirements.txt`, or a lockfile-based tool.
- `.pre-commit-config.yaml`.
- `.gitattributes` for stable line endings.
- CI workflow that runs tests and static checks.
- Optional coverage reporting with a practical threshold.

Suggested initial `pyproject.toml` scope:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]

[tool.ruff]
line-length = 88
target-version = "py314"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "SIM", "RUF"]

[tool.mypy]
python_version = "3.14"
strict = false
warn_unused_ignores = true
warn_redundant_casts = true
```

## Phased Roadmap

### Phase 1: Stabilize The Current Codebase

- Commit or intentionally discard current untracked/modified source changes.
- Add `pyproject.toml`, Ruff, formatter, `.gitattributes`, and CI.
- Fix the `ifs-token` vs `ifs` frontend status drift.
- Clean up the two current test warnings.
- Add missing files to Git if they are part of the app.

### Phase 2: Reliability Hardening

- Implement a single-writer Excel queue/lock.
- Add concurrency tests.
- Add idempotency/recovery design for partial Excel/SQLite failures.
- Add structured logging and operational health details.
- Add SQLite backup/export.

### Phase 3: Architecture Cleanup

- Split `app/main.py` into routers and domain helpers.
- Add Pydantic schemas for all request/response payloads.
- Replace `col_a` style internal logic with domain names and a workbook mapping layer.
- Extract duplicated sync/workbook patterns.
- Split frontend JS into modules.

### Phase 4: Production Readiness

- Add HTTPS or a reverse proxy.
- Add `SESSION_SECRET`, secure cookies, rate limiting, and audit logs.
- Move IFS auth to a service-user/machine-friendly flow if possible.
- Create Windows service deployment docs and incident runbooks.
- Add Playwright mobile smoke tests and production-like dry-run workbook tests.

## Bottom Line

The app is a good MVP with a strong safety instinct and meaningful tests. The professional-grade path is clear: lock down Excel write concurrency, improve auth and operational discipline, establish tooling/CI, then refactor the largest modules into smaller typed units. The first serious production blocker to solve is serialized, idempotent Excel synchronization.
