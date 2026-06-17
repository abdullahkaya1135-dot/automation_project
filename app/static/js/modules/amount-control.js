import { AMOUNT_CONTROL_SHIFTS } from "./constants.js?v=20260617-amount-control";
import { localIsoDate } from "./dates.js?v=20260617-amount-control";
import {
  cleanOptional,
  cleanRequired,
  compareOptionText,
  uniqueSorted,
} from "./utils.js?v=20260617-amount-control";

let amountControlMachines = [];
let amountControlShopOrders = [];
let breakdownRowCounter = 0;

export function initializeAmountControlControls() {
  const form = document.querySelector("#amount-control-form");
  if (!form) {
    return;
  }

  applyDefaultAmountControlDate();
  form.addEventListener("click", handleAmountControlClick);
  document
    .querySelector("#amount-control-machine")
    ?.addEventListener("change", updateAmountControlJobOrders);
}

export function updateAmountControlBootstrap(machines, shopOrderSource) {
  amountControlShopOrders = normalizeShopOrderOptions(shopOrderSource?.options);
  amountControlMachines = normalizeMachineOptions(machines);
  if (!amountControlMachines.length) {
    amountControlMachines = uniqueSorted(
      amountControlShopOrders.map((option) => option.resourceId),
    ).map((machineCode) => ({ machineCode, label: machineCode }));
  }
  amountControlMachines.sort((left, right) => (
    compareOptionText(left.machineCode, right.machineCode)
  ));
  populateAmountControlMachineSelect();
  updateAmountControlJobOrders();
}

export function amountControlRequestBodies(form) {
  const formData = new FormData(form);
  const recordDate = cleanRequired(formData.get("record_date"));
  const machineCode = cleanRequired(formData.get("machine_code"));
  const jobOrder = cleanRequired(formData.get("job_order"));
  const bodies = [];

  for (const shift of AMOUNT_CONTROL_SHIFTS) {
    const shiftSection = form.querySelector(
      `.amount-control-shift[data-shift="${shift}"]`,
    );
    if (!shiftSection) {
      throw new Error(`Vardiya alani bulunamadi: ${shift}`);
    }
    const quantityInput = shiftSection.querySelector("[name='produced_quantity']");
    const producedQuantity = Number(quantityInput?.value);
    if (!Number.isInteger(producedQuantity) || producedQuantity < 0) {
      throw new Error("Uretilen adet 0 veya daha buyuk tam sayi olmalidir.");
    }
    bodies.push({
      record_date: recordDate,
      machine_code: machineCode,
      job_order: jobOrder,
      shift,
      worker_names: cleanRequired(
        shiftSection.querySelector("[name='worker_names']")?.value,
      ),
      produced_quantity: producedQuantity,
      breakdowns: breakdownRequestBodies(shiftSection),
    });
  }

  return bodies;
}

export function resetAmountControlForm(form) {
  form.reset();
  for (const row of form.querySelectorAll("[data-breakdown-row]")) {
    row.remove();
  }
  applyDefaultAmountControlDate();
  updateAmountControlJobOrders();
}

function applyDefaultAmountControlDate() {
  const dateInput = document.querySelector("#amount-control-date");
  if (dateInput && !dateInput.value) {
    dateInput.value = localIsoDate(new Date());
  }
}

function handleAmountControlClick(event) {
  const addButton = event.target.closest("[data-add-breakdown]");
  if (addButton) {
    const shiftSection = addButton.closest(".amount-control-shift");
    if (shiftSection) {
      addBreakdownRow(shiftSection);
    }
    return;
  }

  const removeButton = event.target.closest("[data-remove-breakdown]");
  if (removeButton) {
    removeButton.closest("[data-breakdown-row]")?.remove();
  }
}

