import { apiJson } from "../api.js?v=20260629-shift-manager-labels-v1";
import { localIsoDate } from "./dates.js?v=20260629-shift-manager-labels-v1";
import {
  machineOptionsFromBootstrap,
  normalizeShopOrderOptions,
  shopOrderProductText,
} from "./bootstrap-options.js?v=20260629-shift-manager-labels-v1";
import {
  cleanOptional,
  cleanRequired,
  compareOptionText,
  setMessage,
  uniqueSorted,
} from "./utils.js?v=20260629-shift-manager-labels-v1";

let breakdownMachines = [];
let breakdownShopOrders = [];
let fallbackBreakdownMachines = [];
let fallbackBreakdownShopOrders = [];
let breakdownContextRequestId = 0;

export function initializeBreakdownControls() {
  const form = document.querySelector("#breakdown-form");
  if (!form) {
    return;
  }

  applyDefaultBreakdownDate();
  document
    .querySelector("#breakdown-date")
    ?.addEventListener("change", () => {
      clearBreakdownDateScopedInputs();
      void refreshBreakdownContextForDate();
    });
  document
    .querySelector("#breakdown-machine")
    ?.addEventListener("change", () => {
      updateBreakdownJobOrders();
      applyBreakdownProductFromOrder();
    });
  document
    .querySelector("#breakdown-job-order")
    ?.addEventListener("input", applyBreakdownProductFromOrder);
  document
    .querySelector("#breakdown-product")
    ?.addEventListener("input", (event) => {
      delete event.currentTarget.dataset.autofilledFor;
    });
}

export function updateBreakdownBootstrap(machines, shopOrderSource) {
  fallbackBreakdownShopOrders = normalizeShopOrderOptions(
    shopOrderSource?.options,
  );
  fallbackBreakdownMachines = machineOptionsFromBootstrap(
    machines,
    shopOrderSource,
  ).map((machine) => ({
    machineCode: machine.machineCode,
    label: machine.machineCode,
  }));
  applyBreakdownOptions(fallbackBreakdownMachines, fallbackBreakdownShopOrders);
  void refreshBreakdownContextForDate();
}

export function breakdownRequestBody(form) {
  const formData = new FormData(form);
  const durationMinutes = Number(formData.get("duration_minutes"));
  if (!Number.isInteger(durationMinutes) || durationMinutes < 1) {
    throw new Error("Sure 1 veya daha buyuk tam sayi olmalidir.");
  }

  return {
    record_date: cleanRequired(formData.get("record_date")),
    machine_code: cleanRequired(formData.get("machine_code")),
    shift: cleanRequired(formData.get("shift")),
    reason: cleanRequired(formData.get("reason")),
    duration_minutes: durationMinutes,
    job_order: cleanOptional(formData.get("job_order")),
    produced_product: cleanOptional(formData.get("produced_product")),
  };
}

export function resetBreakdownForm(form) {
  form.reset();
  clearBreakdownDateScopedInputs();
  applyDefaultBreakdownDate();
  updateBreakdownJobOrders();
  void refreshBreakdownContextForDate();
}

function applyDefaultBreakdownDate() {
  const dateInput = document.querySelector("#breakdown-date");
  if (dateInput && !dateInput.value) {
    dateInput.value = previousLocalIsoDate();
  }
}

function previousLocalIsoDate(value = new Date()) {
  const previousDay = new Date(value.getTime());
  previousDay.setDate(previousDay.getDate() - 1);
  return localIsoDate(previousDay);
}

async function refreshBreakdownContextForDate() {
  const requestId = ++breakdownContextRequestId;
  const dateInput = document.querySelector("#breakdown-date");
  const recordDate = cleanOptional(dateInput?.value);
  if (!dateInput || !recordDate) {
    setBreakdownContextMessage("", "");
    applyFallbackBreakdownOptions();
    return;
  }

  try {
    const query = new URLSearchParams({ record_date: recordDate });
    const payload = await apiJson(`/api/breakdowns/context?${query.toString()}`);
    if (!isCurrentBreakdownContextRequest(requestId, recordDate)) {
      return;
    }

    const contextOptions = normalizeBreakdownContextOptions(payload?.options);
    if (payload?.record_date !== recordDate) {
      applyFallbackBreakdownOptions();
      return;
    }
    if (!contextOptions.length) {
      applyFallbackBreakdownOptions();
      setBreakdownContextMessage(
        "Secilen tarih icin makine/is emri iceren proses kaydi yok; genel liste gosteriliyor.",
        "warning",
      );
      return;
    }

    setBreakdownContextMessage("", "");
    applyBreakdownOptions(
      machineOptionsFromContext(contextOptions),
      contextOptions,
    );
  } catch (_error) {
    if (isCurrentBreakdownContextRequest(requestId, recordDate)) {
      applyFallbackBreakdownOptions();
      setBreakdownContextMessage(
        "Proses kaydi okunamadi; genel liste gosteriliyor.",
        "warning",
      );
    }
  }
}

function setBreakdownContextMessage(text, kind) {
  setMessage(document.querySelector("#breakdown-context-message"), text, kind);
}

function isCurrentBreakdownContextRequest(requestId, recordDate) {
  return requestId === breakdownContextRequestId
    && document.querySelector("#breakdown-date")?.value === recordDate;
}

function applyFallbackBreakdownOptions() {
  applyBreakdownOptions(fallbackBreakdownMachines, fallbackBreakdownShopOrders);
}

