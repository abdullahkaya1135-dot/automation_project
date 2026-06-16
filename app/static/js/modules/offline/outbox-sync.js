import { setMessage } from "../utils.js?v=20260612-refactor";
import {
  flushServerExcelQueues,
} from "./server-excel-retry.js?v=20260616-offline-split";
import { updatePhoneSyncStatus } from "./status.js?v=20260616-offline-split";
import {
  markOutboxRecordsFailed,
  markOutboxRecordsSyncing,
  pendingOutboxRecordsForSync,
  queueOfflineRecord,
} from "./outbox-records.js?v=20260616-offline-split";
import {
  isValidationFailure,
  uploadOutboxBatch,
} from "./outbox-upload.js?v=20260616-offline-split";

export { queueOfflineRecord };

let offlineSyncInProgress = false;
let refreshAfterServerSave = async () => {};

export function configureOfflineRefresh(callback) {
  refreshAfterServerSave = callback || (async () => {});
}

export async function syncOutbox(_options = {}) {
  if (offlineSyncInProgress) {
    return;
  }
  offlineSyncInProgress = true;
  const message = document.querySelector("#phone-sync-message");
  let savedCount = 0;
  let failedCount = 0;
  let excelPending = false;
  let retryQueues = { process: false, auxiliary: false };

  try {
    await updatePhoneSyncStatus();
    const records = await pendingOutboxRecordsForSync();

    if (!records.length) {
      setMessage(message, "Telefonda bekleyen kay\u0131t yok.", "success");
      return;
    }

    setMessage(message, "Telefon kay\u0131tlar\u0131 sunucuya g\u00f6nderiliyor...", "");
    const syncingRecords = await markOutboxRecordsSyncing(records);

    try {
      const result = await uploadOutboxBatch(syncingRecords);
      savedCount = result.savedCount;
      failedCount = result.failedCount;
      excelPending = result.excelPending;
      retryQueues = result.retryQueues;
    } catch (error) {
      failedCount = await markOutboxRecordsFailed(
        syncingRecords,
        error,
        { validationFailed: isValidationFailure(error) },
      );
    }

    if (savedCount > 0) {
      if (excelPending) {
        await flushServerExcelQueues(retryQueues);
      }
      await refreshAfterServerSave();
    }

    updateSyncMessage(message, {
      savedCount,
      failedCount,
      excelPending,
    });
  } catch (error) {
    setMessage(message, `Telefon senkronizasyonu ba\u015far\u0131s\u0131z: ${error.message}`, "warning");
  } finally {
    offlineSyncInProgress = false;
    await updatePhoneSyncStatus();
  }
}

function updateSyncMessage(message, { savedCount, failedCount, excelPending }) {
  if (failedCount > 0) {
    setMessage(
      message,
      `${savedCount} kay\u0131t sunucuya g\u00f6nderildi, ${failedCount} kay\u0131t beklemede kald\u0131.`,
      "warning",
    );
    return;
  }
  if (excelPending) {
    setMessage(
      message,
      `${savedCount} telefon kayd\u0131 sunucuya kaydedildi. Excel senkronizasyonu bekliyor.`,
      "warning",
    );
    return;
  }
  setMessage(message, `${savedCount} telefon kayd\u0131 sunucuya g\u00f6nderildi.`, "success");
}
