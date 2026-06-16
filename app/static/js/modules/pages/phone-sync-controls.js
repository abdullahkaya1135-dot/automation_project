import { exportOfflineOutbox } from "../offline/outbox-export.js?v=20260616-offline-split";
import { handlePhoneOutboxSync } from "../offline/service-worker-registration.js?v=20260616-offline-split";

export function bindPhoneSyncControls() {
  const phoneSyncButton = document.querySelector("#sync-phone-outbox");
  if (phoneSyncButton) {
    phoneSyncButton.addEventListener("click", handlePhoneOutboxSync);
  }

  const exportJsonButton = document.querySelector("#export-offline-json");
  if (exportJsonButton) {
    exportJsonButton.addEventListener("click", () => {
      void exportOfflineOutbox("json");
    });
  }

  const exportCsvButton = document.querySelector("#export-offline-csv");
  if (exportCsvButton) {
    exportCsvButton.addEventListener("click", () => {
      void exportOfflineOutbox("csv");
    });
  }
}
