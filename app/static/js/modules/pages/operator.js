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
import {
  initializeShopOrderDropdowns,
  updateShopOrderOptions,
} from "../shop-orders/dropdowns.js?v=20260615-shop-orders";
import { initializeTemperatureShorthandInputs } from "../temperature.js?v=20260612-refactor";
import {
  applyAutomaticTourTiming,
  applyTourContext,
  clearStoredTourContext,
  initializeAutomaticTourTiming,
  matchingTourContext,
  readStoredTourContext,
  storeTourContext,
  updateContextStatus,
} from "../tour-context.js?v=20260612-refactor";
import { setMessage } from "../utils.js?v=20260612-refactor";
import {
  loadBootstrapPayload,
  updateHeaderStatuses,
} from "../bootstrap.js?v=20260612-refactor";
import { handleEntrySubmit } from "./operator-entry.js?v=20260616-operator-forms";
import { handleTourContextSubmit } from "./operator-tour-context.js?v=20260616-operator-forms";
import { bindPhoneSyncControls } from "./phone-sync-controls.js?v=20260616-page-controls";

export function initOperatorPage() {
  const tourForm = document.querySelector("#tour-context-form");
  const entryForm = document.querySelector("#entry-form");
  if (!tourForm || !entryForm) {
    return;
  }

  initializeAutomaticTourTiming();
  initializeShopOrderDropdowns();
  initializeTemperatureShorthandInputs();
  tourForm.addEventListener("submit", handleTourContextSubmit);
  entryForm.addEventListener("submit", handleEntrySubmit);
  bindPhoneSyncControls();

  configureOfflineRefresh(async () => {
    await Promise.all([
      loadOperatorBootstrap(),
      loadExcelPendingCount(),
    ]);
  });
  initializeOfflineFeatures();
  void initializeOperator();
}

async function initializeOperator() {
  await updatePhoneSyncStatus();
  try {
    await loadOperatorBootstrap();
  } catch (error) {
    setMessage(
      document.querySelector("#entry-message"),
      `Baslatma basarisiz: ${error.message}`,
      "error",
    );
  }
  await loadExcelPendingCount();
  scheduleOutboxSync();
}

async function loadOperatorBootstrap() {
  const payload = await loadBootstrapPayload({
    cacheMessageSelector: "#phone-sync-message",
  });
  updateHeaderStatuses(payload);
  updateShopOrderOptions(payload.shop_order_source);
  applyActiveTourContext(payload);
}

function applyActiveTourContext(payload) {
  const automaticTiming = payload.current_tour_timing || null;
  const storedContext = readStoredTourContext();
  const activeContext = automaticTiming
    ? matchingTourContext(storedContext, automaticTiming)
      || matchingTourContext(payload.latest_tour_context, automaticTiming)
    : storedContext || payload.latest_tour_context || null;
  if (activeContext) {
    applyTourContext(activeContext);
    storeTourContext(activeContext);
  } else {
    clearStoredTourContext();
    applyAutomaticTourTiming(automaticTiming);
    updateContextStatus(null);
  }
}
