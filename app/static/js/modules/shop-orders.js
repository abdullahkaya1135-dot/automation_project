import {
  cleanOptional,
  compareOptionText,
  formatTimestamp,
  setInputValue,
  updateStatusPill,
  uniqueSorted,
} from "./utils.js?v=20260629-label-material-availability-v1";

let shopOrderPairs = [];

export function initializeShopOrderDropdowns() {
  const machineSelect = document.querySelector("#machine-select");
  const workOrderInput = document.querySelector("#work-order");
  if (!machineSelect || !workOrderInput) {
    return;
  }

  machineSelect.addEventListener("change", () => {
    const machine = machineSelect.value;
    populateWorkOrderSelect(machine);
    applyMachineSection(machine);
    applySelectedOperationDetails();
  });

  applyMachineSection(machineSelect.value);
}

export function updateShopOrderOptions(source) {
  shopOrderPairs = normalizeShopOrderPairs(source?.options);
  updateShopOrderSourceStatus(source, shopOrderPairs.length);

  const machineSelect = document.querySelector("#machine-select");
  const workOrderInput = document.querySelector("#work-order");
  if (!machineSelect || !workOrderInput) {
    return;
  }

  const previousMachine = machineSelect.value;
  if (!shopOrderPairs.length) {
    setSelectOptions(machineSelect, [], "Makine listesi bulunamadÄ±", "");
    setWorkOrderInput(workOrderInput, "", "");
    setShopOrderSelectsEnabled(false);
    clearOperationPrefills();
    applyMachineSection("");
    return;
  }

  populateMachineSelect(previousMachine);
  populateWorkOrderSelect(machineSelect.value);
  setShopOrderSelectsEnabled(true);
  applyMachineSection(machineSelect.value);
  applySelectedOperationDetails();
}

export function resetShopOrderDropdowns() {
  if (!shopOrderPairs.length) {
    return;
  }
  populateMachineSelect("");
  populateWorkOrderSelect("");
  clearOperationPrefills();
  applyMachineSection("");
}

export function selectedShopOrderOption() {
  const selectedKey = selectedWorkOrderKey();
  if (!selectedKey) {
    return null;
  }
  return shopOrderPairs.find((pair) => pair.key === selectedKey) || null;
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

  if (pairCount > 0) {
    const orderCount = source?.order_count
      || uniqueSorted(shopOrderPairs.map((pair) => pair.orderNo)).length;
    const machineCount = source?.resource_count
      || uniqueSorted(shopOrderPairs.map((pair) => pair.resourceId)).length;
    const sourceLabel = String(source?.source || "").startsWith("ifs") ? "IFS" : "Dosya";
    if (source?.offline_cached_at) {
      updateStatusPill(status, `${orderCount} iÅŸ emri (offline)`, "warning");
      status.title = `${sourceLabel}: ${machineCount} makine / ${pairCount} eÅŸleÅŸme / ${formatTimestamp(source.offline_cached_at)}`;
      return;
    }
    updateStatusPill(status, `${orderCount} iÅŸ emri`, "success");
    status.title = `${sourceLabel}: ${machineCount} makine / ${pairCount} eÅŸleÅŸme`;
    return;
  }

  updateStatusPill(
    status,
    source?.source === "ifs" ? "IFS iÅŸ emri yok" : "Ä°ÅŸ emri listesi yok",
    "warning",
  );
  status.title = source?.last_error || "";
}

function populateMachineSelect(selectedValue) {
  const machineSelect = document.querySelector("#machine-select");
  if (!machineSelect) {
    return;
  }
  setSelectOptions(
    machineSelect,
    uniqueSorted(shopOrderPairs.map((pair) => pair.resourceId)),
    "Makine seÃ§in",
    selectedValue,
  );
}

function populateWorkOrderSelect(machine) {
  const workOrderInput = document.querySelector("#work-order");
  if (!workOrderInput) {
    return;
  }
  const orders = orderOptionsForMachine(machine);
  setWorkOrderOption(workOrderInput, orders);
}

function setShopOrderSelectsEnabled(enabled) {
  const machineSelect = document.querySelector("#machine-select");
  if (machineSelect) {
    machineSelect.disabled = !enabled;
  }

  const workOrderInput = document.querySelector("#work-order");
  if (workOrderInput) {
    workOrderInput.disabled = !enabled;
    workOrderInput.readOnly = true;
  }
}

function selectedWorkOrderKey() {
  const workOrderInput = document.querySelector("#work-order");
  return workOrderInput?.dataset.optionKey || "";
}

function setWorkOrderInput(input, optionKey, label) {
  input.dataset.optionKey = optionKey;
  input.value = label;
}

function workOrderLabel(option, orders) {
  const duplicateCount = orders.filter((value) => (
    value.resourceId === option.resourceId && value.orderNo === option.orderNo
  )).length;
  if (duplicateCount > 1 && option.operationNo) {
    return `${option.orderNo} / Op ${option.operationNo}`;
  }
  return option.orderNo;
}

function setWorkOrderOption(input, orders) {
  if (orders.length !== 1) {
    setWorkOrderInput(input, "", "");
    return;
  }

  const option = orders[0];
  setWorkOrderInput(input, option.key, workOrderLabel(option, orders));
}

function setSelectOptions(select, values, placeholder, selectedValue) {
  const placeholderOption = new Option(placeholder, "");
  const options = values.map((value) => new Option(value, value));
  select.replaceChildren(placeholderOption, ...options);
  select.value = values.includes(selectedValue) ? selectedValue : "";
}

function orderOptionsForMachine(machine) {
  return machine ? shopOrderPairs.filter((pair) => pair.resourceId === machine) : [];
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

function applySelectedOperationDetails() {
  const option = selectedShopOrderOption();
  if (!option) {
    clearOperationPrefills();
    return;
  }

  setInputValue("#product-name", productTextForOption(option));
}
