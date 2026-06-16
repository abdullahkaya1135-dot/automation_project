# Offline Sync

## Safety Model

SQLite is the system of record. Phone submissions are never required to reach
Excel before they are accepted by the server.

The phone stores outbox records in IndexedDB. When connectivity returns, the
browser sends those records to:

```text
POST /api/offline/bulk-sync
```

The server then:

1. Validates the bulk envelope.
2. Processes records in client creation order.
3. Saves or replays tour contexts using `client_request_id`.
4. Resolves local phone dependencies such as an entry depending on a locally
   created tour context.
5. Saves process entries and auxiliary submissions to SQLite.
6. Commits SQLite before touching Excel.
7. Syncs Excel in batches when `sync_excel` is true.
8. Returns one result per phone outbox record so IndexedDB can store the server
   id and final server status.

## Batch Excel Behavior

Process entries use `append_entries_to_workbook`. A batch:

- Acquires the Excel write lock once.
- Opens the process workbook once.
- Validates `A:Y` headers once.
- Finds the real last data row once.
- Creates one backup if new rows need appending.
- Writes all pending rows sequentially.
- Saves once.
- Updates SQLite `sync_status`, `excel_row_number`, `last_error`, and
  `synced_at`.

Auxiliary submissions use `append_auxiliary_submissions_to_workbook`. A batch:

- Acquires the Excel write lock once.
- Opens the auxiliary workbook once.
- Validates `A:I` headers once.
- Writes each submission as one 15-row block.
- Creates one backup and saves once for the whole batch.
- Updates SQLite `excel_start_row` and `excel_end_row`.

## Idempotency

Every offline record should carry `client_request_id`.

Replaying the same batch must not duplicate SQLite rows. For failed Excel retry
paths, the batch writers can reuse existing matching Excel rows before appending
new rows. This protects the common partial-success case where Excel was saved
but SQLite status was not updated.

## Failure Behavior

If Excel is missing, locked, permission-denied, or structurally invalid:

- SQLite rows remain saved.
- Process entries remain `pending_excel` during offline bulk sync or become
  `failed_excel` during supervisor retry.
- Auxiliary submissions follow the same pending/failed distinction.
- `last_error` stores the workbook error.
- The supervisor retry controls can be used after workbook access is restored.

## Regression Tests

Tests should count expensive workbook operations rather than assert elapsed
time. Important checks:

- Many process entries use one workbook open/save/backup.
- Many auxiliary submissions use one workbook open/save/backup.
- Row numbers or block ranges are sequential and unique.
- Replaying a batch does not duplicate SQLite or Excel rows.
- Excel unavailable still leaves SQLite rows saved.
- Legacy single-record endpoints keep working.

The manual verifier can exercise both batch paths against copied workbooks:

```powershell
python scripts\manual_acceptance_check.py --exercise-bulk-sync 1 --exercise-auxiliary-retry 3 --check-role-pages
```
