# Manual Acceptance

Use safe workbook copies unless explicitly validating production paths.

## Required Checks

Run before manual testing:

```powershell
python -m pytest
python -m ruff check .
python -m mypy app tests
```

Start the app:

```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

Open:

```text
http://127.0.0.1:8080
```

## Role Pages

With `APP_ROLE_PINS` configured:

1. Log in as operator and confirm `/operator` opens.
2. Confirm operator sees tour context, machine entry, and phone sync.
3. Confirm operator cannot open `/supervisor`.
4. Log in as utility and confirm `/utility` shows the auxiliary form.
5. Log in as supervisor and confirm retry controls and pending lists are visible.
6. Log in as planning and confirm cycle report and IFS return candidate tools
   are visible.
7. Log in as admin and confirm all workspaces can be opened.

## Offline Bulk Sync

1. Open `/operator` from a phone.
2. Save one tour context while online.
3. Disconnect the phone from the office network.
4. Create many machine entries.
5. Reconnect the phone.
6. Press `Sync` once.
7. Confirm the browser sends one `POST /api/offline/bulk-sync`.
8. Confirm all entries exist in SQLite.
9. Confirm Excel row numbers are sequential.
10. Confirm one process workbook backup exists for the batch.
11. Press `Sync` again and confirm no duplicate Excel rows appear.

## Excel Unavailable

1. Point `EXCEL_PATH` at a missing or locked workbook copy.
2. Submit a machine entry.
3. Confirm the API returns local-save success with Excel pending.
4. Confirm SQLite contains the entry and `excel_row_number` is empty.
5. Restore workbook access.
6. Log in as supervisor.
7. Press process retry.
8. Confirm the entry becomes `synced` with a row number.

## Auxiliary Batch Retry

1. Queue multiple auxiliary submissions while the auxiliary workbook is
   unavailable.
2. Restore workbook access.
3. Log in as supervisor.
4. Press auxiliary retry.
5. Confirm submissions become `synced`.
6. Confirm each submission has a sequential 15-row block.
7. Confirm one auxiliary workbook backup exists for the batch.

## Scripted Check

For the latest synced process entry:

```powershell
python scripts\manual_acceptance_check.py --expected-row 1726
```

Omit `--expected-row` when testing against a fresh workbook copy whose next row
is not known.

To also verify role workspace access:

```powershell
python scripts\manual_acceptance_check.py --check-role-pages
```

After an offline dump, pass the number of machine entries that were synced:

```powershell
python scripts\manual_acceptance_check.py --latest-batch-size 50
```

The batch check verifies the latest SQLite entries are `synced`, have unique
sequential Excel row numbers, and still match the workbook machine/work-order
cells.

For a safe-copy dry run that creates and verifies a new bulk batch through the
running API:

```powershell
python scripts\manual_acceptance_check.py --exercise-bulk-sync 50 --check-role-pages
```

This posts one `/api/offline/bulk-sync` request, verifies one new process
workbook backup, then replays the same batch to confirm no duplicate SQLite or
Excel rows are created. Use this only with copied workbooks and a test SQLite
database.

For a safe-copy dry run of the auxiliary retry batch path, use:

```powershell
python scripts\manual_acceptance_check.py --exercise-bulk-sync 1 --exercise-auxiliary-retry 3 --check-role-pages
```

This queues auxiliary submissions through offline bulk sync with Excel disabled,
then calls `POST /api/auxiliary-systems/sync/retry`. The verifier confirms the
queue step creates no workbook backup, the retry creates exactly one auxiliary
backup, and the latest submissions occupy sequential 15-row Excel blocks. The
auxiliary exercise requires a clean auxiliary pending queue.
