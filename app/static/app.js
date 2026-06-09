const ACTIVE_CONTEXT_KEY = "process.activeTourContext";
const ENTRY_PAYLOAD_FIELDS = [
  "col_f",
  "col_g",
  "col_h",
  "col_i",
  "col_j",
  "col_k",
  "col_l",
  "col_m",
  "col_n",
  "col_o",
  "col_p",
  "col_q",
];
const SYNC_LABELS = {
  synced: "Senkronize",
  pending_excel: "Beklemede",
  failed_excel: "Başarısız",
};
let shopOrderPairs = [];

class ApiError extends Error {
  constructor(message, status, payload) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.payload = payload;
  }
}

function initLogin() {
  const loginForm = document.querySelector("#login-form");
  if (!loginForm) {
    return;
  }

  loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const error = document.querySelector("#login-error");
    const submitButton = loginForm.querySelector("button[type='submit']");
    const formData = new FormData(loginForm);
    const pin = String(formData.get("pin") || "");

    if (error) {
      error.hidden = true;
      error.textContent = "";
    }
    setButtonBusy(submitButton, true, "Giriş yapılıyor");

    try {
      const response = await fetch("/api/login", {
        method: "POST",
        credentials: "same-origin",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ pin }),
      });

      if (response.ok) {
        window.location.assign("/");
        return;
      }

      if (error) {
        error.textContent = "PIN geçersiz.";
        error.hidden = false;
      }
    } catch (_error) {
      if (error) {
        error.textContent = "Giriş başarısız. Bağlantıyı kontrol edip tekrar deneyin.";
        error.hidden = false;
      }
    } finally {
      setButtonBusy(submitButton, false);
    }
  });
}

function initMainPage() {
  const entryForm = document.querySelector("#entry-form");
  const tourForm = document.querySelector("#tour-context-form");
  if (!entryForm || !tourForm) {
    return;
  }

  initializeAutomaticTourTiming();
  tourForm.addEventListener("submit", handleTourContextSubmit);
  entryForm.addEventListener("submit", handleEntrySubmit);
  initializeShopOrderDropdowns();

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

  void initializeApplication();
}

async function initializeApplication() {
  renderLoading(document.querySelector("#recent-entries"), "Kayıtlar yükleniyor...");
  renderLoading(document.querySelector("#pending-entries"), "Bekleyen kayıtlar yükleniyor...");

  try {
    await loadBootstrap();
  } catch (error) {
    setMessage(
      document.querySelector("#entry-message"),
      `Başlatma başarısız: ${error.message}`,
      "error",
    );
  }

  await loadEntryLists();
}

async function apiJson(path, options = {}) {
  const fetchOptions = {
    method: options.method || "GET",
    credentials: "same-origin",
    headers: {
      Accept: "application/json",
      ...(options.headers || {}),
    },
  };

  if (options.body !== undefined) {
    fetchOptions.headers["Content-Type"] = "application/json";
    fetchOptions.body = JSON.stringify(options.body);
  }

  const response = await fetch(path, fetchOptions);
  const payload = await readJsonResponse(response);

  if (response.status === 401) {
    window.location.assign("/login");
    throw new ApiError("Oturum açmanız gerekiyor.", response.status, payload);
  }

  if (!response.ok) {
    throw new ApiError(
      errorMessageFromPayload(payload, response.statusText),
      response.status,
      payload,
    );
  }

  return payload;
}

async function readJsonResponse(response) {
  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("application/json")) {
    return null;
  }
  return response.json();
}

function errorMessageFromPayload(payload, fallback) {
  if (!payload || payload.detail === undefined) {
    return fallback || "İstek başarısız.";
  }

  if (typeof payload.detail === "string") {
    return payload.detail;
  }

  if (Array.isArray(payload.detail)) {
    return payload.detail
      .map((item) => {
        if (item && typeof item === "object" && item.msg) {
          return item.msg;
        }
        return String(item);
      })
      .join(" ");
  }

  return JSON.stringify(payload.detail);
}

