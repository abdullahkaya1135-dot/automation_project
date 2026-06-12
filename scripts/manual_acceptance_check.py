from __future__ import annotations

import argparse
import json
import sys
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import HTTPCookieProcessor, Request, build_opener

from openpyxl import load_workbook
from sqlalchemy import select
from sqlalchemy.orm import selectinload

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import Settings, SettingsError, get_settings  # noqa: E402
from app.database import create_session, sqlite_health  # noqa: E402
from app.models import Entry  # noqa: E402
from app.services.excel_service import (  # noqa: E402
    INVALID_BACKUP_FILENAME_CHARS,
    check_excel_reachable,
)


def _ok(message: str) -> None:
    print(f"[OK] {message}")


def _warn(message: str) -> None:
    print(f"[WARN] {message}")


def _fail(message: str) -> None:
    print(f"[FAIL] {message}")


def _json_request(opener, url: str, *, method: str = "GET", body: dict | None = None) -> dict:
    headers = {"Accept": "application/json"}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")
    request = Request(url, data=data, headers=headers, method=method)
    with opener.open(request, timeout=5) as response:
        response_body = response.read().decode("utf-8")
    return json.loads(response_body) if response_body else {}


def check_http(base_url: str, settings: Settings) -> bool:
    success = True
    base_url = base_url.rstrip("/")
    opener = build_opener(HTTPCookieProcessor(CookieJar()))

    try:
        health = _json_request(opener, f"{base_url}/health")
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        _fail(f"App health endpoint is not reachable at {base_url}: {exc}")
        return False

    sqlite_ok = bool(health.get("sqlite", {}).get("ok"))
    _ok(f"App health is reachable; status={health.get('status')}")
    if sqlite_ok:
        _ok("Health reports SQLite as available")
    else:
        _fail(f"Health reports SQLite issue: {health.get('sqlite')}")
        success = False

    try:
        _json_request(
            opener,
            f"{base_url}/api/login",
            method="POST",
            body={"pin": settings.app_pin},
        )
        bootstrap = _json_request(opener, f"{base_url}/api/bootstrap")
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        _fail(f"Authenticated API check failed: {exc}")
        return False

    excel = bootstrap.get("excel") or {}
    _ok("Authenticated API works")
    if excel.get("available"):
        _ok("Bootstrap reports Excel as available")
    else:
        _warn(f"Bootstrap reports Excel unavailable: {excel.get('last_error')}")
    return success


def latest_entry(settings: Settings) -> Entry | None:
    with create_session(settings) as session:
        return session.scalars(
            select(Entry)
            .options(selectinload(Entry.tour_context))
            .order_by(Entry.created_at.desc(), Entry.id.desc())
        ).first()


def check_sqlite(settings: Settings) -> tuple[bool, Entry | None]:
    health = sqlite_health(settings)
    if not health.get("ok"):
        _fail(f"SQLite health check failed: {health.get('error')}")
        return False, None

    _ok(f"SQLite database is available at {settings.sqlite_path}")
    entry = latest_entry(settings)
    if entry is None:
        _fail("No SQLite entry found. Submit one machine row before final acceptance.")
        return False, None

    _ok(
        "Latest SQLite entry "
        f"id={entry.id}, machine={entry.col_f}, "
        f"work_order={entry.col_g}, sync_status={entry.sync_status}"
    )
    if entry.last_error:
        _warn(f"Latest entry sync error: {entry.last_error}")
    return True, entry


def check_excel(settings: Settings, entry: Entry | None, expected_row: int | None) -> bool:
    status = check_excel_reachable(settings)
    if not status.available:
        if expected_row is not None:
            _fail(f"Excel is unavailable, so row {expected_row} cannot be verified: {status.error}")
            return False
        _warn(f"Excel is unavailable: {status.error}")
        return True

    _ok("Excel workbook is reachable")
    if entry is None:
        return False
    if entry.excel_row_number is None:
        if expected_row is not None:
            _fail(f"Latest entry is not synced to expected Excel row {expected_row}")
            return False
        _warn("Latest entry is not synced to Excel yet")
        return True

    success = True
    if expected_row is not None and entry.excel_row_number != expected_row:
        _fail(
            f"Latest entry Excel row is {entry.excel_row_number}; "
            f"expected {expected_row}"
        )
        success = False
    else:
        _ok(f"Latest entry recorded Excel row {entry.excel_row_number}")

    workbook = load_workbook(settings.excel_path, read_only=True, data_only=True)
    try:
        if settings.sheet_name not in workbook.sheetnames:
            _fail(f"Sheet was not found: {settings.sheet_name}")
            return False
        worksheet = workbook[settings.sheet_name]
        row = next(
            worksheet.iter_rows(
                min_row=entry.excel_row_number,
                max_row=entry.excel_row_number,
                max_col=8,
                values_only=True,
            )
        )
    finally:
        workbook.close()

    if row[5] == entry.col_f and row[7] == entry.col_g:
        _ok("Excel row matches the latest SQLite machine and work order")
    else:
        _fail(
            "Excel row does not match SQLite. "
            f"Excel F:H={row[5:8]}, SQLite F/H={(entry.col_f, entry.col_g)}"
        )
        success = False
    return success


def check_backups(settings: Settings) -> bool:
    backup_dir = Path(settings.backup_dir)
    if not backup_dir.exists():
        _fail(f"Backup directory does not exist: {backup_dir}")
        return False

    source_path = Path(settings.excel_path)
    safe_stem = INVALID_BACKUP_FILENAME_CHARS.sub("_", source_path.stem).strip()
    if not safe_stem:
        safe_stem = "workbook"
    pattern = f"{safe_stem}_*{source_path.suffix or '.xlsx'}"
    backups = sorted(backup_dir.glob(pattern), key=lambda path: path.stat().st_mtime)

    if not backups:
        _fail(f"No timestamped backup found in {backup_dir}")
        return False

    newest = backups[-1]
    _ok(f"Newest backup: {newest.name}")
    if len(backups) <= settings.backup_keep_count:
        _ok(
            f"Backup retention is within limit: "
            f"{len(backups)}/{settings.backup_keep_count}"
        )
        return True

    _fail(
        f"Backup retention exceeded: {len(backups)} files for "
        f"keep_count={settings.backup_keep_count}"
    )
    return False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Verify the manual acceptance state after an operator submits one "
            "machine row through the running FastAPI app."
        )
    )
    parser.add_argument(
        "--url",
        default="http://127.0.0.1:8080",
        help="Base URL for the running app.",
    )
    parser.add_argument(
        "--expected-row",
        type=int,
        default=None,
        help="Expected Excel row for the latest synced entry, for example 1726.",
    )
    parser.add_argument(
        "--skip-http",
        action="store_true",
        help="Skip health/login/bootstrap checks against the running app.",
    )
    parser.add_argument(
        "--skip-backups",
        action="store_true",
        help="Skip backup directory and retention checks.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    checks: list[bool] = []

    try:
        settings = get_settings()
    except SettingsError as exc:
        _fail(str(exc))
        return 1

    _ok("Runtime settings loaded")
    if not args.skip_http:
        checks.append(check_http(args.url, settings))

    sqlite_ok, entry = check_sqlite(settings)
    checks.append(sqlite_ok)
    checks.append(check_excel(settings, entry, args.expected_row))
    if not args.skip_backups:
        checks.append(check_backups(settings))

    if all(checks):
        _ok("Manual acceptance checks passed")
        return 0

    _fail("Manual acceptance checks need attention")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
