# Mobile Process Data Entry MVP

FastAPI app for phone-based process data entry on the office LAN. The app
saves each submission to SQLite first, then lets the operator append a selected
day's pending process rows to the production Excel workbook in one manual bulk
update.

## Project Structure

```text
app/
  core/          Configuration, database sessions, security, and filesystem paths
  features/      Business features with their API, domain, schema, and service code
  integrations/  External system clients such as IFS
  web/           Page routing; static assets and templates still live under app/static and app/templates
  routers/       Compatibility exports for older route import paths
  services/      Compatibility exports plus shared workbook/browser-facing helpers
  domain/        Compatibility exports plus shared request/date helpers
  static/        Browser CSS, JavaScript modules, manifest, and service worker
  templates/     Page templates and shared partials
docs/            Historical plans, implementation notes, and audit reports
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
APP_PIN=choose-a-local-pin
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
IFS_PART_PREFIXES=HM-02,HM-03,HM-04
PRODUCTION_PLANNING_DIR=\\fileserver\GENEL\URETIM GUNLUK TAKIP
PRODUCTION_PLANNING_PATH=\\fileserver\GENEL\URETIM GUNLUK TAKIP\10.06.2026 ÇİZELGE 2.xlsx
```

Do not commit `.env`; it contains the local workbook path, shared PIN, session
secret, and IFS credentials.

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

Every entry is written to SQLite before Excel is touched. Process entries stay
queued for Excel until an operator uses the reports page bulk update button. The
default SQLite database path is:

```text
data/process_entries.sqlite3
```

When the operator selects a date on the reports page and clicks `Excel'e aktar`,
the app appends that day's pending columns `A:Y` to the configured worksheet in
one workbook open/save cycle. Tour context values fill columns `A:E`; machine
entry fields now use canonical Excel letters (`F:Y`) so product is `G`, work
order is `H`, raw material is `I`, shared process values continue through `N`,
and oven and mold temperatures are `X:Y`.

The machine code controls which section-only columns are written. Machines with
`1xx` codes plus `271` write first-section fields `O:Q` and leave `R:W` blank.
Machines with `2xx`, `3xx`, `4xx`, and `5xx` codes write second-section fields
`R:W` and leave `O:Q` blank. The app still accepts older queued phone payloads
and converts them before saving.

Excel append behavior:

- Decimal comma and decimal point inputs are normalized for numeric columns.
- Hyphen-separated temperature or pressure ranges remain text.
- Blank optional fields remain blank cells.
- The app detects the real next data row instead of relying on `ws.max_row`.
- The app validates the existing `A:Y` header shape before writing.

If Excel is locked, missing, permission-denied, or otherwise unreachable during
the bulk update, the selected entries remain saved in SQLite with `failed_excel`
status. Restore workbook access, then use `Excel'e aktar` again for that date.

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
column `A` are ignored before the app checks scheduled orders for
HM-02/HM-03/HM-04 usage in IFS. Set `IFS_PART_PREFIXES` to a comma-separated
list such as
`HM-02,HM-03,HM-04` to control which raw-material prefixes are included; the
legacy `IFS_PART_PREFIX` setting is still accepted for custom single-prefix
overrides when the list is not set.

IFS authentication uses the password grant to obtain a bearer token. Keep
`IFS_USERNAME`, `IFS_PASSWORD`, `IFS_CLIENT_ID`, and optional `IFS_CLIENT_SECRET`
in local `.env` only.

## Backups

Before each Excel save, the app copies the workbook into the configured backup
directory:

```text
data/backups
```

Backup filenames include the source workbook name and a timestamp. The app keeps
only the latest `BACKUP_KEEP_COUNT` backups for that workbook and prunes older
matching backup files.

## Operational Limitations

- This is a LAN-only MVP with simple shared-PIN authentication.
- Run one FastAPI process on one office computer.
- Do not run multiple app instances against the same workbook.
- The workbook must keep the expected worksheet shape in columns `A:Y`.
- The app appends rows only; it does not create new Excel columns.
- QR scanning is not included in this MVP.
- If the workbook is open or locked in a way that blocks saving, entries stay in
  SQLite until the dated `Excel'e aktar` action succeeds.

## Manual Acceptance Test

Use this checklist on the office computer after `.env` points at the real
workbook and contains the shared PIN.

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

Log in with the shared PIN, save one tour context, and submit one machine row.
The UI should save the row locally and show it in the pending Excel list on the
reports page until `Excel'e aktar` is run for that date.

After submitting the row, run the acceptance verifier from another terminal:

```powershell
python scripts\manual_acceptance_check.py --expected-row 1726
```

The verifier checks that the running app responds, authenticated bootstrap works,
the latest SQLite entry exists, the Excel row matches the latest SQLite entry,
and a timestamped backup exists within the configured retention count.

If Excel was unavailable during export, restore workbook access, use the dated
`Excel'e aktar` button, then run the verifier again. For a dry run against a
safe workbook copy, omit `--expected-row` or pass the expected row for that copy.

## Tests

Run the automated test suite from an activated virtual environment:

```powershell
pytest
```

Run static checks when developer tools are installed:

```powershell
ruff check .
mypy app tests
```
