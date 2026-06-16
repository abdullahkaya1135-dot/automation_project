import { setButtonBusy } from "../utils.js?v=20260612-refactor";
import { syncOutbox } from "./outbox-sync.js?v=20260616-offline-split";

let offlineSyncTimer = null;

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

function registerServiceWorker() {
  if (!("serviceWorker" in navigator) || !window.isSecureContext) {
    return;
  }
  navigator.serviceWorker.register("/service-worker.js").catch(() => {
    // Offline capture still works through IndexedDB if PWA caching cannot register.
  });
}
