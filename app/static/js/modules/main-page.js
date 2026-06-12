import { apiJson } from "../api.js?v=20260612-refactor";
import { automaticTourTimingForRequest } from "./dates.js?v=20260612-refactor";
import {
  handleIfsReturnCandidates,
  handlePrintIfsReturnCandidates,
} from "./ifs-return.js?v=20260612-refactor";
import {
  loadAuxiliarySubmissions,
  loadEntryLists,
} from "./lists.js?v=20260612-refactor";
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
} from "./offline.js?v=20260612-refactor";
import {
  auxiliaryRequestBody,
  entryRequestBody,
  hasAuxiliaryMeasurement,
} from "./payloads.js?v=20260612-refactor";
import { renderLoading } from "./render.js?v=20260612-refactor";
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
  const entryForm = document.querySelector("#entry-form");
  const tourForm = document.querySelector("#tour-context-form");
  const auxiliaryForm = document.querySelector("#auxiliary-form");
  if (!entryForm || !tourForm) {
    return;
  }

  initializeAutomaticTourTiming();
  tourForm.addEventListener("submit", handleTourContextSubmit);
  entryForm.addEventListener("submit", handleEntrySubmit);
  if (auxiliaryForm) {
    auxiliaryForm.addEventListener("submit", handleAuxiliarySubmit);
  }
  initializeShopOrderDropdowns();
  initializeTemperatureShorthandInputs();

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

  const cycleReportButton = document.querySelector("#create-cycle-report");
  if (cycleReportButton) {
    cycleReportButton.addEventListener("click", handleCreateCycleReport);
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

  configureOfflineRefresh(async () => {
    await Promise.all([
      loadEntryLists(),
      loadAuxiliarySubmissions(),
      loadExcelPendingCount(),
      loadBootstrap(),
    ]);
  });
  initializeOfflineFeatures();
  void initializeApplication();
}

async function initializeApplication() {
  renderLoading(document.querySelector("#recent-entries"), "Kayıtlar yükleniyor...");
  renderLoading(document.querySelector("#pending-entries"), "Bekleyen kayıtlar yükleniyor...");
  renderLoading(document.querySelector("#auxiliary-submissions"), "Gönderimler yükleniyor...");
  await updatePhoneSyncStatus();

  try {
    await loadBootstrap();
  } catch (error) {
    setMessage(
      document.querySelector("#entry-message"),
      `Başlatma başarısız: ${error.message}`,
      "error",
    );
  }

  await Promise.all([loadEntryLists(), loadAuxiliarySubmissions(), loadExcelPendingCount()]);
  scheduleOutboxSync();
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
      `Çevrimdışı mod: son liste kullanılıyor (${formatTimestamp(cachedBootstrap.updated_at)}).`,
      "warning",
    );
  }
  updateExcelStatus(payload.excel);
  updateAuxiliarySystemsStatus(payload.auxiliary_systems);
  applyAuxiliaryDate(payload.current_auxiliary_date);
  updateShopOrderOptions(payload.shop_order_source);

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
  if (excel && excel.available) {
    status.textContent = "Excel hazır";
    status.title = "";
    status.classList.add("status-success");
    return;
  }

  status.textContent = "Excel kullanılamıyor";
  status.title = excel?.last_error || "";
  status.classList.add("status-warning");
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
    status.textContent = "Yardımcı hazır";
    status.title = "";
    status.classList.add("status-success");
    return;
  }

  if (auxiliarySystems?.target_available) {
    status.textContent = "Form dosyası yok";
    status.title = auxiliarySystems?.form_error || "";
    status.classList.add("status-warning");
    return;
  }

  status.textContent = "Yardımcı Excel yok";
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
      "Tur bilgileri telefona kaydedildi. Bağlantı gelince senkronize edilecek.",
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
    setMessage(message, "Kayıt göndermeden önce tur bilgilerini kaydedin.", "error");
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

  setMessage(message, "Kayıt telefona kaydediliyor...", "");
  setButtonBusy(button, true, "Gönderiliyor");

  try {
    await queueOfflineRecord("entry", body, dependsOnClientRequestId);
    form.reset();
    resetShopOrderDropdowns();
    setMessage(
      message,
      "Kayıt telefona kaydedildi. Bağlantı gelince senkronize edilecek.",
      "warning",
    );
    await syncOutbox({ reason: "entry_submit" });
  } catch (error) {
    setMessage(message, `Kayıt telefona kaydedilemedi: ${error.message}`, "error");
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
    setMessage(message, "En az bir yardımcı sistem ölçümü girin.", "error");
    return;
  }

  body.client_request_id = createClientRequestId();
  body.client_recorded_at = recordedAt.toISOString();

  setMessage(message, "Yardımcı sistemler telefona kaydediliyor...", "");
  setButtonBusy(button, true, "Gönderiliyor");

  try {
    await queueOfflineRecord("auxiliary_submission", body);
    form.reset();
    setMessage(
      message,
      "Yardımcı sistemler telefona kaydedildi. Bağlantı gelince senkronize edilecek.",
      "warning",
    );
    await syncOutbox({ reason: "auxiliary_submit" });
  } catch (error) {
    setMessage(
      message,
      `Yardımcı sistemler telefona kaydedilemedi: ${error.message}`,
      "error",
    );
  } finally {
    setButtonBusy(button, false);
  }
}

