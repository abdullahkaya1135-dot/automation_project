import { apiJson } from "../api.js?v=20260629-label-material-availability-v1";
import {
  renderListError,
  renderLoading,
} from "./render.js?v=20260629-label-material-availability-v1";
import {
  displayValue,
  setButtonBusy,
  setMessage,
  updateStatusPill,
} from "./utils.js?v=20260629-label-material-availability-v1";

const NEAR_COMPLETE_THRESHOLD = 3;
const NOTIFICATION_CHECKBOX_SELECTOR = "input[data-shift-manager-notified]";
const notificationRows = new WeakMap();

const ROW_KEYS = [
  "rows",
  "machines",
  "items",
  "results",
  "near_complete",
  "near_complete_machines",
  "near_complete_jobs",
];
const MACHINE_KEYS = [
  "machine",
  "machine_code",
  "machineCode",
  "resource_id",
  "resourceId",
  "preferred_resource_id",
  "preferredResourceId",
];
const CURRENT_ORDER_KEYS = [
  "current_order_no",
  "currentOrderNo",
  "current_work_order",
  "currentWorkOrder",
  "current_job_order",
  "currentJobOrder",
  "current_shop_order_no",
  "work_order_no",
  "job_order_no",
  "shop_order_no",
  "order_no",
];
const NEXT_ORDER_KEYS = [
  "next_order_no",
  "nextOrderNo",
  "next_work_order",
  "nextWorkOrder",
  "next_job_order",
  "nextJobOrder",
  "next_shop_order_no",
  "nextShopOrderNo",
];
const PLAN_LINE_KEYS = [
  "plan_line",
  "planLine",
  "planning_line",
  "planningLine",
  "planning_row",
  "planningRow",
  "planning_row_no",
  "planningRowNo",
  "planning_row_number",
  "planningRowNumber",
  "planning_order_line",
  "planningOrderLine",
  "next_order.plan_line",
  "next_order.planning_line",
];
const STATUS_KEYS = [
  "status",
  "status_label",
  "statusLabel",
  "status_text",
  "statusText",
  "message",
];
const STATUS_KIND_KEYS = ["status_kind", "statusKind", "severity", "state"];
const NOTIFIED_KEYS = [
  "notified",
  "is_notified",
  "isNotified",
  "notification_sent",
  "notificationSent",
  "informed",
  "is_informed",
  "isInformed",
];

export function initializeShiftManagerSection() {
  const button = document.querySelector("#run-shift-manager-check");
  const container = document.querySelector("#shift-manager-results");
  if (!button && !container) {
    return;
  }

  if (button) {
    button.addEventListener("click", () => {
      void loadShiftManagerNearComplete(button);
    });
  }

  if (container) {
    container.addEventListener("change", handleShiftManagerNotificationChange);
  }
}

async function loadShiftManagerNearComplete(button = null) {
  const message = document.querySelector("#shift-manager-message");
  const container = document.querySelector("#shift-manager-results");
  const query = new URLSearchParams({
    threshold: String(NEAR_COMPLETE_THRESHOLD),
  });

  setMessage(message, "Yaklaşan işler kontrol ediliyor...", "");
  renderLoading(container, "Kalan paket/palet ve plan satırları kontrol ediliyor...");
  setButtonBusy(button, true, "Kontrol ediliyor");

  try {
    const payload = await apiJson(
      `/api/shift-manager/near-complete?${query.toString()}`,
    );
    renderShiftManagerResults(container, payload);

    const rows = shiftManagerRows(payload);
    const nextJobFoundCount = summaryValue(payload, [
      "next_job_found_count",
      "nextJobFoundCount",
      "next_order_found_count",
      "nextOrderFoundCount",
    ]) ?? rows.filter((row) => rowValue(row, NEXT_ORDER_KEYS)).length;

    if (!rows.length) {
      setMessage(message, "Yaklaşan iş bulunmadı.", "success");
      return;
    }

    setMessage(
      message,
      `${rows.length} yaklaşan iş kontrol edildi, ${displayValue(nextJobFoundCount)} sonraki iş bulundu.`,
      Number(nextJobFoundCount) < rows.length ? "warning" : "success",
    );
  } catch (error) {
    setMessage(message, `Yaklaşan işler kontrol edilemedi: ${error.message}`, "error");
    renderListError(container, `Yaklaşan işler kontrol edilemedi: ${error.message}`);
  } finally {
    setButtonBusy(button, false);
  }
}

