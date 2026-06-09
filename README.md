# Mobile Process Data Entry MVP

FastAPI app for phone-based process data entry on the office LAN. The app
saves each submission to SQLite first, then appends the same data to the
production Excel workbook when the workbook is reachable.

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

Create local configuration:

```powershell
Copy-Item .env.example .env
```

Edit `.env` and set at least:

```text
EXCEL_PATH=\\server\share\path\workbook.xlsx
SHEET_NAME=PROSES 2026
APP_PIN=choose-a-local-pin
HOST=0.0.0.0
PORT=8080
TIMEZONE=Europe/Istanbul
SQLITE_PATH=data/process_entries.sqlite3
BACKUP_DIR=data/backups
BACKUP_KEEP_COUNT=20
SHOP_ORDER_SOURCE_PATH=C:\Users\<user>\Desktop\html_to_parse.txt
```

Do not commit `.env`; it contains the local workbook path and shared PIN.

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

## Data Behavior

Every entry is written to SQLite before Excel is touched. The default SQLite
database path is:

```text
data/process_entries.sqlite3
```

After the local save succeeds, the app attempts to append columns `A:Y` to the
configured worksheet. Tour context values fill columns `A:E`; machine entry
values from the UI are mapped into the existing workbook columns: machine to
`F`, work order to `H`, cavity and timing fields to `J:Q`, oven temperatures to
`X`, and mold temperatures to `Y`.

Excel append behavior:

- Decimal comma and decimal point inputs are normalized for numeric columns.
- Hyphen-separated temperature or pressure ranges remain text.
- Blank optional fields remain blank cells.
- The app detects the real next data row instead of relying on `ws.max_row`.
- The app validates the existing `A:Y` header shape before writing.

If Excel is locked, missing, permission-denied, or otherwise unreachable, the
entry remains saved in SQLite with `pending_excel` or `failed_excel` status.
Use the in-app Retry sync button to append pending entries after workbook access
is restored. Retry processes old unsynced entries first and stops on the first
Excel error so the operator can fix the workbook state.

Machine and work order values are loaded from `SHOP_ORDER_SOURCE_PATH`. The
source is expected to be the OData payload saved as `html_to_parse.txt`; each
`value` item contributes `ResourceId` to the Makine dropdown and `OrderNo` to
the İş emri dropdown. When the setting is blank, the app defaults to the current
Windows user's `Desktop\html_to_parse.txt`.

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
  SQLite until Retry sync succeeds.

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
The UI should report either `Synced to Excel` or `Saved locally. Excel sync is
pending.`

After submitting the row, run the acceptance verifier from another terminal:

```powershell
python scripts\manual_acceptance_check.py --expected-row 1726
```

The verifier checks that the running app responds, authenticated bootstrap works,
the latest SQLite entry exists, the Excel row matches the latest SQLite entry,
and a timestamped backup exists within the configured retention count.

If Excel was unavailable during submission, restore workbook access, use the
in-app Retry sync button, then run the verifier again. For a dry run against a
safe workbook copy, omit `--expected-row` or pass the expected row for that copy.

## Tests

Run the automated test suite from an activated virtual environment:

```powershell
pytest
```
