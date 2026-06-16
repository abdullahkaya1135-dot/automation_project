import {
  OFFLINE_DB_NAME,
  OFFLINE_DB_VERSION,
} from "./constants.js?v=20260616-offline-split";

let offlineDbPromise = null;

export function openOfflineDb() {
  if (offlineDbPromise) {
    return offlineDbPromise;
  }
  if (!("indexedDB" in window)) {
    offlineDbPromise = Promise.reject(new Error("Bu taray\u0131c\u0131 IndexedDB desteklemiyor."));
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
    request.onerror = () => reject(request.error || new Error("Telefon veritaban\u0131 a\u00e7\u0131lamad\u0131."));
  });
  return offlineDbPromise;
}

export function idbRequest(request) {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error || new Error("Telefon veritaban\u0131 iste\u011fi ba\u015far\u0131s\u0131z."));
  });
}

export async function getAllOfflineRecords() {
  const db = await openOfflineDb();
  const transaction = db.transaction("outbox", "readonly");
  const records = await idbRequest(transaction.objectStore("outbox").getAll());
  return records.sort((left, right) => String(left.created_at).localeCompare(String(right.created_at)));
}

export async function putOfflineRecord(record) {
  const db = await openOfflineDb();
  return new Promise((resolve, reject) => {
    const transaction = db.transaction("outbox", "readwrite");
    transaction.objectStore("outbox").put(record);
    transaction.oncomplete = () => resolve(record);
    transaction.onerror = () => reject(transaction.error || new Error("Telefon kayd\u0131 yaz\u0131lamad\u0131."));
  });
}

export async function updateOfflineRecordsBulk(updatesByClientRequestId) {
  const entries = Object.entries(updatesByClientRequestId);
  if (!entries.length) {
    return;
  }
  const db = await openOfflineDb();
  return new Promise((resolve, reject) => {
    const transaction = db.transaction("outbox", "readwrite");
    const store = transaction.objectStore("outbox");
    const now = new Date().toISOString();
    for (const [clientRequestId, updates] of entries) {
      const request = store.get(clientRequestId);
      request.onsuccess = () => {
        const record = request.result;
        if (!record) {
          return;
        }
        store.put({
          ...record,
          ...updates,
          updated_at: now,
        });
      };
      request.onerror = () => transaction.abort();
    }
    transaction.oncomplete = () => resolve();
    transaction.onerror = () => reject(transaction.error || new Error("Telefon kay\u0131tlar\u0131 g\u00fcncellenemedi."));
    transaction.onabort = () => reject(transaction.error || new Error("Telefon kay\u0131tlar\u0131 g\u00fcncellenemedi."));
  });
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
    transaction.onerror = () => reject(transaction.error || new Error("Bootstrap \u00f6nbelle\u011fi yaz\u0131lamad\u0131."));
  });
}

export async function readBootstrapCache() {
  const db = await openOfflineDb();
  const transaction = db.transaction("bootstrap_cache", "readonly");
  return idbRequest(transaction.objectStore("bootstrap_cache").get("latest"));
}
