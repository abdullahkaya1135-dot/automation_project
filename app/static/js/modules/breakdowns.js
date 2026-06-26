import { localIsoDate } from "./dates.js?v=20260626-breakdowns-paper-fields";
import {
  machineOptionsFromBootstrap,
  normalizeShopOrderOptions,
  shopOrderProductText,
} from "./bootstrap-options.js?v=20260626-breakdowns-paper-fields";
import {
  cleanOptional,
  cleanRequired,
  uniqueSorted,
} from "./utils.js?v=20260626-breakdowns-paper-fields";

let breakdownMachines = [];
let breakdownShopOrders = [];

export function initializeBreakdownControls() {
  const form = document.querySelector("#breakdown-form");
  if (!form) {
    return;
  }

  applyDefaultBreakdownDate();
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
  breakdownShopOrders = normalizeShopOrderOptions(shopOrderSource?.options);
  breakdownMachines = machineOptionsFromBootstrap(machines, shopOrderSource).map(
    (machine) => ({
      machineCode: machine.machineCode,
      label: machine.machineCode,
    }),
  );
  populateBreakdownMachineSelect();
  updateBreakdownJobOrders();
  applyBreakdownProductFromOrder();
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
  const productInput = document.querySelector("#breakdown-product");
  if (productInput) {
    delete productInput.dataset.autofilledFor;
  }
  applyDefaultBreakdownDate();
  updateBreakdownJobOrders();
}

function applyDefaultBreakdownDate() {
  const dateInput = document.querySelector("#breakdown-date");
  if (dateInput && !dateInput.value) {
    dateInput.value = localIsoDate(new Date());
  }
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
