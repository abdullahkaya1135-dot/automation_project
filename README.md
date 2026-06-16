# Mobile Process Data Entry MVP

FastAPI app for phone-based process data entry on the office LAN. The app
saves each submission to SQLite first, then syncs saved records to the
production Excel workbooks when the workbooks are reachable. Offline phone
records are uploaded in bulk, and Excel writes are batched so a dump of many
records opens, backs up, saves, and closes the workbook once per batch.

## Project Structure

```text
app/
  db/            SQLite startup migrations and schema repair helpers
  domain/        Request parsing, shift/date rules, and field rules
  modules/       Feature-first service/repository/adapter slices
  routers/       FastAPI route modules
  shared/        Cross-feature infrastructure helpers
  static/        Browser CSS, JavaScript modules, manifest, and service worker
  templates/     Page templates and shared partials
  web/           Role workspace catalog and page access policy
docs/            Architecture, sync, manual acceptance, and historical notes
scripts/         Local operations and acceptance-check scripts
tests/           Automated pytest coverage
```

## Setup

Use Python 3.14. This computer has both of these commands available:

```powershell
py -3.14 --version
python --version
```

Create and activate a virtual environment:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

For local development checks, install the optional developer tools:

```powershell
python -m pip install -r requirements-dev.txt
```

Create local configuration:

```powershell
Copy-Item .env.example .env
```

Edit `.env` and set at least:

```text
EXCEL_PATH=\\server\share\path\workbook.xlsx
SHEET_NAME=PROSES 2026
APP_PIN=choose-a-local-admin-pin
APP_ROLE_PINS=operator:1111,utility:2222,supervisor:3333,planning:4444,admin:9999
SESSION_SECRET=generate-a-long-random-secret
HOST=0.0.0.0
PORT=8080
TIMEZONE=Europe/Istanbul
SQLITE_PATH=data/process_entries.sqlite3
BACKUP_DIR=data/backups
BACKUP_KEEP_COUNT=20
CYCLE_TABLE_PATH=C:\path\to\makine cycle tablosu.xlsx
REPORT_OUTPUT_DIR=C:\path\to\reports
IFS_BASE_URL=https://ifs.simsekplastik.com
IFS_TOKEN_URL=https://ifs.simsekplastik.com/auth/realms/prod/protocol/openid-connect/token
IFS_CLIENT_ID=your-ifs-client-id
IFS_USERNAME=your-ifs-user
IFS_PASSWORD=your-ifs-password
PRODUCTION_PLANNING_DIR=\\fileserver\GENEL\URETIM GUNLUK TAKIP
PRODUCTION_PLANNING_PATH=\\fileserver\GENEL\URETIM GUNLUK TAKIP\10.06.2026 ÇİZELGE 2.xlsx
```

Do not commit `.env`; it contains local workbook paths, role PINs, the session
secret, and IFS credentials. `APP_PIN` remains supported as an admin fallback,
but `APP_ROLE_PINS` is the preferred MVP role-separation mechanism.

## Running The App

Start the server from the project folder:

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

Open the app on the office computer:

```text
http://127.0.0.1:8080
```

After login, the app redirects to the workspace for the authenticated role:

- `operator`: `/operator` for tour context, machine entry, and phone sync.
- `utility`: `/utility` for auxiliary systems entry and recent submissions.
- `supervisor`: `/supervisor` for pending/failed Excel sync and retry controls.
- `planning`: `/planning` for cycle report and IFS U1 return candidates.
- `admin`: may open all workspaces.

Check service health:

```text
http://127.0.0.1:8080/health
```

To use the app from a phone on the same company Wi-Fi, find the office
computer's local IP address:

```powershell
ipconfig
```

Then open this URL format on the phone:

```text
http://<office-computer-ip>:8080
```

If the phone cannot connect, allow inbound traffic for Python or TCP port
`8080` in Windows Firewall, and confirm the phone and office computer are on
the same network segment.

## Phone Offline Mode

The phone UI saves submissions to Chrome IndexedDB before sending them to the
office computer. If the hotspot drops, keep using the same app tab; pending
records will sync automatically when the phone reconnects. The
`Telefon Senkronizasyonu` panel also has a manual `Sync` button and JSON/CSV
exports for unsynced phone records.