function applyBreakdownOptions(machines, shopOrders) {
  breakdownMachines = machines;
  breakdownShopOrders = shopOrders;
  populateBreakdownMachineSelect();
  updateBreakdownJobOrders();
  reconcileBreakdownDateScopedInputs();
  applyBreakdownProductFromOrder();
}

function clearBreakdownDateScopedInputs() {
  const orderInput = document.querySelector("#breakdown-job-order");
  if (orderInput) {
    orderInput.value = "";
  }
  const productInput = document.querySelector("#breakdown-product");
  if (productInput) {
    productInput.value = "";
    delete productInput.dataset.autofilledFor;
  }
}

function reconcileBreakdownDateScopedInputs() {
  const orderInput = document.querySelector("#breakdown-job-order");
  const productInput = document.querySelector("#breakdown-product");
  const orderNo = cleanOptional(orderInput?.value);
  if (!orderNo) {
    return;
  }

  const option = selectedBreakdownShopOrder();
  if (!option) {
    clearBreakdownDateScopedInputs();
    return;
  }

  const productText = shopOrderProductText(option);
  const productValue = cleanOptional(productInput?.value);
  if (productValue && productValue !== productText) {
    productInput.value = "";
    delete productInput.dataset.autofilledFor;
  }
}

function normalizeBreakdownContextOptions(options) {
  if (!Array.isArray(options)) {
    return [];
  }
  const seen = new Set();
  const normalized = [];
  for (const option of options) {
    const resourceId = cleanOptional(option?.machine_code);
    const orderNo = cleanOptional(option?.job_order);
    if (!resourceId || !orderNo) {
      continue;
    }
    const partDescription = cleanOptional(option?.produced_product);
    const entryId = cleanOptional(option?.entry_id);
    const submittedAt = cleanOptional(option?.submitted_at);
    const key = [
      resourceId,
      orderNo,
      partDescription || "",
      entryId || submittedAt || "",
    ].join("\u0000");
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    normalized.push({
      key,
      orderNo,
      resourceId,
      releaseNo: "*",
      sequenceNo: "*",
      operationNo: null,
      partNo: null,
      partDescription,
      entryId,
      submittedAt,
    });
  }
  normalized.sort(compareBreakdownContextOptions);
  return normalized;
}

function compareBreakdownContextOptions(left, right) {
  const machineComparison = compareOptionText(left.resourceId, right.resourceId);
  if (machineComparison) {
    return machineComparison;
  }
  const orderComparison = compareOptionText(left.orderNo, right.orderNo);
  if (orderComparison) {
    return orderComparison;
  }
  const leftTime = Date.parse(left.submittedAt || "");
  const rightTime = Date.parse(right.submittedAt || "");
  if (Number.isFinite(leftTime) && Number.isFinite(rightTime)) {
    return rightTime - leftTime;
  }
  if (Number.isFinite(leftTime)) {
    return -1;
  }
  if (Number.isFinite(rightTime)) {
    return 1;
  }
  return compareOptionText(
    left.partDescription || "",
    right.partDescription || "",
  );
}

function machineOptionsFromContext(options) {
  return uniqueSorted(options.map((option) => option.resourceId)).map(
    (machineCode) => ({ machineCode, label: machineCode }),
  );
}

function populateBreakdownMachineSelect() {
  const select = document.querySelector("#breakdown-machine");
  if (!select) {
    return;
  }
  const selectedValue = select.value;
  const options = breakdownMachines.map((machine) => (
    new Option(machine.label, machine.machineCode)
  ));
  select.replaceChildren(new Option("Makine secin", ""), ...options);
  select.value = breakdownMachines.some(
    (machine) => machine.machineCode === selectedValue,
  )
    ? selectedValue
    : "";
  select.disabled = breakdownMachines.length === 0;
}

function updateBreakdownJobOrders() {
  const machine = cleanOptional(
    document.querySelector("#breakdown-machine")?.value,
  );
  const orderList = document.querySelector("#breakdown-job-order-options");
  const productList = document.querySelector("#breakdown-product-options");

  const orders = breakdownShopOrders.filter(
    (option) => !machine || option.resourceId === machine,
  );
  if (orderList) {
    orderList.replaceChildren(
      ...uniqueSorted(orders.map((option) => option.orderNo)).map(
        (orderNo) => new Option(orderNo, orderNo),
      ),
    );
  }
  if (productList) {
    productList.replaceChildren(
      ...uniqueSorted(orders.map(shopOrderProductText)).map(
        (product) => new Option(product, product),
      ),
    );
  }
}

function applyBreakdownProductFromOrder() {
  const productInput = document.querySelector("#breakdown-product");
  if (!productInput) {
    return;
  }

  const option = selectedBreakdownShopOrder();
  const productText = shopOrderProductText(option);
  const canAutofill = !productInput.value || productInput.dataset.autofilledFor;
  if (productText && canAutofill) {
    productInput.value = productText;
    productInput.dataset.autofilledFor = option.key;
    return;
  }
  if (!productText && productInput.dataset.autofilledFor) {
    productInput.value = "";
    delete productInput.dataset.autofilledFor;
  }
}

function selectedBreakdownShopOrder() {
  const machine = cleanOptional(
    document.querySelector("#breakdown-machine")?.value,
  );
  const orderNo = cleanOptional(
    document.querySelector("#breakdown-job-order")?.value,
  );
  if (!machine || !orderNo) {
    return null;
  }
  return breakdownShopOrders.find(
    (option) => option.resourceId === machine && option.orderNo === orderNo,
  ) || null;
}
