import { SYNC_LABELS } from "./constants.js?v=20260612-refactor";
import {
  displayValue,
  entryTime,
  formatTimestamp,
} from "./utils.js?v=20260612-refactor";

export function renderEntryList(container, entries, emptyText) {
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

export function renderAuxiliarySubmissionList(container, submissions, emptyText) {
  if (!container) {
    return;
  }

  if (!submissions.length) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = emptyText;
    container.replaceChildren(empty);
    return;
  }

  const fragment = document.createDocumentFragment();
  for (const submission of submissions) {
    fragment.appendChild(renderAuxiliarySubmissionRow(submission));
  }
  container.replaceChildren(fragment);
}

export function renderIfsReturnCandidates(container, payload) {
  if (!container) {
    return;
  }

  const candidates = Array.isArray(payload?.return_candidates)
    ? payload.return_candidates
    : [];
  const fragment = document.createDocumentFragment();
  fragment.appendChild(renderIfsSummary(payload));

  if (!candidates.length) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "İade adayı yok.";
    fragment.appendChild(empty);
    container.replaceChildren(fragment);
    return;
  }

  fragment.appendChild(renderIfsReturnCandidateTable(candidates));
  container.replaceChildren(fragment);
}

export function renderIfsReturnPrintArea(payload) {
  const container = document.querySelector("#ifs-return-print-area");
  if (!container) {
    return;
  }

  if (!payload) {
    container.replaceChildren();
    return;
  }

  const candidates = Array.isArray(payload.return_candidates)
    ? payload.return_candidates
    : [];
  if (!candidates.length) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "İade adayı yok.";
    container.replaceChildren(empty);
    return;
  }

  container.replaceChildren(renderIfsReturnCandidateTable(candidates));
}

export function renderLoading(container, text) {
  if (!container) {
    return;
  }
  const loading = document.createElement("p");
  loading.className = "empty-state";
  loading.textContent = text;
  container.replaceChildren(loading);
}

export function renderListError(container, text) {
  if (!container) {
    return;
  }
  const error = document.createElement("p");
  error.className = "empty-state error";
  error.textContent = text;
  container.replaceChildren(error);
}

function renderIfsReturnCandidateTable(candidates) {
  const tableWrap = document.createElement("div");
  tableWrap.className = "table-scroll";

  const table = document.createElement("table");
  table.className = "data-table";

  const thead = document.createElement("thead");
  const headerRow = document.createElement("tr");
  for (const label of [
    "Malzeme",
    "Malzeme adı",
    "Lokasyon",
    "Lot",
    "Kullanılabilir",
    "Eldeki",
    "Birim",
  ]) {
    const th = document.createElement("th");
    th.scope = "col";
    th.textContent = label;
    headerRow.appendChild(th);
  }
  thead.appendChild(headerRow);

  const tbody = document.createElement("tbody");
  for (const row of candidates) {
    const tr = document.createElement("tr");
    appendTableCell(tr, row.part_no);
    appendTableCell(tr, row.material_name);
    appendTableCell(tr, row.location_no);
    appendTableCell(tr, row.lot_batch_no);
    appendTableCell(tr, row.available_qty);
    appendTableCell(tr, row.qty_onhand);
    appendTableCell(tr, row.uom);
    tbody.appendChild(tr);
  }

  table.append(thead, tbody);
  tableWrap.appendChild(table);
  return tableWrap;
}

function renderIfsSummary(payload) {
  const summary = document.createElement("div");
  summary.className = "ifs-summary";

  const items = [
    ["U1 stok", payload?.stock_count],
    ["Aktif operasyon", payload?.operation_count],
    ["Aktif HM-02", payload?.active_used_hm02_part_count],
    ["Çizelge iş emri", payload?.planning_order_count],
    ["Çizelge operasyon", payload?.planning_operation_count],
    ["Çizelge HM-02", payload?.planning_used_hm02_part_count],
    ["Toplam malzeme", payload?.used_material_count],
    ["Toplam HM-02", payload?.used_hm02_part_count],
    ["İade adayı", payload?.return_candidate_count],
  ];

  for (const [label, value] of items) {
    const item = document.createElement("div");
    item.className = "ifs-summary-item";

    const itemLabel = document.createElement("span");
    itemLabel.textContent = label;

    const itemValue = document.createElement("strong");
    itemValue.textContent = displayValue(value);

    item.append(itemLabel, itemValue);
    summary.appendChild(item);
  }

  if (payload?.generated_at) {
    const generatedAt = document.createElement("p");
    generatedAt.className = "entry-meta ifs-generated-at";
    generatedAt.textContent = `Son kontrol: ${formatTimestamp(payload.generated_at)}`;
    summary.appendChild(generatedAt);
  }

  if (payload?.planning_source_name || payload?.planning_source_path) {
    const planningSource = document.createElement("p");
    planningSource.className = "entry-meta ifs-planning-source";
    planningSource.textContent = `Çizelge dosyası: ${
      payload.planning_source_name || payload.planning_source_path
    }`;
    if (payload?.planning_source_path) {
      planningSource.title = payload.planning_source_path;
    }
    summary.appendChild(planningSource);
  }

  return summary;
}

function appendTableCell(row, value, className) {
  const cell = document.createElement("td");
  if (className) {
    cell.className = className;
  }
  cell.textContent = displayValue(value);
  row.appendChild(cell);
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

function renderAuxiliarySubmissionRow(submission) {
  const row = document.createElement("article");
  row.className = "entry-row";

  const details = document.createElement("div");
  const title = document.createElement("p");
  title.className = "entry-title";
  title.textContent = auxiliarySubmissionTitle(submission);

  const meta = document.createElement("p");
  meta.className = "entry-meta";
  meta.textContent = auxiliarySubmissionMeta(submission);

  details.append(title, meta);
  if (submission.last_error) {
    const error = document.createElement("p");
    error.className = "entry-meta error";
    error.textContent = submission.last_error;
    details.appendChild(error);
  }

  const status = document.createElement("span");
  status.className = `status-pill ${statusClass(submission.sync_status)}`;
  status.textContent = SYNC_LABELS[submission.sync_status] || submission.sync_status || "Bilinmiyor";
  if (submission.excel_start_row && submission.excel_end_row) {
    status.title = `Excel satırları ${submission.excel_start_row}-${submission.excel_end_row}`;
  }

  row.append(details, status);
  return row;
}

function entryTitle(entry) {
  const payload = entry.payload || {};
  const machine = payload.col_f || "Makine";
  const workOrder = payload.col_h || "";
  return workOrder ? `${machine} - ${workOrder}` : String(machine);
}

function entryMeta(entry) {
  const payload = entry.payload || {};
  const pieces = [
    payload.col_j ? `Toplam göz ${payload.col_j}` : "",
    payload.col_k ? `Çalışan göz ${payload.col_k}` : "",
    entry.excel_row_number ? `Excel satırı ${entry.excel_row_number}` : "",
    formatTimestamp(entry.submitted_at || entry.created_at),
  ].filter(Boolean);
  return pieces.join(" / ");
}

function auxiliarySubmissionTitle(submission) {
  return `Yardımcı sistemler / ${submission.recorded_date || "Tarih yok"}`;
}

function auxiliarySubmissionMeta(submission) {
  const pieces = [
    submission.excel_start_row && submission.excel_end_row
      ? `Excel ${submission.excel_start_row}-${submission.excel_end_row}`
      : "",
    formatTimestamp(submission.submitted_at || submission.created_at),
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

export { entryTime };