function handleShiftManagerNotificationChange(event) {
  const checkbox = event.target;
  if (!(checkbox instanceof HTMLInputElement)) {
    return;
  }
  if (!checkbox.matches(NOTIFICATION_CHECKBOX_SELECTOR)) {
    return;
  }

  void updateShiftManagerNotification(checkbox);
}

async function updateShiftManagerNotification(checkbox) {
  const message = document.querySelector("#shift-manager-message");
  const row = notificationRows.get(checkbox) || {};
  const previousChecked = checkbox.dataset.previousChecked === "true";
  const nextChecked = checkbox.checked;
  const nextOrderNo = rowValue(row, NEXT_ORDER_KEYS) || checkbox.dataset.nextOrderNo;

  if (!nextOrderNo) {
    checkbox.checked = previousChecked;
    checkbox.disabled = true;
    return;
  }

  checkbox.disabled = true;
  setMessage(message, "Bilgilendirme durumu güncelleniyor...", "");

  try {
    await apiJson("/api/shift-manager/notifications", {
      method: "PUT",
      body: shiftManagerNotificationBody(row, nextChecked),
    });
    checkbox.dataset.previousChecked = String(nextChecked);
    setMessage(message, "Bilgilendirme durumu güncellendi.", "success");
  } catch (error) {
    checkbox.checked = previousChecked;
    setMessage(
      message,
      `Bilgilendirme durumu güncellenemedi: ${error.message}`,
      "error",
    );
  } finally {
    checkbox.disabled = !nextOrderNo;
  }
}

function renderShiftManagerResults(container, payload) {
  if (!container) {
    return;
  }

  const rows = shiftManagerRows(payload);
  const fragment = document.createDocumentFragment();
  fragment.appendChild(renderShiftManagerSummary(payload, rows));

  if (!rows.length) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "Yaklaşan iş yok.";
    fragment.appendChild(empty);
    container.replaceChildren(fragment);
    return;
  }

  fragment.appendChild(renderShiftManagerTable(rows));
  container.replaceChildren(fragment);
}

function renderShiftManagerSummary(payload, rows) {
  const summary = document.createElement("div");
  summary.className = "ifs-summary shift-manager-summary";

  const planningFileName = planningSourceName(payload);
  const items = [
    [
      "Aktif makine",
      summaryValue(payload, ["active_machine_count", "activeMachineCount"])
        ?? uniqueRowValueCount(rows, MACHINE_KEYS),
    ],
    [
      "Yakın tamamlanan",
      summaryValue(payload, [
        "near_complete_count",
        "nearCompleteCount",
        "near_complete_machine_count",
        "nearCompleteMachineCount",
      ]) ?? rows.length,
    ],
    [
      "Sonraki iş bulundu",
      summaryValue(payload, [
        "next_job_found_count",
        "nextJobFoundCount",
        "next_order_found_count",
        "nextOrderFoundCount",
      ]) ?? rows.filter((row) => rowValue(row, NEXT_ORDER_KEYS)).length,
    ],
    ["Plan dosyası", planningFileName],
  ];

  for (const [label, value] of items) {
    const item = document.createElement("div");
    item.className = "ifs-summary-item";

    const itemLabel = document.createElement("span");
    itemLabel.textContent = label;

    const itemValue = document.createElement("strong");
    itemValue.textContent = displayValue(value);
    if (label === "Plan dosyası") {
      itemValue.title = planningSourcePath(payload) || String(value || "");
    }

    item.append(itemLabel, itemValue);
    summary.appendChild(item);
  }

  return summary;
}

