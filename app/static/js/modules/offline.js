import { ApiError, apiJson } from "../api.js?v=20260626-breakdown-context-v2";
import {
  OFFLINE_DB_NAME,
  OFFLINE_DB_VERSION,
  OFFLINE_PENDING_STATUSES,
  OFFLINE_STATUS_QUEUED,
  OFFLINE_STATUS_RETRYABLE,
  OFFLINE_STATUS_SERVER_SAVED,
  OFFLINE_STATUS_SYNCING,
  OFFLINE_STATUS_VALIDATION_FAILED,
} from "./constants.js?v=20260626-breakdown-context-v2";
import {
  applyTourContext,
  readStoredTourContext,
  storeTourContext,
} from "./tour-context.js?v=20260626-breakdown-context-v2";
import {
  createClientRequestId,
  downloadTextFile,
  setButtonBusy,
  setMessage,
  updateStatusPill,
} from "./utils.js?v=20260626-breakdown-context-v2";

let offlineDbPromise = null;
let offlineSyncInProgress = false;
let offlineSyncTimer = null;
let refreshAfterServerSave = async () => {};

export function configureOfflineRefresh(callback) {
  refreshAfterServerSave = callback || (async () => {});
}

export function initializeOfflineFeatures() {
  registerServiceWorker();
  window.addEventListener("online", () => {
    scheduleOutboxSync();
  });
  window.addEventListener("focus", () => {
    scheduleOutboxSync();
  });
}

export function scheduleOutboxSync() {
  window.clearTimeout(offlineSyncTimer);
  offlineSyncTimer = window.setTimeout(() => {
    void syncOutbox({ reason: "scheduled" });
  }, 500);
}

export async function handlePhoneOutboxSync(event) {
  const button = event.currentTarget;
  setButtonBusy(button, true, "Senkronize ediliyor");
  try {
    await syncOutbox({ reason: "manual" });
  } finally {
    setButtonBusy(button, false);
  }
}

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

export async function writeBootstrapCache(payload) {
  const db = await openOfflineDb();
  return new Promise((resolve, reject) => {
    const transaction = db.transaction("bootstrap_cache", "readwrite");
    transaction.objectStore("bootstrap_cache").put({
      key: "latest",
      payload,
      updated_at: new Date().toISOString(),
    });
    transaction.oncomplete = () => resolve();
    transaction.onerror = () => reject(transaction.error || new Error("Bootstrap Ã¶nbelleÄŸi yazÄ±lamadÄ±."));
  });
}

export async function readBootstrapCache() {
  const db = await openOfflineDb();
  const transaction = db.transaction("bootstrap_cache", "readonly");
  return idbRequest(transaction.objectStore("bootstrap_cache").get("latest"));
}

export async function syncOutbox(_options = {}) {
  if (offlineSyncInProgress) {
    return;
  }
  offlineSyncInProgress = true;
  const message = document.querySelector("#phone-sync-message");
  let savedCount = 0;
  let failedCount = 0;
  let skippedCount = 0;

  try {
    await updatePhoneSyncStatus();
    const records = (await getAllOfflineRecords())
      .filter((record) => [
        OFFLINE_STATUS_QUEUED,
        OFFLINE_STATUS_RETRYABLE,
        OFFLINE_STATUS_SYNCING,
      ].includes(record.status));

    if (!records.length) {
      setMessage(message, "Telefonda bekleyen kayÄ±t yok.", "success");
      return;
    }

    setMessage(message, "Telefon kayÄ±tlarÄ± sunucuya gÃ¶nderiliyor...", "");
    for (const record of records) {
      const body = await syncBodyForRecord(record);
      if (!body) {
        skippedCount += 1;
        continue;
      }

      const syncingRecord = await updateOfflineRecord(record.client_request_id, {
        status: OFFLINE_STATUS_SYNCING,
        attempt_count: Number(record.attempt_count || 0) + 1,
        last_error: null,
      });

      try {
        const payload = await postOfflineRecord(syncingRecord || record, body);
        const serverId = serverIdFromSyncPayload(record.type, payload);
        await updateOfflineRecord(record.client_request_id, {
          status: OFFLINE_STATUS_SERVER_SAVED,
          server_id: serverId,
          last_error: null,
        });
        applyServerResultToUi(record, payload);
        savedCount += 1;
      } catch (error) {
        failedCount += 1;
        if (error instanceof ApiError && error.status === 422) {
          await updateOfflineRecord(record.client_request_id, {
            status: OFFLINE_STATUS_VALIDATION_FAILED,
            last_error: error.message,
          });
          continue;
        }

        await updateOfflineRecord(record.client_request_id, {
          status: OFFLINE_STATUS_RETRYABLE,
          last_error: error.message || "BaÄŸlantÄ± hatasÄ±",
        });
        break;
      }
    }

    if (savedCount > 0) {
      await flushServerExcelQueues();
      await refreshAfterServerSave();
    }

    if (failedCount > 0) {
      setMessage(
        message,
        `${savedCount} kayÄ±t sunucuya gÃ¶nderildi, ${failedCount} kayÄ±t beklemede kaldÄ±.`,
        "warning",
      );
    } else if (skippedCount > 0) {
      setMessage(
        message,
        `${savedCount} kayÄ±t gÃ¶nderildi. ${skippedCount} kayÄ±t Ã¶nce tur senkronizasyonunu bekliyor.`,
        "warning",
      );
    } else {
      setMessage(message, `${savedCount} telefon kaydÄ± sunucuya gÃ¶nderildi.`, "success");
    }
  } catch (error) {
    setMessage(message, `Telefon senkronizasyonu baÅŸarÄ±sÄ±z: ${error.message}`, "warning");
  } finally {
    offlineSyncInProgress = false;
    await updatePhoneSyncStatus();
  }
}

