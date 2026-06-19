import { SYNC_LABELS } from "./constants.js?v=20260619-frontend-cleanup";
import { dateForDisplay } from "./dates.js?v=20260619-frontend-cleanup";
import {
  displayValue,
  formatTimestamp,
  updateStatusPill,
} from "./utils.js?v=20260619-frontend-cleanup";

const PRODUCTION_LOSS_SHIFT_COLUMNS = [
  {
    label: "24.00-08.00",
    prefix: "shift_2400_0800",
    legacyActualKey: "shift_2400_0800_quantity",
  },
  {
    label: "08.00-16.00",
    prefix: "shift_0800_1600",
    legacyActualKey: "shift_0800_1600_quantity",
  },
  {
    label: "16.00-24.00",
    prefix: "shift_1600_2400",
    legacyActualKey: "shift_1600_2400_quantity",
  },
];

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

export function renderAmountControlShiftList(container, shifts, emptyText) {
  if (!container) {
    return;
  }

  if (!shifts.length) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = emptyText;
    container.replaceChildren(empty);
    return;
  }

  const fragment = document.createDocumentFragment();
  for (const amountShift of shifts) {
    fragment.appendChild(renderAmountControlShiftRow(amountShift));
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

export function renderMissingProductionStarts(container, payload) {
  if (!container) {
    return;
  }

  const machines = Array.isArray(payload?.machines) ? payload.machines : [];
  const fragment = document.createDocumentFragment();
  fragment.appendChild(renderMissingProductionSummary(payload));

  if (!machines.length) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "Eksik yok.";
    fragment.appendChild(empty);
    container.replaceChildren(fragment);
    return;
  }

  fragment.appendChild(renderMissingProductionTable(machines));
  container.replaceChildren(fragment);
}

export function renderProductionLossReport(container, payload) {
  if (!container) {
    return;
  }

  const rows = Array.isArray(payload?.rows) ? payload.rows : [];
  const fragment = document.createDocumentFragment();
  fragment.appendChild(renderProductionLossSummary(payload));

  if (!rows.length) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "Rapor satiri yok.";
    fragment.appendChild(empty);
    container.replaceChildren(fragment);
    return;
  }

  fragment.appendChild(renderProductionLossTable(rows));
  container.replaceChildren(fragment);
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

function renderProductionLossTable(rows) {
  const tableWrap = document.createElement("div");
  tableWrap.className = "table-scroll";

  const table = document.createElement("table");
  table.className = "data-table production-loss-table";

  const thead = document.createElement("thead");
  const headerRow = document.createElement("tr");
  const headers = [
    "Tarih",
    "Makine",
    "Is emri",
    "Urun",
    "Gr",
    ...PRODUCTION_LOSS_SHIFT_COLUMNS.map(
      (shift) => `${shift.label} (Gercek / Optimum / Kayip)`,
    ),
    "Toplam",
    "Aktif goz",
    "Cycle",
    "Net dk",
    "Brut dk",
    "Net kayip",
    "Brut kayip",
    "Mola/durus kaybi",
    "Uyari",
  ];
  for (const label of headers) {
    const th = document.createElement("th");
    th.scope = "col";
    th.textContent = label;
    headerRow.appendChild(th);
  }
  thead.appendChild(headerRow);

  const tbody = document.createElement("tbody");
  for (const row of rows) {
    const tr = document.createElement("tr");
    appendTableCell(tr, row.record_date);
    appendTableCell(tr, `${displayValue(row.machine_name)} / ${displayValue(row.machine_code)}`);
    appendTableCell(tr, row.job_order, "mono-cell");
    appendTableCell(tr, row.product_description);
    appendTableCell(tr, row.gram);
    for (const shift of PRODUCTION_LOSS_SHIFT_COLUMNS) {
      appendShiftLossCell(tr, row, shift);
    }
    appendTableCell(tr, row.daily_total_quantity);
    appendTableCell(tr, row.active_cavities);
    appendTableCell(tr, row.cycle_time_seconds);
    appendTableCell(tr, row.net_machine_minutes);
    appendTableCell(tr, row.gross_elapsed_minutes);
    appendTableCell(tr, row.production_loss_net);
    appendTableCell(tr, row.production_loss_gross);
    appendTableCell(tr, row.break_loss_quantity);
    appendTableCell(tr, row.warnings);
    tbody.appendChild(tr);
  }

  table.append(thead, tbody);
  tableWrap.appendChild(table);
  return tableWrap;
}