function renderShiftManagerTable(rows) {
  const tableWrap = document.createElement("div");
  tableWrap.className = "table-scroll";

  const table = document.createElement("table");
  table.className = "data-table shift-manager-table";

  const thead = document.createElement("thead");
  const headerRow = document.createElement("tr");
  for (const label of [
    "Makine",
    "Mevcut iş emri",
    "Kalan paket/palet",
    "Mevcut ürün",
    "Sonraki iş emri",
    "Sonraki ürün",
    "Plan satırı",
    "Durum",
    "Bilgilendirildi",
  ]) {
    const th = document.createElement("th");
    th.scope = "col";
    th.textContent = label;
    headerRow.appendChild(th);
  }
  thead.appendChild(headerRow);

  const tbody = document.createElement("tbody");
  for (const row of rows) {
    const nextOrderNo = rowValue(row, NEXT_ORDER_KEYS);
    const tr = document.createElement("tr");
    appendTableCell(tr, rowValue(row, MACHINE_KEYS), "mono-cell");
    appendTableCell(tr, rowValue(row, CURRENT_ORDER_KEYS), "mono-cell");
    appendTableCell(tr, remainingPackagePalletText(row));
    appendTableCell(tr, productText(row, "current"));
    appendTableCell(tr, nextOrderNo, "mono-cell");
    appendTableCell(tr, productText(row, "next"));
    appendTableCell(tr, rowValue(row, PLAN_LINE_KEYS), "mono-cell");
    appendStatusCell(tr, row, nextOrderNo);
    appendNotificationCell(tr, row, nextOrderNo);
    tbody.appendChild(tr);
  }

  table.append(thead, tbody);
  tableWrap.appendChild(table);
  return tableWrap;
}

function appendStatusCell(tableRow, row, nextOrderNo) {
  const cell = document.createElement("td");
  const pill = document.createElement("span");
  updateStatusPill(pill, statusText(row, nextOrderNo), statusKind(row, nextOrderNo));
  cell.appendChild(pill);
  tableRow.appendChild(cell);
}

function appendNotificationCell(tableRow, row, nextOrderNo) {
  const cell = document.createElement("td");
  cell.className = "shift-manager-notification-cell";

  const checkbox = document.createElement("input");
  checkbox.type = "checkbox";
  checkbox.checked = booleanValue(rowValue(row, NOTIFIED_KEYS));
  checkbox.disabled = !nextOrderNo;
  checkbox.dataset.previousChecked = String(checkbox.checked);
  checkbox.dataset.nextOrderNo = nextOrderNo ? String(nextOrderNo) : "";
  checkbox.dataset.shiftManagerNotified = "true";
  checkbox.setAttribute(
    "aria-label",
    `${displayValue(rowValue(row, MACHINE_KEYS))} bilgilendirildi`,
  );

  notificationRows.set(checkbox, row);
  cell.appendChild(checkbox);
  tableRow.appendChild(cell);
}

function appendTableCell(tableRow, value, className = "") {
  const cell = document.createElement("td");
  if (className) {
    cell.className = className;
  }
  cell.textContent = displayValue(value);
  tableRow.appendChild(cell);
}

function shiftManagerRows(payload) {
  if (Array.isArray(payload)) {
    return payload;
  }

  for (const key of ROW_KEYS) {
    if (Array.isArray(payload?.[key])) {
      return payload[key];
    }
  }
  return [];
}

function shiftManagerNotificationBody(row, informed) {
  const body = {
    informed,
  };

  addBodyValue(body, "machine_code", rowValue(row, MACHINE_KEYS));
  addBodyValue(body, "current_order_no", rowValue(row, CURRENT_ORDER_KEYS));
  addBodyValue(body, "next_order_no", rowValue(row, NEXT_ORDER_KEYS));

  return body;
}

function addBodyValue(body, key, value) {
  if (value !== null) {
    body[key] = value;
  }
}

function summaryValue(payload, keys) {
  const summary = payload?.summary && typeof payload.summary === "object"
    ? payload.summary
    : null;
  for (const source of [payload, summary]) {
    const value = rowValue(source, keys);
    if (value !== null) {
      return value;
    }
  }
  return null;
}

function rowValue(row, keys) {
  if (!row || typeof row !== "object") {
    return null;
  }

  for (const key of keys) {
    const value = nestedValue(row, key);
    if (value !== null && value !== undefined && value !== "") {
      return value;
    }
  }
  return null;
}

function nestedValue(source, key) {
  if (!String(key).includes(".")) {
    return source?.[key];
  }

  return String(key)
    .split(".")
    .reduce((value, part) => {
      if (value === null || value === undefined || typeof value !== "object") {
        return undefined;
      }
      return value[part];
    }, source);
}

function uniqueRowValueCount(rows, keys) {
  return new Set(
    rows
      .map((row) => rowValue(row, keys))
      .filter((value) => value !== null && value !== undefined && value !== ""),
  ).size;
}

