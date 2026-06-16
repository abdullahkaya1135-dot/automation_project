import { apiJson } from "../../api.js?v=20260612-refactor";

export function pendingExcelQueuesFromBulkResponse(payload) {
  const queues = { process: false, auxiliary: false };
  for (const result of payload.records || []) {
    if (result.synced_to_excel !== false) {
      continue;
    }
    if (result.type === "entry") {
      queues.process = true;
    }
    if (result.type === "auxiliary_submission") {
      queues.auxiliary = true;
    }
  }

  if (payload.excel_pending && !queues.process && !queues.auxiliary) {
    queues.process = true;
    queues.auxiliary = true;
  }
  return queues;
}

export async function flushServerExcelQueues(queues) {
  const retryRequests = [];
  if (queues.process) {
    retryRequests.push(apiJson("/api/sync/retry", {
      method: "POST",
      redirectOnAuth: false,
    }));
  }
  if (queues.auxiliary) {
    retryRequests.push(apiJson("/api/auxiliary-systems/sync/retry", {
      method: "POST",
      redirectOnAuth: false,
    }));
  }
  if (!retryRequests.length) {
    return;
  }
  await Promise.allSettled(retryRequests);
}
