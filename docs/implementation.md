# Mobile Process Data Entry MVP Implementation Plan

> Historical note: This original MVP plan predates the first-batch module
> migration to `app/core`, `app/features`, `app/domain`, and `app/integrations`.
> Use [README.md](../README.md) for current setup and module layout.

## 1. Confirm Local Prerequisites

1. Verify the workspace contains only project files that should be part of the MVP.
2. Locate the Python 3.14 executable on the office computer.
   - Try `py -3.14`, then `python`, then the installed Python path if needed.
   - Record the working command in the README.
3. Confirm the production Excel workbook can be opened from the office computer.
   - Verify the configured UNC path is reachable.
   - Confirm the workbook contains the target sheet `PROSES 2026`.
   - Confirm the real last data row in the workbook.
4. Confirm the office computer can serve the app over LAN.
   - Host: `0.0.0.0`
   - Port: `8080`
   - Test URL format from phone: `http://<local-ip>:8080`
5. Decide the first shared app PIN and store it only in local configuration.

## 2. Scaffold the FastAPI Project

1. Create the project structure:

   ```text
   app/
     __init__.py
     main.py
     config.py
     database.py
     models.py
     schemas.py
     auth.py
     excel_service.py
     sync_service.py
     templates/
       login.html
       index.html
     static/
       app.css
       app.js
   data/
     backups/
   tests/
   .env.example
   README.md
   requirements.txt
   ```

2. Add dependencies to `requirements.txt`:
   - `fastapi`
   - `uvicorn`
   - `jinja2`
   - `python-dotenv`
   - `sqlalchemy`
   - `openpyxl`
   - `pytest`
   - `httpx`
3. Add `.env.example` with:

   ```text
   EXCEL_PATH=
   SHEET_NAME=PROSES 2026
   APP_PIN=
   HOST=0.0.0.0
   PORT=8080
   TIMEZONE=Europe/Istanbul
   SQLITE_PATH=data/process_entries.sqlite3
   BACKUP_DIR=data/backups
   BACKUP_KEEP_COUNT=20
   ```

4. Configure `.gitignore` to exclude:
   - `.env`
   - `.venv/`
   - `data/*.sqlite3`
   - `data/backups/*.xlsx`
   - Python cache and test cache files.

## 3. Build Configuration and App Startup

1. Implement `app/config.py`.
   - Load values from `.env`.
   - Validate required settings on startup.
   - Convert `PORT` and `BACKUP_KEEP_COUNT` to integers.
2. Implement `app/main.py`.
   - Create the FastAPI app.
   - Mount static assets.
   - Configure Jinja templates.
   - Register API routes.
   - Add `GET /health`.
3. On startup, initialize SQLite tables if they do not exist.
4. On startup, initialize SQLite and check runtime configuration.

## 4. Design the SQLite Data Model

1. Implement `tour_contexts`.
   - `id`
   - `date`
   - `ambient_temp`
   - `production_engineer`
   - `shift_chief`
   - `shift`
   - `created_at`
   - `updated_at`
2. Implement `entries`.
   - `id`
   - `tour_context_id`
   - Excel payload columns `col_a` through `col_y`
   - SQLite-only fields: `status`, `notes`, `mold_info`
   - Sync fields: `sync_status`, `excel_row_number`, `last_error`
   - Timestamps: `submitted_at`, `created_at`, `updated_at`, `synced_at`
3. Use sync statuses:
   - `synced`
   - `pending_excel`
   - `failed_excel`
4. Add helper functions for creating sessions and committing changes safely.

## 5. Implement Authentication

1. Implement `POST /api/login`.
   - Accept a PIN.
   - Compare with `APP_PIN`.
   - Set a simple signed or opaque session cookie.
2. Add an auth dependency for protected routes.
3. Redirect unauthenticated page requests to the login page.
4. Return `401` from unauthenticated API requests.
5. Keep authentication intentionally simple because this is a LAN-only MVP.

## 6. Implement Excel Workbook Services

1. Implement workbook loading in `excel_service.py`.
   - Open the configured workbook with `openpyxl`.
   - Select the configured sheet by name.
   - Fail with a clear typed error if the file is missing, locked, permission-denied, or the sheet is absent.
2. Implement true last-row detection.
   - Do not use `ws.max_row` as the append target.
   - Scan rows for actual values in the relevant columns.
   - Treat formatting-only rows as empty.
   - Return the last row containing meaningful data.
3. Implement header validation.
   - Read existing headers from columns `A:Y`.
   - Confirm the expected workbook shape before appending.
   - Fail safely if the workbook structure has changed.
4. Implement value normalization.
   - Accept decimal comma or decimal point for numeric fields.
   - Convert numeric values before writing to Excel.
   - Preserve hyphen-separated temperature or pressure strings as text.
   - Preserve blank optional fields as blank cells.
5. Implement backup creation before each save.
   - Copy the workbook to `data/backups/`.
   - Use a timestamped filename.
   - Keep only the latest `BACKUP_KEEP_COUNT` backup files.
6. Implement append.
   - Build a full row for columns `A:Y`.
   - Append to the detected next real row.
   - Save the workbook.
   - Return the Excel row number.

## 7. Implement API Routes

1. Implement `GET /api/bootstrap`.
   - Return latest active tour context if useful.
   - Return current Excel availability and last sync error if any.
2. Implement `POST /api/tour-context`.
   - Validate date, ambient temperature, engineer, shift chief, and shift.
   - Save the context in SQLite.
   - Return the saved context ID.