When the phone reconnects, pending outbox records are sent to
`POST /api/offline/bulk-sync` in one request. The server resolves local phone
dependencies, such as entries that depend on an offline-created tour context,
saves everything to SQLite first, and then syncs process entries and auxiliary
submissions to Excel in batches. The legacy single-record endpoints remain
available for compatibility.

Use one stable phone URL. Chrome stores IndexedDB per exact origin, so changing
between IPs, hostnames, HTTP/HTTPS, or ports creates a different local phone
database.

For the PWA shell to reopen while offline, phone access must use HTTPS, such as:

```text
https://192.168.137.1:8443
```

Create the local certificate files:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\create_https_cert.ps1 -InstallRootForCurrentUser
```

Install `local-certs\process-project-local-ca.cer` on the phone as a trusted CA
certificate, then start the HTTPS server with:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_https_server.ps1 -Port 8443 -CertFile .\local-certs\process-project-server.crt -KeyFile .\local-certs\process-project-server.key
```

If the phone cannot open the HTTPS URL, run PowerShell as Administrator once
and allow inbound TCP 8443:

```powershell
New-NetFirewallRule -DisplayName "Process Project HTTPS 8443" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8443 -Profile Any
```

Service workers do not register on a normal phone LAN URL over plain HTTP.
Plain HTTP still supports IndexedDB queueing while the loaded tab remains open,
but it will not provide the full offline app shell after a browser reload.

## Data Behavior

Every entry is written to SQLite before Excel is touched. The default SQLite
database path is:

```text
data/process_entries.sqlite3
```

After the local save succeeds, Excel sync may happen immediately or as part of
a batch retry/offline bulk sync. Process entries append columns `A:Y` to the
configured worksheet. Tour context values fill columns `A:E`; machine entry
fields now use canonical Excel letters (`F:Y`) so product is `G`, work order is
`H`, raw material is `I`, shared process values continue through `N`, and oven
and mold temperatures are `X:Y`.

Payload field definitions are backend-owned. `/api/bootstrap` includes
`field_definitions`, and `/api/field-definitions` exposes the same lists for
diagnostics. The phone UI uses those definitions when building process-entry
and auxiliary payloads, which keeps frontend field lists aligned with Python
validation and Excel mapping rules.

The machine code controls which section-only columns are written. Machines with
`1xx` codes plus `271` write first-section fields `O:Q` and leave `R:W` blank.
Machines with `2xx`, `3xx`, `4xx`, and `5xx` codes write second-section fields
`R:W` and leave `O:Q` blank. The app still accepts older queued phone payloads
and converts them before saving.

Excel sync behavior:

- Decimal comma and decimal point inputs are normalized for numeric columns.
- Hyphen-separated temperature or pressure ranges remain text.
- Blank optional fields remain blank cells.
- The app detects the real next data row instead of relying on `ws.max_row`.
- The app validates the existing `A:Y` header shape before writing.
- Batch process-entry sync opens the workbook once, creates one backup, writes
  all rows sequentially, saves once, and updates SQLite row numbers.
- Batch auxiliary sync writes multiple 15-row daily blocks with one workbook
  open, one backup, and one save.

If Excel is locked, missing, permission-denied, or otherwise unreachable, the
entry remains saved in SQLite with `pending_excel` or `failed_excel` status.
Use supervisor Retry buttons to append pending entries or auxiliary submissions
after workbook access is restored. Retry processes old unsynced records first.
If the workbook is unavailable, records remain in SQLite with the last Excel
error and can be retried later.

Machine and work order values are loaded directly from IFS with an OAuth bearer
token. The app fetches active PET operations during `/api/bootstrap` and maps
`PreferredResourceId` to the Makine dropdown and `OrderNo` to the work-order
dropdown.

The `IFS U1 Iade Adaylari` check also reads visible job orders from column `A`
of the latest valid `.xlsx` workbook in `PRODUCTION_PLANNING_DIR`. Daily files
are selected by the newest date at the start of the filename, such as
`12.06.2026 CIZELGE 1.xlsx`; file modified time is only used as a tie-breaker.
Temporary Excel files starting with `~$` are ignored. If
`PRODUCTION_PLANNING_DIR` is blank, the app falls back to the configured
`PRODUCTION_PLANNING_PATH` workbook. Hidden sheets, hidden rows, and hidden
column `A` are ignored before the app checks scheduled orders for HM-02 usage in
IFS.

