import { ApiError, apiJson } from "../../api.js?v=20260612-refactor";
import {
  OFFLINE_STATUS_RETRYABLE,
  OFFLINE_STATUS_SERVER_SAVED,
} from "./constants.js?v=20260616-offline-split";
import { updateOfflineRecordsBulk } from "./outbox-db.js?v=20260616-offline-split";
import {
  applyServerResultToUi,
  resultPayloadForRecord,
} from "./outbox-results.js?v=20260616-offline-split";
import { pendingExcelQueuesFromBulkResponse } from "./server-excel-retry.js?v=20260616-offline-split";

export function isValidationFailure(error) {
  return error instanceof ApiError && error.status === 422;
}

export async function uploadOutboxBatch(syncingRecords) {
  const payload = await apiJson("/api/offline/bulk-sync", {
    method: "POST",
    body: {
      records: syncingRecords.map(bulkRecordForUpload),
      sync_excel: true,
    },
    redirectOnAuth: false,
  });
  const resultByClientId = new Map(
    (payload.records || [])
      .filter((result) => result.client_request_id)
      .map((result) => [result.client_request_id, result]),
  );
  const retryQueues = pendingExcelQueuesFromBulkResponse(payload);
  const savedUpdates = {};
  let savedCount = 0;
  let failedCount = 0;
  for (const record of syncingRecords) {
    const result = resultByClientId.get(record.client_request_id);
    if (!result) {
      failedCount += 1;
      savedUpdates[record.client_request_id] = {
        status: OFFLINE_STATUS_RETRYABLE,
        last_error: "Sunucu bu kay\u0131t i\u00e7in sonu\u00e7 d\u00f6nd\u00fcrmedi.",
      };
      continue;
    }
    savedUpdates[record.client_request_id] = {
      status: OFFLINE_STATUS_SERVER_SAVED,
      server_id: result.server_id || null,
      last_error: result.synced_to_excel === false ? payload.excel_error : null,
    };
    applyServerResultToUi(record, resultPayloadForRecord(result));
    savedCount += 1;
  }
  await updateOfflineRecordsBulk(savedUpdates);
  return {
    savedCount,
    failedCount,
    excelPending: Boolean(payload.excel_pending),
    retryQueues,
  };
}

function bulkRecordForUpload(record) {
  return {
    type: record.type,
    client_request_id: record.client_request_id,
    depends_on_client_request_id: record.depends_on_client_request_id || null,
    client_recorded_at: record.body?.client_recorded_at || null,
    body: record.body || {},
  };
}
