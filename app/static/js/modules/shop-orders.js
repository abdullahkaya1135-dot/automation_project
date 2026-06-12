import { apiJson } from "../api.js?v=20260612-refactor";
import {
  cleanOptional,
  compareOptionText,
  formatTimestamp,
  setInputValue,
  setMessage,
  uniqueSorted,
} from "./utils.js?v=20260612-refactor";

let shopOrderPairs = [];

export function initializeShopOrderDropdowns() {
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
      workOrderSelect.value = matchingOrders[0].key;
    }
    applyMachineSection(machine);
    void applySelectedOperationDetails();
  });

  workOrderSelect.addEventListener("change", () => {
    const option = selectedShopOrderOption();
    if (!option) {
      clearOperationPrefills();
      return;
    }

    if (machineSelect.value !== option.resourceId) {
      machineSelect.value = option.resourceId;
      populateWorkOrderSelect(option.key, machineSelect.value);
    }
    applyMachineSection(machineSelect.value);
    void applySelectedOperationDetails();
  });

  applyMachineSection(machineSelect.value);
}

export function updateShopOrderOptions(source) {
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
    clearOperationPrefills();
    applyMachineSection("");
    return;
  }

  populateMachineSelect(previousMachine);
  populateWorkOrderSelect(previousWorkOrder, machineSelect.value);
  setShopOrderSelectsEnabled(true);
  applyMachineSection(machineSelect.value);
  void applySelectedOperationDetails();
}

export function resetShopOrderDropdowns() {
  if (!shopOrderPairs.length) {
    return;
  }
  populateMachineSelect("");
  populateWorkOrderSelect("", "");
  clearOperationPrefills();
  applyMachineSection("");
}

export function selectedShopOrderOption() {
  const workOrderSelect = document.querySelector("#work-order");
  if (!workOrderSelect || !workOrderSelect.value) {
    return null;
  }
  return shopOrderPairs.find((pair) => pair.key === workOrderSelect.value) || null;
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

    const releaseNo = cleanOptional(option?.release_no) || "*";
    const sequenceNo = cleanOptional(option?.sequence_no) || "*";
    const rawOperationNo = option?.operation_no == null ? null : Number(option.operation_no);
    const operationNo = Number.isFinite(rawOperationNo) ? rawOperationNo : null;
    const partNo = cleanOptional(option?.part_no);
    const partDescription = cleanOptional(option?.part_description);
    const key = `${orderNo}\u0000${resourceId}\u0000${releaseNo}\u0000${sequenceNo}\u0000${operationNo ?? ""}`;
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    pairs.push({
      key,
      orderNo,
      resourceId,
      releaseNo,
      sequenceNo,
      operationNo,
      partNo,
      partDescription,
    });
  }

  pairs.sort((left, right) => {
    const machineComparison = compareOptionText(left.resourceId, right.resourceId);
    if (machineComparison) {
      return machineComparison;
    }
    const orderComparison = compareOptionText(left.orderNo, right.orderNo);
    if (orderComparison) {
      return orderComparison;
    }
    return (left.operationNo || 0) - (right.operationNo || 0);
  });
  return pairs;
}

