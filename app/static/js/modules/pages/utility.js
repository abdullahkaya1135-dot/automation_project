import { loadAuxiliarySubmissions } from "../lists.js?v=20260612-refactor";
import {
  initializeOfflineFeatures,
  scheduleOutboxSync,
} from "../offline/service-worker-registration.js?v=20260616-offline-split";
import { renderLoading } from "../render/shared.js?v=20260615-render";
import {
  setButtonBusy,
  setMessage,
} from "../utils.js?v=20260612-refactor";
import {
  applyAuxiliaryDate,
  loadBootstrapPayload,
  updateHeaderStatuses,
} from "../bootstrap.js?v=20260612-refactor";
import { handleAuxiliarySubmit } from "./utility-auxiliary.js?v=20260616-utility-forms";

export function initUtilityPage() {
  const auxiliaryForm = document.querySelector("#auxiliary-form");
  if (!auxiliaryForm) {
    return;
  }

  auxiliaryForm.addEventListener("submit", handleAuxiliarySubmit);
  bindAuxiliaryRefresh();
  initializeOfflineFeatures();
  void initializeUtility();
}

async function initializeUtility() {
  renderLoading(
    document.querySelector("#auxiliary-submissions"),
    "Gonderimler yukleniyor...",
  );
  try {
    await loadUtilityBootstrap();
  } catch (error) {
    setMessage(
      document.querySelector("#auxiliary-message"),
      `Baslatma basarisiz: ${error.message}`,
      "error",
    );
  }
  await loadAuxiliarySubmissions();
  scheduleOutboxSync();
}

async function loadUtilityBootstrap() {
  const payload = await loadBootstrapPayload();
  updateHeaderStatuses(payload);
  applyAuxiliaryDate(payload.current_auxiliary_date);
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