export async function updatePhoneSyncStatus() {
  const pendingStatus = document.querySelector("#phone-pending-count");
  const serverStatus = document.querySelector("#phone-server-saved-count");
  try {
    const records = await getAllOfflineRecords();
    const pendingCount = records.filter((record) => OFFLINE_PENDING_STATUSES.has(record.status)).length;
    const serverSavedCount = records.filter((record) => record.status === OFFLINE_STATUS_SERVER_SAVED).length;
    updateStatusPill(
      pendingStatus,
      `Telefon bekleyen: ${pendingCount}`,
      pendingCount ? "warning" : "success",
    );
    updateStatusPill(serverStatus, `Sunucuya kaydedilen: ${serverSavedCount}`, "success");
  } catch (error) {
    updateStatusPill(pendingStatus, "Telefon veritabanÄ± yok", "error");
    updateStatusPill(serverStatus, error.message, "error");
  }
}

export async function loadExcelPendingCount() {
  const excelStatus = document.querySelector("#excel-pending-count");
  if (!excelStatus) {
    return;
  }
  try {
    const [
      pendingEntries,
      failedEntries,
      pendingAuxiliary,
      failedAuxiliary,
    ] = await Promise.all([
      apiJson("/api/entries?sync_status=pending_excel&limit=200"),
      apiJson("/api/entries?sync_status=failed_excel&limit=200"),
      apiJson("/api/auxiliary-systems/submissions?sync_status=pending_excel&limit=200"),
      apiJson("/api/auxiliary-systems/submissions?sync_status=failed_excel&limit=200"),
    ]);
    const count = [
      ...(pendingEntries.entries || []),
      ...(failedEntries.entries || []),
      ...(pendingAuxiliary.submissions || []),
      ...(failedAuxiliary.submissions || []),
    ].length;
    updateStatusPill(excelStatus, `Excel bekleyen: ${count}`, count ? "warning" : "success");
  } catch (_error) {
    updateStatusPill(excelStatus, "Excel bekleyen: offline", "warning");
  }
}

export async function exportOfflineOutbox(format) {
  const records = await getAllOfflineRecords();
  if (format === "csv") {
    downloadTextFile("telefon-bekleyen-kayitlar.csv", offlineRecordsCsv(records), "text/csv");
    return;
  }
  downloadTextFile(
    "telefon-bekleyen-kayitlar.json",
    JSON.stringify(records, null, 2),
    "application/json",
  );
}

function registerServiceWorker() {
  if (!("serviceWorker" in navigator) || !window.isSecureContext) {
    return;
  }
  navigator.serviceWorker.register("/service-worker.js").catch(() => {
    // Offline capture still works through IndexedDB if PWA caching cannot register.
  });
}

function openOfflineDb() {
  if (offlineDbPromise) {
    return offlineDbPromise;
  }
  if (!("indexedDB" in window)) {
    offlineDbPromise = Promise.reject(new Error("Bu tarayÄ±cÄ± IndexedDB desteklemiyor."));
    return offlineDbPromise;
  }

  offlineDbPromise = new Promise((resolve, reject) => {
    const request = indexedDB.open(OFFLINE_DB_NAME, OFFLINE_DB_VERSION);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains("outbox")) {
        const outbox = db.createObjectStore("outbox", {
          keyPath: "client_request_id",
        });
        outbox.createIndex("status", "status", { unique: false });
        outbox.createIndex("type", "type", { unique: false });
        outbox.createIndex("created_at", "created_at", { unique: false });
      }
      if (!db.objectStoreNames.contains("meta")) {
        db.createObjectStore("meta", { keyPath: "key" });
      }
      if (!db.objectStoreNames.contains("bootstrap_cache")) {
        db.createObjectStore("bootstrap_cache", { keyPath: "key" });
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error || new Error("Telefon veritabanÄ± aÃ§Ä±lamadÄ±."));
  });
  return offlineDbPromise;
}