3. Implement `POST /api/entries`.
   - Validate required machine row fields.
   - Combine the selected tour context with the machine row payload.
   - Save to SQLite first.
   - Attempt Excel append immediately.
   - If Excel append succeeds, mark `synced`.
   - If Excel append fails, mark `pending_excel` and return a local-save success response.
4. Implement `GET /api/entries`.
   - Return recent entries.
   - Support filtering by `sync_status`.
5. Implement `POST /api/sync/retry`.
   - Find pending or failed entries.
   - Append each unsynced entry to Excel.
   - Update row numbers and sync status.
   - Stop or continue on errors according to the safest implementation; report all results.
6. Implement `GET /health`.
   - Return app status.
   - Include SQLite status.
   - Include Excel reachability without modifying the workbook.

## 8. Build the Mobile UI

1. Create `login.html`.
   - PIN input.
   - Submit button.
   - Error state.
2. Create `index.html`.
   - Tour context section:
     - Date
     - Ambient temperature
     - Production engineer
     - Shift chief
     - Shift
   - Machine entry section:
     - Manual machine input.
     - Product and work order inputs.
     - Inputs for the remaining Excel `A:Y` payload fields.
     - SQLite-only status, notes, and mold info fields.
   - Recent submissions section.
   - Pending Excel sync section.
   - Retry sync button.
3. Optimize for phone use.
   - Large tap targets.
   - Minimal scrolling during repeated machine entry.
   - Numeric keyboard hints for numeric fields.
   - Clear saved/synced/pending feedback after submit.
4. Keep QR scanning out of the MVP.
   - Use manual machine entry first.
   - Revisit QR only after HTTPS or a supported camera-access setup exists.

## 9. Implement Frontend Behavior

1. Implement login submission with `fetch`.
2. Load bootstrap data after login.
3. Save or restore the active tour context in the browser session.
4. Submit entries through `/api/entries`.
5. Display result states:
   - Synced to Excel.
   - Saved locally, Excel pending.
   - Validation error.
6. Load recent entries and pending entries after each submit.
7. Wire the retry sync button to `/api/sync/retry`.

## 10. Add Tests

1. Add unit tests for true last-row detection.
   - Use a temporary workbook where `ws.max_row` is misleading because of formatting.
   - Confirm the detected next row follows the current workbook's real last row.
2. Add unit tests for Excel append.
   - Use a temporary workbook copy.
   - Submit one full entry.
   - Confirm headers are preserved.
   - Confirm all columns `A:Y` are written.
   - Confirm returned row number and SQLite sync metadata are correct.
3. Add unit tests for Excel failure handling.
   - Simulate missing workbook.
   - Simulate permission or locked workbook where possible.
   - Confirm entry remains in SQLite as `pending_excel`.
   - Confirm retry succeeds after workbook access is restored.
4. Add API tests with FastAPI `TestClient`.
   - Login.
   - Bootstrap.
   - Tour context save.
   - Entry submit.
   - Pending entry list.
   - Retry sync.
   - Health check.
5. Add a basic UI smoke test if practical.
   - Confirm login page renders.
   - Confirm main page renders after authenticated request.

## 11. Write the README

1. Document setup.
   - Python command.
   - Virtual environment creation.
   - Dependency installation.
   - `.env` creation.
2. Document running the app.
   - Local command.
   - LAN URL format.
   - Firewall note.
3. Document data behavior.
   - SQLite is always written first.
   - Excel append happens after local save.
   - Pending Excel entries can be retried.
4. Document backups.
   - Backup location.
   - Retention count.
5. Document operational limitations.
   - Single FastAPI process.
   - Single office computer.
   - No QR scanning in MVP.
   - No new Excel columns.

## 12. Manual Acceptance Test

1. Start the app on the office computer:

   ```text
   uvicorn app.main:app --host 0.0.0.0 --port 8080
   ```

2. Open the app from the office computer browser.
3. Open the app from a phone on company Wi-Fi using `http://<local-ip>:8080`.
4. Log in with the shared PIN.
5. Enter one tour context.
6. Submit one machine row.
7. Confirm the UI reports either:
   - Synced to Excel.
   - Saved locally, Excel pending.
8. Confirm the SQLite entry exists.
9. If Excel was available, confirm the workbook has a new row at the expected next row.
10. If Excel was unavailable, restore access and run retry sync.
11. Confirm a timestamped backup was created in `data/backups/`.
12. Confirm old backups are pruned after the retention count is exceeded.

## 13. Implementation Order

1. Scaffold files, config, dependencies, and README skeleton.
2. Implement SQLite models and database initialization.
3. Implement Excel read, header validation, and true last-row detection.
4. Implement Excel backup and append.
5. Implement authentication and protected routes.
6. Implement API endpoints.
7. Build the mobile UI.
8. Add retry sync behavior.
9. Add automated tests.
10. Run manual acceptance testing from desktop and phone.
11. Polish README with the final run commands and known limitations.

## 14. Completion Criteria

1. The app starts locally on `0.0.0.0:8080`.
2. A phone on company Wi-Fi can open the app.
3. A user can log in with the configured PIN.
4. Tour context is entered once and reused for fast machine entries.
5. Machine IDs are entered manually without loading or caching existing Excel rows.
6. Every entry is saved to SQLite before Excel is touched.
7. Excel rows are appended to the real next row, ignoring formatting-only rows.
8. Excel backups are created before saves and old backups are pruned.
9. Locked or unreachable Excel files do not lose submitted data.
10. Retry sync can append pending SQLite entries later.
11. Automated tests cover the main sync and failure paths.
12. README explains setup, running, LAN access, backups, and limitations.
