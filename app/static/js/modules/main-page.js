import { apiJson } from "../api.js?v=20260612-refactor";
import {
  amountControlRequestBodies,
  initializeAmountControlControls,
  resetAmountControlForm,
  updateAmountControlBootstrap,
} from "./amount-control.js?v=20260617-amount-control";
import {
  automaticTourTimingForRequest,
  dateForDisplay,
  dateForRequest,
} from "./dates.js?v=20260612-refactor";
import {
  handleIfsReturnCandidates,
  handlePrintIfsReturnCandidates,
} from "./ifs-return.js?v=20260612-refactor";
import {
  loadAmountControlShifts,
  loadAuxiliarySubmissions,
  loadEntryLists,
} from "./lists.js?v=20260618-recent-entries";
import {
  configureOfflineRefresh,
  exportOfflineOutbox,
  handlePhoneOutboxSync,
  initializeOfflineFeatures,
  loadExcelPendingCount,
  queueOfflineRecord,
  readBootstrapCache,
  scheduleOutboxSync,
  syncOutbox,
  updatePhoneSyncStatus,
  writeBootstrapCache,
} from "./offline.js?v=20260618-excel-bulk";
import {
  auxiliaryRequestBody,
  entryRequestBody,
  hasAuxiliaryMeasurement,
} from "./payloads.js?v=20260612-refactor";
import {
  renderListError,
  renderLoading,
  renderMissingProductionStarts,
  renderProductionLossReport,
} from "./render.js?v=20260619-production-loss";
import {
  initializeShopOrderDropdowns,
  resetShopOrderDropdowns,
  updateShopOrderOptions,
} from "./shop-orders.js?v=20260612-refactor";
import {
  initializeTemperatureShorthandInputs,
  normalizeTemperatureShorthandForm,
} from "./temperature.js?v=20260612-refactor";
import {
  applyAutomaticTourTiming,
  applyTourContext,
  clearStoredTourContext,
  initializeAutomaticTourTiming,
  matchingTourContext,
  readStoredTourContext,
  storeTourContext,
  updateContextStatus,
} from "./tour-context.js?v=20260612-refactor";
import {
  cleanRequired,
  createClientRequestId,
  formatTimestamp,
  setButtonBusy,
  setMessage,
} from "./utils.js?v=20260612-refactor";

export function initMainPage() {
  const page = document.body?.dataset?.page;
  if (!page || page === "login") {
    return;
  }

  initializeSharedShell(page);
  initializePage(page);
  void initializeApplication(page);
}

function initializeSharedShell(page) {
  bindPhoneSyncPanel();
  configureOfflineRefresh(async () => {
    await refreshCurrentPage(page);
  });
  initializeOfflineFeatures();
}

function initializePage(page) {
  if (page === "process") {
    initializeProcessPage();
    return;
  }
  if (page === "auxiliary") {
    initializeAuxiliaryPage();
    return;
  }
  if (page === "amount-control") {
    initializeAmountControlPage();
    return;
  }
  if (page === "reports") {
    initializeReportsPage();
  }
}

