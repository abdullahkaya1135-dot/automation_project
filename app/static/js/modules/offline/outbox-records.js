import {
  OFFLINE_STATUS_QUEUED,
  OFFLINE_STATUS_RETRYABLE,
  OFFLINE_STATUS_SYNCING,
  OFFLINE_STATUS_VALIDATION_FAILED,
} from "./constants.js?v=20260616-offline-split";
import { createClientRequestId } from "../utils.js?v=20260612-refactor";
import {
  getAllOfflineRecords,
  putOfflineRecord,
  updateOfflineRecordsBulk,
} from "./outbox-db.js?v=20260616-offline-split";
import { updatePhoneSyncStatus } from "./status.js?v=20260616-offline-split";

const PENDING_SYNC_STATUSES = new Set([
  OFFLINE_STATUS_QUEUED,
  OFFLINE_STATUS_RETRYABLE,
  OFFLINE_STATUS_SYNCING,
]);

export async function queueOfflineRecord(type, body, dependsOnClientRequestId = null) {
  const now = new Date().toISOString();
  const clientRequestId = body.client_request_id || createClientRequestId();
  body.client_request_id = clientRequestId;
  const record = {
    client_request_id: clientRequestId,
    type,
    body,
    depends_on_client_request_id: dependsOnClientRequestId,
    status: OFFLINE_STATUS_QUEUED,
    attempt_count: 0,
    last_error: null,
    server_id: null,
    created_at: now,
    updated_at: now,
  };
  await putOfflineRecord(record);
  await updatePhoneSyncStatus();
  return record;
}

export async function pendingOutboxRecordsForSync() {
  return (await getAllOfflineRecords())
    .filter((record) => PENDING_SYNC_STATUSES.has(record.status));
}

export async function markOutboxRecordsSyncing(records) {
  const syncingUpdates = {};
  for (const record of records) {
    syncingUpdates[record.client_request_id] = {
      status: OFFLINE_STATUS_SYNCING,
      attempt_count: Number(record.attempt_count || 0) + 1,
      last_error: null,
    };
  }
  await updateOfflineRecordsBulk(syncingUpdates);
  return records.map((record) => ({
    ...record,
    ...syncingUpdates[record.client_request_id],
  }));
}

export async function markOutboxRecordsFailed(records, error, { validationFailed = false } = {}) {
  const failureStatus = validationFailed
    ? OFFLINE_STATUS_VALIDATION_FAILED
    : OFFLINE_STATUS_RETRYABLE;
  const failureUpdates = {};
  for (const record of records) {
    failureUpdates[record.client_request_id] = {
      status: failureStatus,
      last_error: error.message || "Ba\u011flant\u0131 hatas\u0131",
    };
  }
  await updateOfflineRecordsBulk(failureUpdates);
  return records.length;
}