function remainingPackagePalletText(row) {
  const explicit = rowValue(row, [
    "remaining_package_pallet",
    "remainingPackagePallet",
    "remaining_package_pallet_text",
    "remainingPackagePalletText",
    "remaining_text",
    "remainingText",
    "remaining",
  ]);
  if (explicit !== null) {
    return explicit;
  }

  const packageCount = rowValue(row, [
    "remaining_package_count",
    "remainingPackageCount",
    "remaining_packages",
    "remainingPackages",
    "remaining_pack_count",
    "remainingPackCount",
  ]);
  const palletCount = rowValue(row, [
    "remaining_pallet_count",
    "remainingPalletCount",
    "remaining_pallets",
    "remainingPallets",
    "remaining_palet_count",
    "remainingPaletCount",
  ]);

  if (packageCount !== null || palletCount !== null) {
    if (packageCount !== null && palletCount !== null) {
      return `${displayValue(packageCount)} / ${displayValue(palletCount)}`;
    }
    return displayValue(packageCount ?? palletCount);
  }
  return null;
}

function productText(row, prefix) {
  const explicit = rowValue(row, [
    `${prefix}_product`,
    `${prefix}Product`,
    `${prefix}_product_name`,
    `${prefix}ProductName`,
    `${prefix}_part`,
    `${prefix}Part`,
  ]);
  if (explicit !== null) {
    return explicit;
  }

  const partNo = rowValue(row, [
    `${prefix}_part_no`,
    `${prefix}PartNo`,
    `${prefix}_product_no`,
    `${prefix}ProductNo`,
  ]);
  const description = rowValue(row, [
    `${prefix}_part_description`,
    `${prefix}PartDescription`,
    `${prefix}_product_description`,
    `${prefix}ProductDescription`,
    `${prefix}_description`,
    `${prefix}Description`,
  ]);

  if (partNo !== null && description !== null) {
    return `${partNo} - ${description}`;
  }
  return partNo ?? description;
}

function statusText(row, nextOrderNo) {
  const explicitStatus = rowValue(row, STATUS_KEYS);
  if (explicitStatus !== null) {
    return statusLabel(explicitStatus);
  }
  return nextOrderNo ? "Yeni iş emri var" : "Yeni iş emri yok";
}

function statusLabel(value) {
  const text = String(value);
  const labels = {
    next_found: "Yeni iş emri var",
    machine_not_in_plan: "Makine planda bulunamadı",
    current_order_not_in_plan: "Mevcut iş emri planda bulunamadı",
    no_next_job: "Yeni iş emri yok",
    invalid_remaining_qty: "Kalan miktar hesaplanamadı",
  };
  return labels[text.trim().toLowerCase()] ?? text;
}

function statusKind(row, nextOrderNo) {
  const value = String(rowValue(row, STATUS_KIND_KEYS) || "").trim().toLowerCase();
  if (["success", "ok", "ready", "found", "complete"].includes(value)) {
    return "success";
  }
  if (["error", "failed", "fail"].includes(value)) {
    return "error";
  }
  if (["warning", "missing", "not_found", "no_next_order"].includes(value)) {
    return "warning";
  }
  return nextOrderNo ? "success" : "warning";
}

function planningSourceName(payload) {
  const explicit = summaryValue(payload, [
    "planning_file_name",
    "planningFileName",
    "planning_filename",
    "planningFilename",
    "planning_source_name",
    "planningSourceName",
  ]);
  if (explicit !== null) {
    return explicit;
  }

  const sourcePath = planningSourcePath(payload);
  return sourcePath ? String(sourcePath).split(/[\\/]/).pop() : null;
}

function planningSourcePath(payload) {
  return summaryValue(payload, [
    "planning_file_path",
    "planningFilePath",
    "planning_source_path",
    "planningSourcePath",
  ]);
}

function booleanValue(value) {
  if (typeof value === "boolean") {
    return value;
  }
  if (typeof value === "number") {
    return value > 0;
  }
  if (typeof value === "string") {
    const normalized = value.trim().toLowerCase();
    return ["1", "true", "yes", "evet", "ok", "sent", "gonderildi"].includes(
      normalized,
    );
  }
  return false;
}
