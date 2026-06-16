import { applyMachineSection } from "./machine-section.js?v=20260615-shop-orders";
import { applyOperationDetails, clearOperationPrefills } from "./materials.js?v=20260615-shop-orders";
import { normalizeShopOrderPairs } from "./normalization.js?v=20260615-shop-orders";
import {
  findShopOrderPair,
  hasShopOrderPairs,
  orderOptionsForMachine,
  setShopOrderPairs,
  shopOrderPairs,
} from "./state.js?v=20260615-shop-orders";
import { updateShopOrderSourceStatus } from "./status.js?v=20260615-shop-orders";
import { uniqueSorted } from "../utils.js?v=20260612-refactor";

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
    void applyOperationDetails(selectedShopOrderOption());
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
    void applyOperationDetails(option);
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
  const pairs = normalizeShopOrderPairs(source?.options);
  setShopOrderPairs(pairs);
  updateShopOrderSourceStatus(source, pairs);

  if (!pairs.length) {
    setSelectOptions(machineSelect, [], "Makine listesi bulunamad\u0131", "");
    setSelectOptions(workOrderSelect, [], "\u0130\u015f emri listesi bulunamad\u0131", "");
    setShopOrderSelectsEnabled(false);
    clearOperationPrefills();
    applyMachineSection("");
    return;
  }

  populateMachineSelect(previousMachine);
  populateWorkOrderSelect(previousWorkOrder, machineSelect.value);
  setShopOrderSelectsEnabled(true);
  applyMachineSection(machineSelect.value);
  void applyOperationDetails(selectedShopOrderOption());
}

export function resetShopOrderDropdowns() {
  if (!hasShopOrderPairs()) {
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
  return findShopOrderPair(workOrderSelect.value);
}

function populateMachineSelect(selectedValue) {
  const machineSelect = document.querySelector("#machine-select");
  if (!machineSelect) {
    return;
  }
  setSelectOptions(
    machineSelect,
    uniqueSorted(shopOrderPairs().map((pair) => pair.resourceId)),
    "Makine se\u00e7in",
    selectedValue,
  );
}

function populateWorkOrderSelect(selectedValue, machine) {
  const workOrderSelect = document.querySelector("#work-order");
  if (!workOrderSelect) {
    return;
  }
  const orders = orderOptionsForMachine(machine);
  setSelectOptionObjects(workOrderSelect, orders, "\u0130\u015f emri se\u00e7in", selectedValue);
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