function renderProductionLossSummary(payload) {
  const summary = document.createElement("div");
  summary.className = "ifs-summary";

  const items = [
    ["Baslangic", payload?.date_from],
    ["Bitis", payload?.date_to],
    ["Satir", payload?.row_count],
    ["Uyari", payload?.warning_count],
    [
      "Etiket",
      payload?.source_summary?.labels_refreshed ? "Yenilendi" : "Cache",
    ],
    ["Etiket kayit", payload?.source_summary?.label_event_count],
    ["Etiket miktar", payload?.source_summary?.label_quantity_total],
    ["IFS", payload?.source_summary?.ifs_refreshed ? "Yenilendi" : "Cache"],
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

  if (payload?.output_path) {
    const outputPath = document.createElement("p");
    outputPath.className = "entry-meta ifs-generated-at";
    outputPath.textContent = `Excel: ${payload.output_path}`;
    summary.appendChild(outputPath);
  }

  if (payload?.source_summary?.ifs_error) {
    const ifsError = document.createElement("p");
    ifsError.className = "entry-meta error ifs-generated-at";
    ifsError.textContent = `IFS: ${payload.source_summary.ifs_error}`;
    summary.appendChild(ifsError);
  }

  if (payload?.source_summary?.label_ifs_error) {
    const labelError = document.createElement("p");
    labelError.className = "entry-meta error ifs-generated-at";
    labelError.textContent = `Etiket/arsiv: ${payload.source_summary.label_ifs_error}`;
    summary.appendChild(labelError);
  }

  return summary;
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

function renderMissingProductionTable(machines) {
  const tableWrap = document.createElement("div");
  tableWrap.className = "table-scroll";

  const table = document.createElement("table");
  table.className = "data-table";

  const thead = document.createElement("thead");
  const headerRow = document.createElement("tr");
  for (const label of [
    "Salon",
    "Makine",
    "İş emri",
    "Ürün",
    "Çevrim",
    "Son kayıt",
    "Kayıt",
  ]) {
    const th = document.createElement("th");
    th.scope = "col";
    th.textContent = label;
    headerRow.appendChild(th);
  }
  thead.appendChild(headerRow);

  const tbody = document.createElement("tbody");
  for (const row of machines) {
    const tr = document.createElement("tr");
    appendTableCell(tr, row.hall_number ? `Salon ${row.hall_number}` : row.hall_name);
    appendTableCell(tr, row.machine_code, "mono-cell");
    appendTableCell(tr, row.latest_work_order, "mono-cell");
    appendTableCell(tr, row.latest_product);
    appendTableCell(tr, row.latest_cycle_time);
    appendTableCell(tr, formatTimestamp(row.latest_submitted_at));
    appendTableCell(tr, row.entry_count);
    tbody.appendChild(tr);
  }

  table.append(thead, tbody);
  tableWrap.appendChild(table);
  return tableWrap;
}

function renderMissingProductionSummary(payload) {
  const summary = document.createElement("div");
  summary.className = "ifs-summary";

  const items = [
    ["Tarih", payload?.process_date],
    ["Çevrim girilen", payload?.working_machine_count],
    ["IFS aktif makine", payload?.active_ifs_machine_count],
    ["Başlatma eksiği", payload?.missing_count],
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

  return summary;
}

function renderIfsSummary(payload) {
  const summary = document.createElement("div");
  summary.className = "ifs-summary";

  const items = [
    ["U1 stok", payload?.stock_count],
    ["Aktif operasyon", payload?.operation_count],
    [
      "Aktif HM-02/03/04",
      payload?.active_used_part_count ?? payload?.active_used_hm02_part_count,
    ],
    ["Çizelge iş emri", payload?.planning_order_count],
    ["Çizelge operasyon", payload?.planning_operation_count],
    [
      "Çizelge HM-02/03/04",
      payload?.planning_used_part_count ?? payload?.planning_used_hm02_part_count,
    ],
    ["Toplam malzeme", payload?.used_material_count],
    [
      "Toplam HM-02/03/04",
      payload?.used_part_count ?? payload?.used_hm02_part_count,
    ],
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

function appendShiftLossCell(rowElement, reportRow, shift) {
  const cell = document.createElement("td");
  cell.className = "production-loss-shift-cell";

  const metrics = [
    [
      "Gercek",
      shiftMetricValue(reportRow, shift, "actual_quantity", shift.legacyActualKey),
    ],
    ["Optimum", shiftMetricValue(reportRow, shift, "optimum_quantity")],
    ["Kayip", shiftMetricValue(reportRow, shift, "loss_quantity")],
  ];

  for (const [label, value] of metrics) {
    const metric = document.createElement("span");
    metric.className = "production-loss-shift-metric";

    const metricLabel = document.createElement("span");
    metricLabel.textContent = label;

    const metricValue = document.createElement("strong");
    metricValue.textContent = displayValue(value);

    metric.append(metricLabel, metricValue);
    cell.appendChild(metric);
  }

  rowElement.appendChild(cell);
}

function shiftMetricValue(reportRow, shift, metricKey, fallbackKey) {
  const nestedShift = findNestedShiftResult(reportRow, shift);
  return firstDisplayValue(
    nestedShift?.[metricKey],
    nestedShift?.[metricKey.replace("_quantity", "")],
    reportRow?.[`${shift.prefix}_${metricKey}`],
    fallbackKey ? reportRow?.[fallbackKey] : undefined,
  );
}

function findNestedShiftResult(reportRow, shift) {
  const shiftResults = Array.isArray(reportRow?.shift_results)
    ? reportRow.shift_results
    : Array.isArray(reportRow?.shifts)
    ? reportRow.shifts
    : [];

  return shiftResults.find((item) => {
    const label = item?.shift || item?.label || item?.name;
    return label === shift.label || item?.prefix === shift.prefix;
  });
}

function firstDisplayValue(...values) {
  for (const value of values) {
    if (value !== null && value !== undefined && value !== "") {
      return value;
    }
  }
  return null;
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
  updateSyncStatusPill(status, entry.sync_status);
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
  updateSyncStatusPill(status, submission.sync_status);
  if (submission.excel_start_row && submission.excel_end_row) {
    status.title = `Excel satırları ${submission.excel_start_row}-${submission.excel_end_row}`;
  }

  row.append(details, status);
  return row;
}

function renderAmountControlShiftRow(amountShift) {
  const row = document.createElement("article");
  row.className = "entry-row";

  const details = document.createElement("div");
  const title = document.createElement("p");
  title.className = "entry-title";
  title.textContent = amountControlShiftTitle(amountShift);

  const meta = document.createElement("p");
  meta.className = "entry-meta";
  meta.textContent = amountControlShiftMeta(amountShift);

  details.append(title, meta);

  const status = document.createElement("span");
  updateStatusPill(status, `${displayValue(amountShift.produced_quantity)} adet`, "success");

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

function amountControlShiftTitle(amountShift) {
  return [
    dateForDisplay(amountShift.record_date),
    amountShift.machine_code,
    amountShift.job_order,
    amountShift.shift,
  ].filter(Boolean).join(" / ");
}

function amountControlShiftMeta(amountShift) {
  const breakdownCount = Array.isArray(amountShift.breakdowns)
    ? amountShift.breakdowns.length
    : 0;
  const pieces = [
    amountShift.worker_names ? `Calisanlar: ${amountShift.worker_names}` : "",
    breakdownCount ? `${breakdownCount} ariza` : "",
    formatTimestamp(amountShift.created_at),
  ].filter(Boolean);
  return pieces.join(" / ");
}

function updateSyncStatusPill(element, syncStatus) {
  updateStatusPill(
    element,
    SYNC_LABELS[syncStatus] || syncStatus || "Bilinmiyor",
    syncStatusKind(syncStatus),
  );
}

function syncStatusKind(syncStatus) {
  if (syncStatus === "synced") {
    return "success";
  }
  if (syncStatus === "failed_excel") {
    return "error";
  }
  return "warning";
}