function addBreakdownRow(shiftSection) {
  const container = shiftSection.querySelector("[data-breakdowns]");
  if (!container) {
    return;
  }

  const row = document.createElement("div");
  row.className = "breakdown-row";
  row.dataset.breakdownRow = "true";

  const grid = document.createElement("div");
  grid.className = "field-grid compact-grid";
  grid.append(
    fieldElement("Uretilen urun", breakdownInput("produced_product", "text", true)),
    fieldElement("Durus nedeni", breakdownInput("stop_reason", "text", true)),
    fieldElement(
      "Sure (dk)",
      breakdownInput("duration_minutes", "number", true, {
        min: "1",
        step: "1",
        inputmode: "numeric",
      }),
    ),
    fieldElement("Durus baslangici", breakdownInput("stopped_at", "datetime-local")),
    fieldElement("Durus bitisi", breakdownInput("resumed_at", "datetime-local")),
  );

  const action = document.createElement("div");
  action.className = "field breakdown-actions";
  const removeButton = document.createElement("button");
  removeButton.type = "button";
  removeButton.className = "secondary-action";
  removeButton.dataset.removeBreakdown = "true";
  removeButton.textContent = "Kaldir";
  action.appendChild(removeButton);
  grid.appendChild(action);

  row.appendChild(grid);
  container.appendChild(row);
}

function fieldElement(labelText, input) {
  const field = document.createElement("div");
  field.className = "field";

  const label = document.createElement("label");
  const inputId = `amount-breakdown-${breakdownRowCounter++}`;
  label.htmlFor = inputId;
  label.textContent = labelText;
  input.id = inputId;

  field.append(label, input);
  return field;
}

function breakdownInput(name, type, required = false, attributes = {}) {
  const input = document.createElement("input");
  input.name = name;
  input.type = type;
  input.autocomplete = "off";
  input.required = required;
  for (const [key, value] of Object.entries(attributes)) {
    input.setAttribute(key, value);
  }
  return input;
}

function breakdownRequestBodies(shiftSection) {
  return Array.from(shiftSection.querySelectorAll("[data-breakdown-row]")).map(
    (row) => {
      const formData = new FormData();
      for (const input of row.querySelectorAll("input")) {
        formData.set(input.name, input.value);
      }
      return {
        produced_product: cleanRequired(formData.get("produced_product")),
        stop_reason: cleanRequired(formData.get("stop_reason")),
        duration_minutes: Number(formData.get("duration_minutes")),
        stopped_at: cleanOptional(formData.get("stopped_at")),
        resumed_at: cleanOptional(formData.get("resumed_at")),
      };
    },
  );
}

function normalizeMachineOptions(machines) {
  if (!Array.isArray(machines)) {
    return [];
  }
  const seen = new Set();
  const normalized = [];
  for (const machine of machines) {
    const machineCode = cleanOptional(machine?.machine_code);
    if (!machineCode || seen.has(machineCode)) {
      continue;
    }
    seen.add(machineCode);
    const hallName = cleanOptional(machine?.hall_name);
    normalized.push({
      machineCode,
      label: hallName ? `${machineCode} / ${hallName}` : machineCode,
    });
  }
  return normalized;
}

function normalizeShopOrderOptions(options) {
  if (!Array.isArray(options)) {
    return [];
  }
  const seen = new Set();
  const normalized = [];
  for (const option of options) {
    const orderNo = cleanOptional(option?.order_no);
    const resourceId = cleanOptional(option?.resource_id);
    if (!orderNo || !resourceId) {
      continue;
    }
    const key = `${resourceId}\u0000${orderNo}`;
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    normalized.push({ orderNo, resourceId });
  }
  return normalized;
}

function populateAmountControlMachineSelect() {
  const select = document.querySelector("#amount-control-machine");
  if (!select) {
    return;
  }
  const selectedValue = select.value;
  const options = amountControlMachines.map((machine) => (
    new Option(machine.label, machine.machineCode)
  ));
  select.replaceChildren(new Option("Makine secin", ""), ...options);
  select.value = amountControlMachines.some(
    (machine) => machine.machineCode === selectedValue,
  )
    ? selectedValue
    : "";
  select.disabled = amountControlMachines.length === 0;
}

function updateAmountControlJobOrders() {
  const machine = cleanOptional(
    document.querySelector("#amount-control-machine")?.value,
  );
  const dataList = document.querySelector("#amount-control-job-order-options");
  if (!dataList) {
    return;
  }
  const orders = uniqueSorted(
    amountControlShopOrders
      .filter((option) => !machine || option.resourceId === machine)
      .map((option) => option.orderNo),
  );
  dataList.replaceChildren(
    ...orders.map((orderNo) => new Option(orderNo, orderNo)),
  );
}