function updateShopOrderSourceStatus(source, pairCount) {
  const status = document.querySelector("#shop-order-source-status");
  if (!status) {
    return;
  }

  status.classList.remove(
    "status-muted",
    "status-success",
    "status-warning",
    "status-error",
  );
  if (pairCount > 0) {
    const orderCount = source?.order_count
      || uniqueSorted(shopOrderPairs.map((pair) => pair.orderNo)).length;
    const machineCount = source?.resource_count
      || uniqueSorted(shopOrderPairs.map((pair) => pair.resourceId)).length;
    const sourceLabel = source?.source === "ifs" ? "IFS" : "Dosya";
    if (source?.offline_cached_at) {
      status.textContent = `${orderCount} iş emri (offline)`;
      status.title = `${sourceLabel}: ${machineCount} makine / ${pairCount} eşleşme / ${formatTimestamp(source.offline_cached_at)}`;
      status.classList.add("status-warning");
      return;
    }
    status.textContent = `${orderCount} iş emri`;
    status.title = `${sourceLabel}: ${machineCount} makine / ${pairCount} eşleşme`;
    status.classList.add("status-success");
    return;
  }

  status.textContent = source?.source === "ifs" ? "IFS iş emri yok" : "İş emri listesi yok";
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
  setSelectOptionObjects(workOrderSelect, orders, "İş emri seçin", selectedValue);
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

function setSelectOptionObjects(select, values, placeholder, selectedValue) {
  const placeholderOption = new Option(placeholder, "");
  const duplicateCounts = values.reduce((counts, option) => {
    const countKey = `${option.resourceId}\u0000${option.orderNo}`;
    counts.set(countKey, (counts.get(countKey) || 0) + 1);
    return counts;
  }, new Map());
  const options = values.map((value) => {
    const countKey = `${value.resourceId}\u0000${value.orderNo}`;
    const label = duplicateCounts.get(countKey) > 1 && value.operationNo
      ? `${value.orderNo} / Op ${value.operationNo}`
      : value.orderNo;
    return new Option(label, value.key);
  });
  select.replaceChildren(placeholderOption, ...options);
  select.value = values.some((value) => value.key === selectedValue)
    ? selectedValue
    : "";
}

function orderOptionsForMachine(machine) {
  return shopOrderPairs.filter((pair) => !machine || pair.resourceId === machine);
}

function machineSection(machine) {
  const match = String(machine || "").match(/\d+/);
  if (!match) {
    return "";
  }
  const code = Number(match[0]);
  if (code === 271 || (code >= 100 && code <= 199)) {
    return "first";
  }
  if (code >= 200 && code <= 599) {
    return "second";
  }
  return "first";
}

function applyMachineSection(machine) {
  const section = machineSection(machine);
  const sectionFields = document.querySelectorAll("[data-section-field]");
  for (const container of sectionFields) {
    const visible = section && container.dataset.sectionField === section;
    container.hidden = !visible;
    for (const input of container.querySelectorAll("input, select, textarea")) {
      input.disabled = !visible;
      if (!visible) {
        input.value = "";
      }
    }
  }
}

function clearOperationPrefills() {
  setInputValue("#product-name", "");
  setInputValue("#raw-material", "");
  setMaterialOptions([]);
}

function productTextForOption(option) {
  if (!option) {
    return "";
  }
  if (option.partNo && option.partDescription?.startsWith(option.partNo)) {
    return option.partDescription;
  }
  return [option.partNo, option.partDescription].filter(Boolean).join(" - ");
}

async function applySelectedOperationDetails() {
  const option = selectedShopOrderOption();
  if (!option) {
    clearOperationPrefills();
    return;
  }

  setInputValue("#product-name", productTextForOption(option));
  await prefillRawMaterial(option);
}

async function prefillRawMaterial(option) {
  const rawMaterialInput = document.querySelector("#raw-material");
  if (!rawMaterialInput || !option || !option.operationNo) {
    setMaterialOptions([]);
    return;
  }
  rawMaterialInput.value = "";

  const query = new URLSearchParams({
    order_no: option.orderNo,
    release_no: option.releaseNo || "*",
    sequence_no: option.sequenceNo || "*",
    operation_no: String(option.operationNo),
  });

  try {
    const payload = await apiJson(`/api/ifs/operation-hm02-materials?${query}`);
    const partNumbers = uniqueSorted(
      (Array.isArray(payload.materials) ? payload.materials : [])
        .map((material) => cleanOptional(material.part_no)),
    );
    setMaterialOptions(partNumbers);
    if (partNumbers.length === 1) {
      rawMaterialInput.value = partNumbers[0];
    }
  } catch (error) {
    setMaterialOptions([]);
    setMessage(
      document.querySelector("#entry-message"),
      `Hammadde otomatik alınamadı; elle girebilirsiniz. ${error.message}`,
      "warning",
    );
  }
}

function setMaterialOptions(partNumbers) {
  const dataList = document.querySelector("#raw-material-options");
  if (!dataList) {
    return;
  }
  dataList.replaceChildren(
    ...partNumbers.map((partNumber) => new Option(partNumber, partNumber)),
  );
}
