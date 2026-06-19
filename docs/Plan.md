Mobile Process Data Entry MVP Plan

> Historical note: This original MVP planning artifact predates the current
> module layout and later IFS/auxiliary-system features. Use
> [../README.md](../README.md) for current setup and operation details.

Summary
Build a local FastAPI web app in the empty Process Project workspace. The app
will run on the office computer at `http://<local-ip>:8080`, accept mobile
entries over company Wi-Fi, save every submission to SQLite first, then append a
full row into the configured production workbook.

The target workbook is reachable from the desktop and has one sheet,
`PROSES 2026`. Append logic must calculate the true last value row rather than
using `ws.max_row`, because workbook formatting can extend far beyond real data.

Key Changes
Scaffold a Python 3.14 FastAPI app with SQLite, openpyxl, Jinja/static mobile
UI, `.env` config, and a README.
Use a shared PIN login, stored in local config, with a simple session cookie.
Use a tour-context workflow: enter Tarih, Ortam Sıcaklığı, Üretim Müh.,
Vardiya Amiri, and Vardiya once, then submit fast machine rows.
Use manual machine entry; QR scanning is deferred because phone camera access
over LAN HTTP is unreliable without HTTPS.
Append full Excel rows into columns A:Y, matching the existing workbook headers.
Store MVP-only fields such as status, notes, submission timestamp, app entry ID,
and sync state in SQLite only.
Before each Excel save, create a local timestamped backup under `data/backups/`,
keeping a small rolling set such as the latest 20 backups.
If Excel writing fails because the workbook is locked, unreachable, or
permission-denied, keep the entry in SQLite as `pending_excel` and show "saved
locally, Excel pending"; provide a retry sync action.

Interfaces
Config:
EXCEL_PATH
SHEET_NAME=PROSES 2026
APP_PIN
HOST=0.0.0.0
PORT=8080
TIMEZONE=Europe/Istanbul

SQLite tables:
tour_contexts: date, ambient temp, engineer, shift chief, shift, created
timestamps.
entries: Excel column payload A:Y, SQLite-only notes/status/mold_info, sync
status, Excel row number, error message, timestamps.

Main API:
POST /api/login
GET /api/bootstrap
POST /api/tour-context
POST /api/entries
GET /api/entries
POST /api/sync/retry
GET /health

Excel mapping:
Use existing headers from A:Y: date, ambient temp, production engineer, shift
chief, shift, machine, product, work order, raw material, cavity counts,
cycle/cooling/injection/blow times, conditioner/dryer temp, injection
pressure/speed, holding values, clamp force, barrel temps, mold temps.
Parse decimal comma or decimal point inputs into numeric Excel values where
appropriate.
Treat hyphen-separated temperature/pressure strings as text where the current
workbook already uses that format.

Test Plan
Unit-test true last-row detection against a workbook copy where `ws.max_row` is
misleading.
Unit-test Excel append on a temporary copy: one entry creates the expected next
row, preserves headers, writes all mapped columns, and updates sync metadata.
Unit-test failure handling by simulating a locked/missing workbook: entry remains
in SQLite as pending and retry later succeeds.
API tests with FastAPI TestClient: login, bootstrap, tour context save, entry
submit, pending list, retry sync.
Manual acceptance test on office computer: run Uvicorn on `0.0.0.0:8080`, open
from phone via local IP, submit one machine row, confirm SQLite entry and Excel
row append.

Assumptions
MVP is single-office-computer, single FastAPI process, no multiple Uvicorn
workers.
The existing workbook structure stays unchanged; no new Excel columns are added.
The implementation will first locate Python 3.14 because `python`/`py` were not
visible on this shell PATH during inspection.
The app is LAN-only MVP software, not an IT-approved production server; firewall
and company security approval may still be needed before factory use.