function bindPhoneSyncPanel() {
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

function initializeProcessPage() {
  const entryForm = document.querySelector("#entry-form");
  const tourForm = document.querySelector("#tour-context-form");

  if (tourForm) {
    initializeAutomaticTourTiming();
    tourForm.addEventListener("submit", handleTourContextSubmit);
  }
  if (entryForm) {
    entryForm.addEventListener("submit", handleEntrySubmit);
  }

  initializeShopOrderDropdowns();
  initializeTemperatureShorthandInputs();
}

function initializeAuxiliaryPage() {
  const auxiliaryForm = document.querySelector("#auxiliary-form");
  if (auxiliaryForm) {
    auxiliaryForm.addEventListener("submit", handleAuxiliarySubmit);
  }

  const auxiliaryRetryButton = document.querySelector("#retry-auxiliary-sync");
  if (auxiliaryRetryButton) {
    auxiliaryRetryButton.addEventListener("click", handleRetryAuxiliarySync);
  }

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

function initializeAmountControlPage() {
  const amountControlForm = document.querySelector("#amount-control-form");
  initializeAmountControlControls();
  if (amountControlForm) {
    amountControlForm.addEventListener("submit", handleAmountControlSubmit);
  }

  const amountControlRefreshButton = document.querySelector("#refresh-amount-control");
  if (amountControlRefreshButton) {
    amountControlRefreshButton.addEventListener("click", async () => {
      setButtonBusy(amountControlRefreshButton, true, "Yenileniyor");
      try {
        await loadAmountControlShifts();
      } finally {
        setButtonBusy(amountControlRefreshButton, false);
      }
    });
  }
}

function initializeReportsPage() {
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

  const retryButton = document.querySelector("#retry-sync");
  if (retryButton) {
    retryButton.addEventListener("click", handleRetrySync);
  }

  const cycleReportButton = document.querySelector("#create-cycle-report");
  if (cycleReportButton) {
    cycleReportButton.addEventListener("click", handleCreateCycleReport);
  }

  initializeProductionLossForm();

  const whatsappMessageButton = document.querySelector("#generate-whatsapp-status-message");
  if (whatsappMessageButton) {
    whatsappMessageButton.addEventListener("click", handleGenerateWhatsappStatusMessage);
  }

  const whatsappCopyButton = document.querySelector("#copy-whatsapp-status-message");
  if (whatsappCopyButton) {
    whatsappCopyButton.addEventListener("click", handleCopyWhatsappStatusMessage);
  }

  const missingProductionButton = document.querySelector("#run-missing-production-starts");
  if (missingProductionButton) {
    missingProductionButton.addEventListener("click", handleMissingProductionStarts);
  }

  const ifsReturnButton = document.querySelector("#run-ifs-return-candidates");
  if (ifsReturnButton) {
    ifsReturnButton.addEventListener("click", handleIfsReturnCandidates);
  }

  const ifsReturnPrintButton = document.querySelector("#print-ifs-return-candidates");
  if (ifsReturnPrintButton) {
    ifsReturnPrintButton.disabled = true;
    ifsReturnPrintButton.addEventListener("click", handlePrintIfsReturnCandidates);
  }
}

async function initializeApplication(page) {
  renderInitialLoading(page);
  await updatePhoneSyncStatus();

  try {
    await loadBootstrap();
  } catch (error) {
    setMessage(
      pageMessageTarget(page),
      `Baslatma basarisiz: ${error.message}`,
      "error",
    );
  }

  await loadPageData(page);
  scheduleOutboxSync();
}

function renderInitialLoading(page) {
  if (page === "reports") {
    renderLoading(document.querySelector("#recent-entries"), "Kayitlar yukleniyor...");
    renderLoading(document.querySelector("#pending-entries"), "Bekleyen kayitlar yukleniyor...");
    return;
  }
  if (page === "auxiliary") {
    renderLoading(document.querySelector("#auxiliary-submissions"), "Gonderimler yukleniyor...");
    return;
  }
  if (page === "amount-control") {
    renderLoading(
      document.querySelector("#amount-control-submissions"),
      "Miktar kontrolleri yukleniyor...",
    );
  }
}

async function refreshCurrentPage(page) {
  await loadBootstrap();
  await Promise.all([
    updatePhoneSyncStatus(),
    loadExcelPendingCount(),
    ...pageDataLoaders(page),
  ]);
}

async function loadPageData(page) {
  await Promise.all([
    loadExcelPendingCount(),
    ...pageDataLoaders(page),
  ]);
}

function pageDataLoaders(page) {
  if (page === "reports") {
    return [loadEntryLists()];
  }
  if (page === "auxiliary") {
    return [loadAuxiliarySubmissions()];
  }
  if (page === "amount-control") {
    return [loadAmountControlShifts()];
  }
  return [];
}

function pageMessageTarget(page) {
  if (page === "process") {
    return document.querySelector("#entry-message")
      || document.querySelector("#tour-context-message");
  }
  if (page === "auxiliary") {
    return document.querySelector("#auxiliary-message");
  }
  if (page === "amount-control") {
    return document.querySelector("#amount-control-message");
  }
  if (page === "reports") {
    return document.querySelector("#sync-message")
      || document.querySelector("#cycle-report-message")
      || document.querySelector("#whatsapp-status-feedback")
      || document.querySelector("#missing-production-message")
      || document.querySelector("#ifs-return-message");
  }
  return document.querySelector("#phone-sync-message");
}

async function loadBootstrap() {
  let payload;
  try {
    payload = await apiJson("/api/bootstrap");
    try {
      await writeBootstrapCache(payload);
    } catch (_cacheError) {
      // The live bootstrap payload is enough; offline cache is an extra safety net.
    }
  } catch (error) {
    const cachedBootstrap = await readBootstrapCache();
    if (!cachedBootstrap) {
      throw error;
    }
    payload = cachedBootstrap.payload;
    if (payload?.shop_order_source) {
      payload.shop_order_source.offline_cached_at = cachedBootstrap.updated_at;
    }
    setMessage(
      document.querySelector("#phone-sync-message"),
      `Cevrimdisi mod: son liste kullaniliyor (${formatTimestamp(cachedBootstrap.updated_at)}).`,
      "warning",
    );
  }
  updateExcelStatus(payload.excel);
  applyExcelSyncDate(payload.current_tour_timing?.date);
  updateAuxiliarySystemsStatus(payload.auxiliary_systems);
  applyAuxiliaryDate(payload.current_auxiliary_date);
  updateShopOrderOptions(payload.shop_order_source);
  updateAmountControlBootstrap(payload.machines || [], payload.shop_order_source);
  updateProductionEngineerOptions(payload.production_engineers || []);

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

function updateExcelStatus(excel) {
  const status = document.querySelector("#excel-status");
  if (!status) {
    return;
  }

  status.classList.remove(
    "status-muted",
    "status-success",
    "status-warning",
    "status-error",
  );
  if (excel?.database_backed) {
    status.textContent = "Veritabani hazir";
    status.title = "";
    status.classList.add("status-success");
    return;
  }
  if (excel && excel.available) {
    status.textContent = "Excel hazir";
    status.title = "";
    status.classList.add("status-success");
    return;
  }

  status.textContent = "Excel kullanilamiyor";
  status.title = excel?.last_error || "";
  status.classList.add("status-warning");
}

function updateProductionEngineerOptions(engineers) {
  const select = document.querySelector("#production-engineer");
  if (!select) {
    return;
  }

  const currentValue = select.value;
  const placeholder = select.querySelector("option[value='']");
  select.replaceChildren();
  if (placeholder) {
    select.appendChild(placeholder);
  } else {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "Uretim muhendisi secin";
    select.appendChild(option);
  }

  for (const engineer of engineers) {
    const option = document.createElement("option");
    option.value = engineer.full_name;
    option.textContent = engineer.full_name;
    option.dataset.engineerId = String(engineer.id);
    select.appendChild(option);
  }

  if (currentValue) {
    select.value = currentValue;
  }
}

function updateAuxiliarySystemsStatus(auxiliarySystems) {
  const status = document.querySelector("#auxiliary-systems-status");
  if (!status) {
    return;
  }

  status.classList.remove(
    "status-muted",
    "status-success",
    "status-warning",
    "status-error",
  );
  if (auxiliarySystems?.target_available && auxiliarySystems?.form_available) {
    status.textContent = "Yardimci hazir";
    status.title = "";
    status.classList.add("status-success");
    return;
  }

  if (auxiliarySystems?.target_available) {
    status.textContent = "Form dosyasi yok";
    status.title = auxiliarySystems?.form_error || "";
    status.classList.add("status-warning");
    return;
  }

  status.textContent = "Yardimci Excel yok";
  status.title = auxiliarySystems?.target_error || auxiliarySystems?.form_error || "";
  status.classList.add("status-warning");
}

function applyAuxiliaryDate(value) {
  const dateInput = document.querySelector("#auxiliary-date");
  const dateLabel = document.querySelector("#auxiliary-date-label");
  if (dateInput) {
    dateInput.value = value || "";
  }
  if (dateLabel) {
    dateLabel.textContent = value ? `Tarih: ${value}` : "";
  }
}

function applyExcelSyncDate(value) {
  const dateInput = document.querySelector("#sync-process-date");
  if (!dateInput || dateInput.value) {
    return;
  }
  dateInput.value = dateForRequest(value);
  const productionLossDateFrom = document.querySelector("#production-loss-date-from");
  const productionLossDateTo = document.querySelector("#production-loss-date-to");
  if (productionLossDateFrom && !productionLossDateFrom.value) {
    productionLossDateFrom.value = dateInput.value;
  }
  if (productionLossDateTo && !productionLossDateTo.value) {
    productionLossDateTo.value = dateInput.value;
  }
}

async function handleTourContextSubmit(event) {
  event.preventDefault();

  const form = event.currentTarget;
  const message = document.querySelector("#tour-context-message");
  const button = form.querySelector("button[type='submit']");
  if (!form.reportValidity()) {
    return;
  }

  setMessage(message, "Tur bilgileri telefona kaydediliyor...", "");
  setButtonBusy(button, true, "Kaydediliyor");

  try {
    const recordedAt = new Date();
    const automaticTiming = automaticTourTimingForRequest(recordedAt);
    applyAutomaticTourTiming(automaticTiming);
    const clientRequestId = createClientRequestId();

    const formData = new FormData(form);
    const body = {
      date: automaticTiming.date,
      ambient_temp: cleanRequired(formData.get("ambient_temp")),
      production_engineer: cleanRequired(formData.get("production_engineer")),
      shift_chief: cleanRequired(formData.get("shift_chief")),
      shift: automaticTiming.shift,
      client_request_id: clientRequestId,
      client_recorded_at: recordedAt.toISOString(),
    };

    await queueOfflineRecord("tour_context", body);
    const context = {
      id: `local:${clientRequestId}`,
      client_request_id: clientRequestId,
      client_recorded_at: body.client_recorded_at,
      ...body,
    };

    applyTourContext(context);
    storeTourContext(context);
    setMessage(
      message,
      "Tur bilgileri telefona kaydedildi. Baglanti gelince senkronize edilecek.",
      "warning",
    );
    await syncOutbox({ reason: "tour_context_submit" });
  } catch (error) {
    setMessage(message, `Tur bilgileri kaydedilemedi: ${error.message}`, "error");
  } finally {
    setButtonBusy(button, false);
  }
}

async function handleEntrySubmit(event) {
  event.preventDefault();

  const form = event.currentTarget;
  const message = document.querySelector("#entry-message");
  const button = form.querySelector("button[type='submit']");
  const contextId = document.querySelector("#tour-context-id")?.value;
  const activeContext = readStoredTourContext();

  if (!contextId) {
    setMessage(message, "Kayit gondermeden once tur bilgilerini kaydedin.", "error");
    document.querySelector("#tour-context-heading")?.scrollIntoView({
      behavior: "smooth",
      block: "start",
    });
    return;
  }

  if (!form.reportValidity()) {
    return;
  }

  normalizeTemperatureShorthandForm(form);
  const recordedAt = new Date();
  const clientRequestId = createClientRequestId();
  const body = entryRequestBody(form, contextId);
  body.client_request_id = clientRequestId;
  body.client_recorded_at = recordedAt.toISOString();
  const dependsOnClientRequestId = activeContext?.client_request_id
    && String(activeContext.id || "").startsWith("local:")
    ? activeContext.client_request_id
    : null;

  setMessage(message, "Kayit telefona kaydediliyor...", "");
  setButtonBusy(button, true, "Gonderiliyor");

  try {
    await queueOfflineRecord("entry", body, dependsOnClientRequestId);
    form.reset();
    resetShopOrderDropdowns();
    setMessage(
      message,
      "Kayit telefona kaydedildi. Baglanti gelince senkronize edilecek.",
      "warning",
    );
    await syncOutbox({ reason: "entry_submit" });
  } catch (error) {
    setMessage(message, `Kayit telefona kaydedilemedi: ${error.message}`, "error");
  } finally {
    setButtonBusy(button, false);
  }
}

async function handleAuxiliarySubmit(event) {
  event.preventDefault();

  const form = event.currentTarget;
  const message = document.querySelector("#auxiliary-message");
  const button = form.querySelector("button[type='submit']");

  if (!form.reportValidity()) {
    return;
  }

  const recordedAt = new Date();
  const body = auxiliaryRequestBody(form, recordedAt);
  if (!hasAuxiliaryMeasurement(body.payload)) {
    setMessage(message, "En az bir yardimci sistem olcumu girin.", "error");
    return;
  }

  body.client_request_id = createClientRequestId();
  body.client_recorded_at = recordedAt.toISOString();

  setMessage(message, "Yardimci sistemler telefona kaydediliyor...", "");
  setButtonBusy(button, true, "Gonderiliyor");

  try {
    await queueOfflineRecord("auxiliary_submission", body);
    form.reset();
    setMessage(
      message,
      "Yardimci sistemler telefona kaydedildi. Baglanti gelince senkronize edilecek.",
      "warning",
    );
    await syncOutbox({ reason: "auxiliary_submit" });
  } catch (error) {
    setMessage(
      message,
      `Yardimci sistemler telefona kaydedilemedi: ${error.message}`,
      "error",
    );
  } finally {
    setButtonBusy(button, false);
  }
}

async function handleAmountControlSubmit(event) {
  event.preventDefault();

  const form = event.currentTarget;
  const message = document.querySelector("#amount-control-message");
  const button = form.querySelector("button[type='submit']");

  if (!form.reportValidity()) {
    return;
  }

  let bodies;
  try {
    bodies = amountControlRequestBodies(form);
  } catch (error) {
    setMessage(message, error.message, "error");
    return;
  }

  const recordedAt = new Date();
  for (const body of bodies) {
    body.client_request_id = createClientRequestId();
    body.client_recorded_at = recordedAt.toISOString();
  }

  setMessage(message, "Miktar kontrolu telefona kaydediliyor...", "");
  setButtonBusy(button, true, "Gonderiliyor");

  try {
    for (const body of bodies) {
      await queueOfflineRecord("amount_control_shift", body);
    }
    resetAmountControlForm(form);
    setMessage(
      message,
      "Miktar kontrolu telefona kaydedildi. Baglanti gelince senkronize edilecek.",
      "warning",
    );
    await syncOutbox({ reason: "amount_control_submit" });
  } catch (error) {
    setMessage(
      message,
      `Miktar kontrolu telefona kaydedilemedi: ${error.message}`,
      "error",
    );
  } finally {
    setButtonBusy(button, false);
  }
}

async function handleRetrySync(event) {
  const button = event.currentTarget;
  const message = document.querySelector("#sync-message");
  const processDate = document.querySelector("#sync-process-date")?.value || "";

  if (!processDate) {
    setMessage(message, "Excel aktarimi icin tarih secin.", "error");
    return;
  }

  const displayDate = dateForDisplay(processDate);
  setMessage(message, `${displayDate} icin Excel aktarimi baslatiliyor...`, "");
  setButtonBusy(button, true, "Aktariliyor");

  try {
    const query = new URLSearchParams({ process_date: processDate });
    const payload = await apiJson(`/api/sync/retry?${query.toString()}`, {
      method: "POST",
    });

    if (payload.failed) {
      setMessage(
        message,
        `${displayDate} aktarimi ${payload.synced} kayit ve ${payload.failed} hata ile durdu. ${payload.remaining} kayit bekliyor.`,
        "warning",
      );
    } else if (!payload.synced) {
      setMessage(
        message,
        `${displayDate} icin Excel'e aktarilacak bekleyen kayit yok.`,
        "success",
      );
    } else {
      setMessage(
        message,
        `${displayDate} icin ${payload.synced} kayit Excel'e aktarildi. ${payload.remaining} kayit bekliyor.`,
        "success",
      );
    }

    await Promise.all([loadEntryLists(), loadBootstrap(), loadExcelPendingCount()]);
  } catch (error) {
    setMessage(message, `Excel aktarimi basarisiz: ${error.message}`, "error");
  } finally {
    setButtonBusy(button, false);
  }
}

async function handleRetryAuxiliarySync(event) {
  const button = event.currentTarget;
  const message = document.querySelector("#auxiliary-message");

  setMessage(message, "Yardimci sistemler Excel senkronizasyonu tekrar deneniyor...", "");
  setButtonBusy(button, true, "Deneniyor");

  try {
    const payload = await apiJson("/api/auxiliary-systems/sync/retry", {
      method: "POST",
    });

    if (payload.failed) {
      setMessage(
        message,
        `Tekrar deneme ${payload.synced} senkronizasyon ve ${payload.failed} hata sonrasi durdu. ${payload.remaining} gonderim bekliyor.`,
        "warning",
      );
    } else {
      setMessage(
        message,
        `Tekrar deneme tamamlandi. ${payload.synced} gonderim senkronize edildi, ${payload.remaining} gonderim bekliyor.`,
        "success",
      );
    }

    await Promise.all([loadAuxiliarySubmissions(), loadBootstrap(), loadExcelPendingCount()]);
  } catch (error) {
    setMessage(message, `Tekrar deneme basarisiz: ${error.message}`, "error");
  } finally {
    setButtonBusy(button, false);
  }
}

async function handleCreateCycleReport(event) {
  const button = event.currentTarget;
  const message = document.querySelector("#cycle-report-message");

  setMessage(message, "Cevrim kontrol raporu olusturuluyor...", "");
  setButtonBusy(button, true, "Olusturuluyor");

  try {
    const payload = await apiJson("/api/cycle-report/today", {
      method: "POST",
    });
    const warningText = payload.warning_count
      ? ` ${payload.warning_count} uyari var.`
      : "";
    setMessage(
      message,
      `Rapor olusturuldu: ${payload.output_path}. ${payload.row_count} kayit islendi.${warningText}`,
      payload.warning_count ? "warning" : "success",
    );
    await loadMissingProductionStarts();
    await loadWhatsappStatusMessage();
  } catch (error) {
    setMessage(message, `Rapor olusturulamadi: ${error.message}`, "error");
  } finally {
    setButtonBusy(button, false);
  }
}

function initializeProductionLossForm() {
  const form = document.querySelector("#production-loss-form");
  if (!form) {
    return;
  }
  form.addEventListener("submit", handleCreateProductionLossReport);
}

async function handleCreateProductionLossReport(event) {
  event.preventDefault();

  const form = event.currentTarget;
  const message = document.querySelector("#production-loss-message");
  const container = document.querySelector("#production-loss-results");
  const button = form.querySelector("button[type='submit']");

  if (!form.reportValidity()) {
    return;
  }

  const formData = new FormData(form);
  const body = {
    date_from: cleanRequired(formData.get("date_from")),
    date_to: cleanRequired(formData.get("date_to")),
    refresh_ifs: formData.get("refresh_ifs") === "on",
  };

  setMessage(message, "Production Loss raporu olusturuluyor...", "");
  renderLoading(container, "Miktar, cevrim ve IFS zamanlari hesaplaniyor...");
  setButtonBusy(button, true, "Olusturuluyor");

  try {
    const payload = await apiJson("/api/production-loss-reports", {
      method: "POST",
      body,
    });
    renderProductionLossReport(container, payload);
    const warningText = payload.warning_count
      ? ` ${payload.warning_count} uyari var.`
      : "";
    setMessage(
      message,
      `Rapor olusturuldu: ${payload.output_path}. ${payload.row_count} satir.${warningText}`,
      payload.warning_count ? "warning" : "success",
    );
  } catch (error) {
    setMessage(message, `Production Loss raporu olusturulamadi: ${error.message}`, "error");
    renderListError(container, `Production Loss raporu olusturulamadi: ${error.message}`);
  } finally {
    setButtonBusy(button, false);
  }
}

async function handleGenerateWhatsappStatusMessage(event) {
  const button = event.currentTarget;
  await loadWhatsappStatusMessage(button);
}

async function loadWhatsappStatusMessage(button = null) {
  const message = document.querySelector("#whatsapp-status-feedback");
  const textarea = document.querySelector("#whatsapp-status-message-text");
  const copyButton = document.querySelector("#copy-whatsapp-status-message");

  setMessage(message, "WhatsApp mesaji olusturuluyor...", "");
  if (textarea) {
    textarea.value = "";
  }
  if (copyButton) {
    copyButton.disabled = true;
  }
  setButtonBusy(button, true, "Olusturuluyor");

  try {
    const payload = await apiJson("/api/ifs/whatsapp-status-message");
    if (textarea) {
      textarea.value = payload.message || "";
    }
    if (copyButton) {
      copyButton.disabled = !payload.message;
    }
    setMessage(
      message,
      `${payload.machine_count || 0} makine icin WhatsApp mesaji hazir.`,
      "success",
    );
  } catch (error) {
    setMessage(message, `WhatsApp mesaji olusturulamadi: ${error.message}`, "error");
  } finally {
    setButtonBusy(button, false);
  }
}

async function handleCopyWhatsappStatusMessage() {
  const message = document.querySelector("#whatsapp-status-feedback");
  const textarea = document.querySelector("#whatsapp-status-message-text");
  const text = textarea?.value || "";
  if (!text) {
    setMessage(message, "Kopyalanacak WhatsApp mesaji yok.", "error");
    return;
  }

  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
    } else {
      textarea.select();
      document.execCommand("copy");
    }
    setMessage(message, "WhatsApp mesaji kopyalandi.", "success");
  } catch (error) {
    setMessage(message, `WhatsApp mesaji kopyalanamadi: ${error.message}`, "error");
  }
}

async function handleMissingProductionStarts(event) {
  const button = event.currentTarget;
  await loadMissingProductionStarts(button);
}

async function loadMissingProductionStarts(button = null) {
  const message = document.querySelector("#missing-production-message");
  const container = document.querySelector("#missing-production-results");
  const processDate = document.querySelector("#sync-process-date")?.value || "";

  if (!processDate) {
    setMessage(message, "IFS baslatma kontrolu icin tarih secin.", "error");
    return;
  }

  const displayDate = dateForDisplay(processDate);
  setMessage(message, `${displayDate} icin IFS baslatma kontrolu calisiyor...`, "");
  renderLoading(container, "IFS operasyonlari ve girilen cevrimler karsilastiriliyor...");
  setButtonBusy(button, true, "Kontrol ediliyor");

  try {
    const query = new URLSearchParams({ process_date: processDate });
    const payload = await apiJson(`/api/ifs/missing-production-starts?${query.toString()}`);
    renderMissingProductionStarts(container, payload);
    if (payload.missing_count) {
      setMessage(
        message,
        `${displayDate} icin ${payload.missing_count} makine IFS'te baslatilmamis gorunuyor.`,
        "warning",
      );
    } else {
      setMessage(message, `${displayDate} icin eksik yok.`, "success");
    }
  } catch (error) {
    setMessage(message, `IFS baslatma kontrolu basarisiz: ${error.message}`, "error");
    renderListError(container, `IFS baslatma kontrolu basarisiz: ${error.message}`);
  } finally {
    setButtonBusy(button, false);
  }
}