async function loadBootstrap() {
  const payload = await apiJson("/api/bootstrap");
  updateExcelStatus(payload.excel);
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

  status.classList.remove("status-muted", "status-success", "status-warning", "status-error");
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

function initializeShopOrderDropdowns() {
  const machineSelect = document.querySelector("#machine-select");
  const workOrderSelect = document.querySelector("#work-order");
  if (!machineSelect || !workOrderSelect) {
    return;
  }

  machineSelect.addEventListener("change", () => {
    const machine = machineSelect.value;
    populateWorkOrderSelect(workOrderSelect.value, machine);
    const matchingOrders = orderOptionsForMachine(machine);
    if (!workOrderSelect.value && matchingOrders.length === 1) {
      workOrderSelect.value = matchingOrders[0];
    }
  });

  workOrderSelect.addEventListener("change", () => {
    const workOrder = workOrderSelect.value;
    if (!workOrder) {
      return;
    }

    const matchingMachines = machineOptionsForOrder(workOrder);
    if (matchingMachines.length === 1 && machineSelect.value !== matchingMachines[0]) {
      machineSelect.value = matchingMachines[0];
      populateWorkOrderSelect(workOrder, machineSelect.value);
    }
  });
}

function updateShopOrderOptions(source) {
  const machineSelect = document.querySelector("#machine-select");
  const workOrderSelect = document.querySelector("#work-order");
  if (!machineSelect || !workOrderSelect) {
    return;
  }

  const previousMachine = machineSelect.value;
  const previousWorkOrder = workOrderSelect.value;
  shopOrderPairs = normalizeShopOrderPairs(source?.options);
  updateShopOrderSourceStatus(source, shopOrderPairs.length);

  if (!shopOrderPairs.length) {
    setSelectOptions(machineSelect, [], "Makine listesi bulunamadı", "");
    setSelectOptions(workOrderSelect, [], "İş emri listesi bulunamadı", "");
    setShopOrderSelectsEnabled(false);
    return;
  }

  populateMachineSelect(previousMachine);
  populateWorkOrderSelect(previousWorkOrder, machineSelect.value);
  setShopOrderSelectsEnabled(true);
}

function normalizeShopOrderPairs(options) {
  if (!Array.isArray(options)) {
    return [];
  }

  const seen = new Set();
  const pairs = [];
  for (const option of options) {
    const orderNo = cleanOptional(option?.order_no);
    const resourceId = cleanOptional(option?.resource_id);
    if (!orderNo || !resourceId) {
      continue;
    }

    const key = `${orderNo}\u0000${resourceId}`;
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    pairs.push({ orderNo, resourceId });
  }

  pairs.sort((left, right) => {
    const machineComparison = compareOptionText(left.resourceId, right.resourceId);
    if (machineComparison) {
      return machineComparison;
    }
    return compareOptionText(left.orderNo, right.orderNo);
  });
  return pairs;
}

function updateShopOrderSourceStatus(source, pairCount) {
  const status = document.querySelector("#shop-order-source-status");
  if (!status) {
    return;
  }

  status.classList.remove("status-muted", "status-success", "status-warning", "status-error");
  if (pairCount > 0) {
    const orderCount = source?.order_count || uniqueSorted(shopOrderPairs.map((pair) => pair.orderNo)).length;
    const machineCount = source?.resource_count || uniqueSorted(shopOrderPairs.map((pair) => pair.resourceId)).length;
    status.textContent = `${orderCount} iş emri`;
    status.title = `${machineCount} makine / ${pairCount} eşleşme`;
    status.classList.add("status-success");
    return;
  }

  status.textContent = "İş emri listesi yok";
  status.title = source?.last_error || "";
  status.classList.add("status-warning");
}

function populateMachineSelect(selectedValue) {
  const machineSelect = document.querySelector("#machine-select");
  if (!machineSelect) {
    return;
  }
  setSelectOptions(
    machineSelect,
    uniqueSorted(shopOrderPairs.map((pair) => pair.resourceId)),
    "Makine seçin",
    selectedValue,
  );
}

function populateWorkOrderSelect(selectedValue, machine) {
  const workOrderSelect = document.querySelector("#work-order");
  if (!workOrderSelect) {
    return;
  }
  const orders = orderOptionsForMachine(machine);
  setSelectOptions(workOrderSelect, orders, "İş emri seçin", selectedValue);
}

function resetShopOrderDropdowns() {
  if (!shopOrderPairs.length) {
    return;
  }
  populateMachineSelect("");
  populateWorkOrderSelect("", "");
}

function setShopOrderSelectsEnabled(enabled) {
  for (const selector of ["#machine-select", "#work-order"]) {
    const select = document.querySelector(selector);
    if (select) {
      select.disabled = !enabled;
    }
  }
}

function setSelectOptions(select, values, placeholder, selectedValue) {
  const placeholderOption = new Option(placeholder, "");
  const options = values.map((value) => new Option(value, value));
  select.replaceChildren(placeholderOption, ...options);
  select.value = values.includes(selectedValue) ? selectedValue : "";
}

function orderOptionsForMachine(machine) {
  return uniqueSorted(
    shopOrderPairs
      .filter((pair) => !machine || pair.resourceId === machine)
      .map((pair) => pair.orderNo),
  );
}

function machineOptionsForOrder(workOrder) {
  return uniqueSorted(
    shopOrderPairs
      .filter((pair) => pair.orderNo === workOrder)
      .map((pair) => pair.resourceId),
  );
}

function uniqueSorted(values) {
  return Array.from(new Set(values.filter(Boolean))).sort(compareOptionText);
}

function compareOptionText(left, right) {
  return String(left).localeCompare(String(right), "tr", {
    numeric: true,
    sensitivity: "base",
  });
}

function updateContextStatus(context) {
  const status = document.querySelector("#context-status");
  if (!status) {
    return;
  }

  status.classList.remove("status-muted", "status-success", "status-warning", "status-error");
  if (!context) {
    status.textContent = "Aktif tur yok";
    status.classList.add("status-muted");
    return;
  }

  status.textContent = `Tur ${dateForDisplay(context.date)} / ${context.shift}`;
  status.classList.add("status-success");
}

async function handleTourContextSubmit(event) {
  event.preventDefault();

  const form = event.currentTarget;
  const message = document.querySelector("#tour-context-message");
  const button = form.querySelector("button[type='submit']");
  if (!form.reportValidity()) {
    return;
  }

  setMessage(message, "Tur bilgileri kaydediliyor...", "");
  setButtonBusy(button, true, "Kaydediliyor");

  try {
    const automaticTiming = automaticTourTimingForRequest();
    applyAutomaticTourTiming(automaticTiming);

    const formData = new FormData(form);
    const body = {
      date: automaticTiming.date,
      ambient_temp: cleanRequired(formData.get("ambient_temp")),
      production_engineer: cleanRequired(formData.get("production_engineer")),
      shift_chief: cleanRequired(formData.get("shift_chief")),
      shift: automaticTiming.shift,
    };

    const payload = await apiJson("/api/tour-context", {
      method: "POST",
      body,
    });
    const context = payload.tour_context || {
      id: payload.id,
      ...body,
    };

    applyTourContext(context);
    storeTourContext(context);
    setMessage(message, "Tur bilgileri kaydedildi.", "success");
  } catch (error) {
    setMessage(message, `Doğrulama hatası: ${error.message}`, "error");
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

  const body = entryRequestBody(form, contextId);
  setMessage(message, "Kayıt kaydediliyor...", "");
  setButtonBusy(button, true, "Gönderiliyor");

  try {
    const payload = await apiJson("/api/entries", {
      method: "POST",
      body,
    });

    if (payload.synced_to_excel) {
      const rowNumber = payload.entry?.excel_row_number;
      const suffix = rowNumber ? ` Satır ${rowNumber}.` : "";
      setMessage(message, `Excel ile senkronize edildi.${suffix}`, "success");
    } else {
      setMessage(message, "Yerel olarak kaydedildi. Excel senkronizasyonu bekliyor.", "warning");
    }

    form.reset();
    resetShopOrderDropdowns();
    await Promise.all([loadEntryLists(), loadBootstrap()]);
  } catch (error) {
    const prefix = error instanceof ApiError && error.status === 422
      ? "Doğrulama hatası"
      : "Kayıt gönderilemedi";
    setMessage(message, `${prefix}: ${error.message}`, "error");
  } finally {
    setButtonBusy(button, false);
  }
}

function entryRequestBody(form, contextId) {
  const formData = new FormData(form);
  const payload = {};
  for (const fieldName of ENTRY_PAYLOAD_FIELDS) {
    payload[fieldName] = cleanOptional(formData.get(fieldName));
  }

  return {
    tour_context_id: Number(contextId),
    payload,
    status: cleanOptional(formData.get("status")),
    notes: cleanOptional(formData.get("notes")),
    mold_info: cleanOptional(formData.get("mold_info")),
  };
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

async function loadEntryLists() {
  await Promise.all([loadRecentEntries(), loadPendingEntries()]);
}

async function loadRecentEntries() {
  const container = document.querySelector("#recent-entries");
  try {
    const payload = await apiJson("/api/entries?limit=10");
    renderEntryList(
      container,
      Array.isArray(payload.entries) ? payload.entries : [],
      "Son kayıt yok.",
    );
  } catch (error) {
    renderListError(container, `Son kayıtlar yüklenemedi: ${error.message}`);
  }
}

async function loadPendingEntries() {
  const container = document.querySelector("#pending-entries");
  try {
    const [pendingPayload, failedPayload] = await Promise.all([
      apiJson("/api/entries?sync_status=pending_excel&limit=50"),
      apiJson("/api/entries?sync_status=failed_excel&limit=50"),
    ]);
    const entries = [
      ...(Array.isArray(pendingPayload.entries) ? pendingPayload.entries : []),
      ...(Array.isArray(failedPayload.entries) ? failedPayload.entries : []),
    ]
      .sort((left, right) => entryTime(right) - entryTime(left))
      .slice(0, 50);

    renderEntryList(container, entries, "Bekleyen kayıt yok.");
  } catch (error) {
    renderListError(container, `Bekleyen kayıtlar yüklenemedi: ${error.message}`);
  }
}

function renderEntryList(container, entries, emptyText) {
  if (!container) {
    return;
  }

  if (!entries.length) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = emptyText;
    container.replaceChildren(empty);
    return;
  }

  const fragment = document.createDocumentFragment();
  for (const entry of entries) {
    fragment.appendChild(renderEntryRow(entry));
  }
  container.replaceChildren(fragment);
}

function renderEntryRow(entry) {
  const row = document.createElement("article");
  row.className = "entry-row";

  const details = document.createElement("div");
  const title = document.createElement("p");
  title.className = "entry-title";
  title.textContent = entryTitle(entry);

  const meta = document.createElement("p");
  meta.className = "entry-meta";
  meta.textContent = entryMeta(entry);

  details.append(title, meta);
  if (entry.last_error) {
    const error = document.createElement("p");
    error.className = "entry-meta error";
    error.textContent = entry.last_error;
    details.appendChild(error);
  }

  const status = document.createElement("span");
  status.className = `status-pill ${statusClass(entry.sync_status)}`;
  status.textContent = SYNC_LABELS[entry.sync_status] || entry.sync_status || "Bilinmiyor";
  if (entry.excel_row_number) {
    status.title = `Excel satırı ${entry.excel_row_number}`;
  }

  row.append(details, status);
  return row;
}

function entryTitle(entry) {
  const payload = entry.payload || {};
  const machine = payload.col_f || "Makine";
  const workOrder = payload.col_g || "";
  return workOrder ? `${machine} - ${workOrder}` : String(machine);
}

function entryMeta(entry) {
  const payload = entry.payload || {};
  const pieces = [
    payload.col_h ? `Toplam göz ${payload.col_h}` : "",
    payload.col_i ? `Çalışan göz ${payload.col_i}` : "",
    entry.excel_row_number ? `Excel satırı ${entry.excel_row_number}` : "",
    formatTimestamp(entry.submitted_at || entry.created_at),
  ].filter(Boolean);
  return pieces.join(" / ");
}

function statusClass(syncStatus) {
  if (syncStatus === "synced") {
    return "status-success";
  }
  if (syncStatus === "failed_excel") {
    return "status-error";
  }
  return "status-warning";
}

function renderLoading(container, text) {
  if (!container) {
    return;
  }
  const loading = document.createElement("p");
  loading.className = "empty-state";
  loading.textContent = text;
  container.replaceChildren(loading);
}

function renderListError(container, text) {
  if (!container) {
    return;
  }
  const error = document.createElement("p");
  error.className = "empty-state error";
  error.textContent = text;
  container.replaceChildren(error);
}

function applyTourContext(context) {
  setInputValue("#tour-context-id", context.id);
  setInputValue("#tour-date", dateForRequest(context.date));
  setInputValue("#ambient-temp", context.ambient_temp);
  setInputValue("#production-engineer", context.production_engineer);
  setInputValue("#shift-chief", context.shift_chief);
  setInputValue("#shift", context.shift);
  updateContextStatus(context);
}

function matchingTourContext(context, automaticTiming) {
  if (!context || !automaticTiming) {
    return null;
  }

  const sameDate = dateForDisplay(context.date) === dateForDisplay(automaticTiming.date);
  const sameShift = String(context.shift || "") === String(automaticTiming.shift || "");
  return sameDate && sameShift ? context : null;
}

function applyAutomaticTourTiming(timing) {
  setInputValue("#tour-context-id", "");
  setInputValue("#tour-date", timing ? dateForRequest(timing.date) : "");
  setInputValue("#shift", timing ? timing.shift : "");
}

function readStoredTourContext() {
  try {
    const raw = window.sessionStorage.getItem(ACTIVE_CONTEXT_KEY);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw);
    if (parsed && parsed.id) {
      return parsed;
    }
  } catch (_error) {
    return null;
  }
  return null;
}

function storeTourContext(context) {
  try {
    window.sessionStorage.setItem(ACTIVE_CONTEXT_KEY, JSON.stringify(context));
  } catch (_error) {
    // Session storage is helpful for speed, but the saved backend context remains valid.
  }
}

function clearStoredTourContext() {
  try {
    window.sessionStorage.removeItem(ACTIVE_CONTEXT_KEY);
  } catch (_error) {
    // Nothing to clear if the browser blocks session storage.
  }
}

function initializeAutomaticTourTiming() {
  applyAutomaticTourTiming(automaticTourTimingForRequest());
}

function automaticTourTimingForRequest() {
  const now = new Date();
  return {
    date: localIsoDate(now),
    shift: shiftForLocalTime(now),
  };
}

function localIsoDate(value) {
  const localTime = value.getTime() - value.getTimezoneOffset() * 60000;
  return new Date(localTime).toISOString().slice(0, 10);
}

function shiftForLocalTime(value) {
  const hour = value.getHours();
  if (hour < 8) {
    return "24.00-08.00";
  }
  if (hour < 16) {
    return "08.00-16.00";
  }
  return "16.00-24.00";
}

function dateForRequest(value) {
  const text = String(value || "").trim();
  const displayMatch = text.match(/^(\d{2})\.(\d{2})\.(\d{4})$/);
  if (displayMatch) {
    const [, day, month, year] = displayMatch;
    return `${year}-${month}-${day}`;
  }
  return text;
}

function dateForDisplay(value) {
  const text = String(value || "").trim();
  const isoMatch = text.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (isoMatch) {
    const [, year, month, day] = isoMatch;
    return `${day}.${month}.${year}`;
  }
  return text;
}

function setInputValue(selector, value) {
  const input = document.querySelector(selector);
  if (input) {
    input.value = value == null ? "" : String(value);
  }
}

function setMessage(element, text, kind) {
  if (!element) {
    return;
  }
  element.textContent = text;
  element.classList.remove("error", "success", "warning");
  if (kind) {
    element.classList.add(kind);
  }
}

function setButtonBusy(button, busy, busyText) {
  if (!button) {
    return;
  }
  if (!button.dataset.defaultText) {
    button.dataset.defaultText = button.textContent;
  }
  button.disabled = busy;
  button.textContent = busy ? busyText || button.dataset.defaultText : button.dataset.defaultText;
}

function cleanRequired(value) {
  return String(value || "").trim();
}

function cleanOptional(value) {
  const text = String(value || "").trim();
  return text || null;
}

function formatTimestamp(value) {
  if (!value) {
    return "";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return String(value);
  }
  return new Intl.DateTimeFormat("tr-TR", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(parsed);
}

function entryTime(entry) {
  const value = entry.submitted_at || entry.created_at || "";
  const parsed = Date.parse(value);
  return Number.isNaN(parsed) ? 0 : parsed;
}

initLogin();
initMainPage();