async function handleRetrySync(event) {
  const button = event.currentTarget;
  const message = document.querySelector("#sync-message");

  setMessage(message, "Bekleyen Excel senkronizasyonu tekrar deneniyor...", "");
  setButtonBusy(button, true, "Deneniyor");

  try {
    const payload = await apiJson("/api/sync/retry", {
      method: "POST",
    });

    if (payload.failed) {
      setMessage(
        message,
        `Tekrar deneme ${payload.synced} senkronizasyon ve ${payload.failed} hata sonrası durdu. ${payload.remaining} kayıt bekliyor.`,
        "warning",
      );
    } else {
      setMessage(
        message,
        `Tekrar deneme tamamlandı. ${payload.synced} kayıt senkronize edildi, ${payload.remaining} kayıt bekliyor.`,
        "success",
      );
    }

    await Promise.all([loadEntryLists(), loadBootstrap()]);
  } catch (error) {
    setMessage(message, `Tekrar deneme başarısız: ${error.message}`, "error");
  } finally {
    setButtonBusy(button, false);
  }
}

async function handleRetryAuxiliarySync(event) {
  const button = event.currentTarget;
  const message = document.querySelector("#auxiliary-message");

  setMessage(message, "Yardımcı sistemler Excel senkronizasyonu tekrar deneniyor...", "");
  setButtonBusy(button, true, "Deneniyor");

  try {
    const payload = await apiJson("/api/auxiliary-systems/sync/retry", {
      method: "POST",
    });

    if (payload.failed) {
      setMessage(
        message,
        `Tekrar deneme ${payload.synced} senkronizasyon ve ${payload.failed} hata sonrası durdu. ${payload.remaining} gönderim bekliyor.`,
        "warning",
      );
    } else {
      setMessage(
        message,
        `Tekrar deneme tamamlandı. ${payload.synced} gönderim senkronize edildi, ${payload.remaining} gönderim bekliyor.`,
        "success",
      );
    }

    await Promise.all([loadAuxiliarySubmissions(), loadBootstrap()]);
  } catch (error) {
    setMessage(message, `Tekrar deneme başarısız: ${error.message}`, "error");
  } finally {
    setButtonBusy(button, false);
  }
}

async function handleCreateCycleReport(event) {
  const button = event.currentTarget;
  const message = document.querySelector("#cycle-report-message");

  setMessage(message, "Çevrim kontrol raporu oluşturuluyor...", "");
  setButtonBusy(button, true, "Oluşturuluyor");

  try {
    const payload = await apiJson("/api/cycle-report/today", {
      method: "POST",
    });
    const warningText = payload.warning_count
      ? ` ${payload.warning_count} uyarı var.`
      : "";
    setMessage(
      message,
      `Rapor oluşturuldu: ${payload.output_path}. ${payload.row_count} kayıt işlendi.${warningText}`,
      payload.warning_count ? "warning" : "success",
    );
  } catch (error) {
    setMessage(message, `Rapor oluşturulamadı: ${error.message}`, "error");
  } finally {
    setButtonBusy(button, false);
  }
}
