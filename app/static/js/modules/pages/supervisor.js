import {
  loadAuxiliarySubmissions,
  loadEntryLists,
} from "../lists.js?v=20260612-refactor";
import {
  configureOfflineRefresh,
} from "../offline/outbox-sync.js?v=20260616-offline-split";
import {
  initializeOfflineFeatures,
  scheduleOutboxSync,
} from "../offline/service-worker-registration.js?v=20260616-offline-split";
import {
  loadExcelPendingCount,
  updatePhoneSyncStatus,
} from "../offline/status.js?v=20260616-offline-split";
import { renderLoading } from "../render/shared.js?v=20260615-render";
import { setButtonBusy } from "../utils.js?v=20260612-refactor";
import {
  loadBootstrapPayload,
  updateHeaderStatuses,
} from "../bootstrap.js?v=20260612-refactor";
import { bindPhoneSyncControls } from "./phone-sync-controls.js?v=20260616-page-controls";
import { bindSupervisorSyncControls } from "./supervisor-sync-controls.js?v=20260616-supervisor-sync";

export function initSupervisorPage() {
  bindEntryListRefresh();
  bindAuxiliaryRefresh();
  bindSupervisorSyncControls({ refreshBootstrap: loadSupervisorBootstrap });
  bindPhoneSyncControls();

  configureOfflineRefresh(async () => {
    await Promise.all([
      loadEntryLists(),
      loadAuxiliarySubmissions(),
      loadExcelPendingCount(),
      loadSupervisorBootstrap(),
    ]);
  });
  initializeOfflineFeatures();
  void initializeSupervisor();
}

async function initializeSupervisor() {
  renderLoading(document.querySelector("#recent-entries"), "Kayitlar yukleniyor...");
  renderLoading(document.querySelector("#pending-entries"), "Bekleyen kayitlar yukleniyor...");
  renderLoading(
    document.querySelector("#auxiliary-submissions"),
    "Gonderimler yukleniyor...",
  );
  await updatePhoneSyncStatus();
  await Promise.all([
    loadSupervisorBootstrap(),
    loadEntryLists(),
    loadAuxiliarySubmissions(),
    loadExcelPendingCount(),
  ]);
  scheduleOutboxSync();
}

async function loadSupervisorBootstrap() {
  const payload = await loadBootstrapPayload({
    cacheMessageSelector: "#phone-sync-message",
  });
  updateHeaderStatuses(payload);
}

function bindEntryListRefresh() {
  const refreshButton = document.querySelector("#refresh-entries");
  if (refreshButton) {
    refreshButton.addEventListener("click", async () => {
      setButtonBusy(refreshButton, true, "Yenileniyor");
      try {
        await loadEntryLists();
      } finally {
        setButtonBusy(refreshButton, false);
      }
    });
  }
}

function bindAuxiliaryRefresh() {
  const auxiliaryRefreshButton = document.querySelector("#refresh-auxiliary-submissions");
  if (auxiliaryRefreshButton) {
    auxiliaryRefreshButton.addEventListener("click", async () => {
      setButtonBusy(auxiliaryRefreshButton, true, "Yenileniyor");
      try {
        await loadAuxiliarySubmissions();
      } finally {
        setButtonBusy(auxiliaryRefreshButton, false);
      }
    });
  }
}