IFS authentication uses the password grant to obtain a bearer token. Keep
`IFS_USERNAME`, `IFS_PASSWORD`, `IFS_CLIENT_ID`, and optional `IFS_CLIENT_SECRET`
in local `.env` only.

## Backups

Before each Excel batch save, the app copies the workbook into the configured backup
directory:

```text
data/backups
```

Backup filenames include the source workbook name and a timestamp. The app keeps
only the latest `BACKUP_KEEP_COUNT` backups for that workbook and prunes older
matching backup files.

## Operational Limitations

- This is a LAN-only MVP with lightweight role PIN authentication.
- Run one FastAPI process on one office computer.
- Do not run multiple app instances against the same workbook.
- The workbook must keep the expected worksheet shape in columns `A:Y`.
- The app appends rows only; it does not create new Excel columns.
- QR scanning is not included in this MVP.
- If the workbook is open or locked in a way that blocks saving, entries stay in
  SQLite until Retry sync succeeds.

## Manual Acceptance Test

Use this checklist on the office computer after `.env` points at safe workbook
copies or the real workbooks and contains the role PINs.

Start the app:

```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

Open the app on the office computer:

```text
http://127.0.0.1:8080
```

Open the app from a phone on company Wi-Fi:

```text
http://<office-computer-ip>:8080
```

Log in as `operator`, save one tour context, and submit one machine row. The
record should be stored in the phone outbox first, then uploaded to the server.
The server saves SQLite before Excel and returns the current Excel sync state.

For the offline dump path:

1. Open `/operator` from a phone.
2. Disconnect the phone from the office network.
3. Save one tour context and many machine entries.
4. Reconnect.
5. Press `Sync` once.
6. Confirm the server receives one `/api/offline/bulk-sync` request.
7. Confirm SQLite contains every entry.
8. Confirm Excel rows are sequential and unique.
9. Confirm one workbook backup was created for the batch.
10. Press `Sync` again and confirm rows are not duplicated.

After submitting the row, run the acceptance verifier from another terminal:

```powershell
python scripts\manual_acceptance_check.py --expected-row 1726
```

The verifier checks that the running app responds, authenticated bootstrap works,
the latest SQLite entry exists, the Excel row matches the latest SQLite entry,
and a timestamped backup exists within the configured retention count.

For role-page acceptance, include:

```powershell
python scripts\manual_acceptance_check.py --check-role-pages
```

For an offline dump of many machine entries, include the latest batch size after
syncing:

```powershell
python scripts\manual_acceptance_check.py --latest-batch-size 50
```

That batch check verifies the latest SQLite process entries are synced to unique
sequential Excel rows and that each Excel row still matches its SQLite machine
and work order.

For a safe-copy dry run that creates a new phone-style bulk sync batch through
the running API, use:

```powershell
python scripts\manual_acceptance_check.py --exercise-bulk-sync 50 --check-role-pages
```

This posts one `/api/offline/bulk-sync` request with 50 entries, verifies one
new process workbook backup, then replays the same batch to confirm no duplicate
SQLite or Excel rows are created. Use this only with copied workbooks and a test
SQLite database.

For a safe-copy dry run of the auxiliary retry batch path, include:

```powershell
python scripts\manual_acceptance_check.py --exercise-bulk-sync 1 --exercise-auxiliary-retry 3 --check-role-pages
```

The auxiliary exercise queues submissions through `/api/offline/bulk-sync` with
Excel sync disabled, confirms the queue step does not touch the workbook, then
calls the supervisor retry API and verifies one auxiliary workbook backup plus
sequential 15-row Excel blocks. Run it only when there are no pre-existing
unsynced auxiliary submissions.

If Excel was unavailable during submission, restore workbook access, log in as
`supervisor`, use the relevant Retry button, then run the verifier again. For a
dry run against a safe workbook copy, omit `--expected-row` or pass the expected
row for that copy.

## Tests

Run the automated test suite from an activated virtual environment:

```powershell
python -m pytest
```

Run static checks when developer tools are installed:

```powershell
python -m ruff check .
python -m mypy app tests
```

The performance regression tests count workbook open/save/backup calls for bulk
sync and retry paths; they do not rely on wall-clock timing.