function idbRequest(request) {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error || new Error("Telefon veritabanÄ± isteÄŸi baÅŸarÄ±sÄ±z."));
  });
}

async function getOfflineRecord(clientRequestId) {
  const db = await openOfflineDb();
  const transaction = db.transaction("outbox", "readonly");
  return idbRequest(transaction.objectStore("outbox").get(clientRequestId));
}

async function getAllOfflineRecords() {
  const db = await openOfflineDb();
  const transaction = db.transaction("outbox", "readonly");
  const records = await idbRequest(transaction.objectStore("outbox").getAll());
  return records.sort((left, right) => String(left.created_at).localeCompare(String(right.created_at)));
}

async function putOfflineRecord(record) {
  const db = await openOfflineDb();
  return new Promise((resolve, reject) => {
    const transaction = db.transaction("outbox", "readwrite");
    transaction.objectStore("outbox").put(record);
    transaction.oncomplete = () => resolve(record);
    transaction.onerror = () => reject(transaction.error || new Error("Telefon kaydÄ± yazÄ±lamadÄ±."));
  });
}

async function updateOfflineRecord(clientRequestId, updates) {
  const record = await getOfflineRecord(clientRequestId);
  if (!record) {
    return null;
  }
  const updated = {
    ...record,
    ...updates,
    updated_at: new Date().toISOString(),
  };
  await putOfflineRecord(updated);
  return updated;
}

async function syncBodyForRecord(record) {
  const body = { ...(record.body || {}) };
  if (record.type !== "entry" || !record.depends_on_client_request_id) {
    return body;
  }

  const dependency = await getOfflineRecord(record.depends_on_client_request_id);
  if (!dependency || !dependency.server_id) {
    return null;
  }
  body.tour_context_id = dependency.server_id;
  return body;
}

async function postOfflineRecord(record, body) {
  const endpoint = offlineEndpointForType(record.type);
  return apiJson(endpoint, {
    method: "POST",
    body,
    redirectOnAuth: false,
  });
}

function offlineEndpointForType(type) {
  if (type === "tour_context") {
    return "/api/tour-context";
  }
  if (type === "entry") {
    return "/api/entries";
  }
  if (type === "auxiliary_submission") {
    return "/api/auxiliary-systems/submissions";
  }
  if (type === "amount_control_shift") {
    return "/api/amount-control/shifts";
  }
  if (type === "breakdown") {
    return "/api/breakdowns";
  }
  throw new Error(`Bilinmeyen telefon kayÄ±t tipi: ${type}`);
}

function serverIdFromSyncPayload(type, payload) {
  if (type === "tour_context") {
    return payload?.tour_context?.id || payload?.id || null;
  }
  if (type === "entry") {
    return payload?.entry?.id || null;
  }
  if (type === "auxiliary_submission") {
    return payload?.submission?.id || null;
  }
  if (type === "amount_control_shift") {
    return payload?.shift?.id || payload?.id || null;
  }
  if (type === "breakdown") {
    return payload?.breakdown?.id || payload?.id || null;
  }
  return null;
}

function applyServerResultToUi(record, payload) {
  if (record.type !== "tour_context" || !payload?.tour_context) {
    return;
  }
  const activeContext = readStoredTourContext();
  if (activeContext?.client_request_id !== record.client_request_id) {
    return;
  }
  applyTourContext(payload.tour_context);
  storeTourContext(payload.tour_context);
  setMessage(
    document.querySelector("#tour-context-message"),
    "Tur bilgileri sunucuya kaydedildi.",
    "success",
  );
}

async function flushServerExcelQueues() {
  await Promise.allSettled([
    apiJson("/api/auxiliary-systems/sync/retry", {
      method: "POST",
      redirectOnAuth: false,
    }),
  ]);
}

function offlineRecordsCsv(records) {
  const rows = [
    [
      "client_request_id",
      "type",
      "status",
      "attempt_count",
      "server_id",
      "created_at",
      "updated_at",
      "last_error",
      "body_json",
    ],
    ...records.map((record) => [
      record.client_request_id,
      record.type,
      record.status,
      record.attempt_count,
      record.server_id,
      record.created_at,
      record.updated_at,
      record.last_error,
      JSON.stringify(record.body || {}),
    ]),
  ];
  return rows.map((row) => row.map(csvCell).join(",")).join("\n");
}

function csvCell(value) {
  const text = value == null ? "" : String(value);
  return `"${text.replaceAll('"', '""')}"`;
}
