export const OFFLINE_DB_NAME = "process-offline-v1";
export const OFFLINE_DB_VERSION = 1;
export const OFFLINE_STATUS_QUEUED = "queued";
export const OFFLINE_STATUS_SYNCING = "syncing";
export const OFFLINE_STATUS_RETRYABLE = "retryable";
export const OFFLINE_STATUS_SERVER_SAVED = "server_saved";
export const OFFLINE_STATUS_VALIDATION_FAILED = "validation_failed";
export const OFFLINE_PENDING_STATUSES = new Set([
  OFFLINE_STATUS_QUEUED,
  OFFLINE_STATUS_SYNCING,
  OFFLINE_STATUS_RETRYABLE,
  OFFLINE_STATUS_VALIDATION_FAILED,
]);
