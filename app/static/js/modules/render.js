import { SYNC_LABELS } from "./constants.js?v=20260626-breakdown-context-v2";
import { dateForDisplay } from "./dates.js?v=20260626-breakdown-context-v2";
import {
  displayValue,
  formatTimestamp,
  updateStatusPill,
} from "./utils.js?v=20260626-breakdown-context-v2";

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

const PACKAGE_LABEL_CHECKLIST_ROW_SOURCES = [
  {
    label: "Machine",
    keys: [
      "machine",
      "machine_code",
      "machineCode",
      "resource_id",
      "resourceId",
      "ResourceId",
      "preferred_resource_id",
      "preferredResourceId",
      "PreferredResourceId",
    ],
    className: "mono-cell package-label-checklist-machine-cell",
    colClassName: "package-label-checklist-machine-col",
    value: packageLabelChecklistMachineText,
  },
  {
    label: "JobOrder",
    keys: ["job_order", "job_order_no", "order_no", "shop_order_no", "source_ref1"],
    className: "mono-cell package-label-checklist-job-order-cell",
    colClassName: "package-label-checklist-job-order-col",
  },
  {
    label: "PartNo",
    keys: ["part_no", "partNo", "material_part_no", "materialPartNo"],
    className:
      "mono-cell package-label-checklist-single-line-cell package-label-checklist-part-no-cell",
    colClassName: "package-label-checklist-part-no-col",
  },
  {
    label: "Description",
    keys: [
      "description",
      "part_description",
      "material_name",
      "material_description",
      "part_desc",
    ],
    className:
      "package-label-checklist-single-line-cell package-label-checklist-description-cell",
    colClassName: "package-label-checklist-description-col",
  },
  {
    label: "HandlingUnitId",
    keys: [
      "handling_unit",
      "handling_unit_id",
      "handling_unit_no",
      "handlingUnit",
      "handlingUnitId",
      "handlingUnitNo",
      "sscc",
      "package_id",
    ],
    className: "mono-cell package-label-checklist-handling-unit-cell",
    colClassName: "package-label-checklist-handling-unit-col",
    value: packageLabelChecklistHandlingUnitText,
  },
  {
    label: "ReceiptDate",
    keys: ["receipt_date", "receiptDate", "ReceiptDate"],
    className:
      "mono-cell package-label-checklist-single-line-cell package-label-checklist-receipt-date-cell",
    colClassName: "package-label-checklist-receipt-date-col",
    value: packageLabelChecklistReceiptDateText,
  },
  {
    label: "Label OK",
    keys: [
      "label_ok",
      "labelOk",
      "has_label",
      "label_found",
      "label_printed",
      "label_status",
    ],
    className: "package-label-checklist-writing-cell",
    colClassName: "package-label-checklist-label-ok-col",
    value: packageLabelChecklistStatusText,
  },
  {
    label: "Reason",
    keys: ["missing_reason", "missingReason", "label_missing_reason", "reason"],
    className: "package-label-checklist-writing-cell",
    colClassName: "package-label-checklist-reason-col",
  },
];
const PACKAGE_LABEL_CHECKLIST_GROUP_COLUMN_COUNT = 4;

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

export function renderBreakdownList(container, breakdowns, emptyText) {
  if (!container) {
    return;
  }

  if (!breakdowns.length) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = emptyText;
    container.replaceChildren(empty);
    return;
  }

  const fragment = document.createDocumentFragment();
  for (const breakdown of breakdowns) {
    fragment.appendChild(renderBreakdownRow(breakdown));
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
    empty.textContent = "Ä°ade adayÄ± yok.";
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
    deactivatePrintArea(container);
    container.replaceChildren();
    return;
  }

  const candidates = Array.isArray(payload.return_candidates)
    ? payload.return_candidates
    : [];
  if (!candidates.length) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "Ä°ade adayÄ± yok.";
    container.replaceChildren(empty);
    activatePrintArea(container);
    return;
  }

  container.replaceChildren(renderIfsReturnCandidateTable(candidates));
  activatePrintArea(container);
}

export function renderPackageLabelChecklist(container, payload) {
  if (!container) {
    return;
  }

  const rows = packageLabelChecklistRows(payload);
  const fragment = document.createDocumentFragment();
  fragment.appendChild(renderPackageLabelChecklistSummary(payload, rows));

  if (!rows.length) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "Checklist satiri yok.";
    fragment.appendChild(empty);
    container.replaceChildren(fragment);
    return;
  }

  fragment.appendChild(renderPackageLabelChecklistTable(rows));
  container.replaceChildren(fragment);
}

export function renderPackageLabelChecklistPrintArea(payload) {
  const container = document.querySelector("#package-label-checklist-print-area");
  if (!container) {
    return;
  }

  if (!payload) {
    deactivatePrintArea(container);
    container.replaceChildren();
    return;
  }

  const rows = packageLabelChecklistRows(payload);
  const fragment = document.createDocumentFragment();

  if (!rows.length) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "Checklist satiri yok.";
    fragment.appendChild(empty);
  } else {
    fragment.appendChild(renderPackageLabelChecklistTable(rows));
  }

  container.replaceChildren(fragment);
  activatePrintArea(container);
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
    "Lot/Parti",
    "Urun",
    "Gr",
    ...PRODUCTION_LOSS_SHIFT_COLUMNS.map(
      (shift) => `${shift.label} (Gercek / Beklenen / Kayip)`,
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
    appendTableCell(tr, row.lot_batch_no, "mono-cell");
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
    ["Cevrim atlanan", payload?.source_summary?.realized_cycle_skipped_count],
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

  if (payload?.source_summary?.realized_cycle_skip_message) {
    const cycleSkip = document.createElement("p");
    cycleSkip.className = "entry-meta warning ifs-generated-at";
    cycleSkip.textContent = payload.source_summary.realized_cycle_skip_message;
    summary.appendChild(cycleSkip);
  }

  return summary;
}

function renderPackageLabelChecklistSummary(payload, rows) {
  const summaryPayload = payload?.summary || {};
  const summary = document.createElement("div");
  summary.className = "ifs-summary package-label-checklist-summary";
  const counts = packageLabelChecklistSummaryCounts(payload, rows);

  const items = [
    ["Satir", counts.rowCount],
    ["Handling Unit", counts.handlingUnitCount],
    ["Makine", counts.matchedCount],
    ["Belirsiz", counts.ambiguousCount],
    ["Makine yok", counts.notFoundCount],
    ["Is emri yok", counts.missingJobOrderCount],
    ["Operasyon okunamadi", counts.operationLookupFailedCount],
    [
      "Son kontrol",
      summaryPayload.generated_at ? formatTimestamp(summaryPayload.generated_at) : null,
    ],
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

  if (payload?.source_name || payload?.source_path) {
    const source = document.createElement("p");
    source.className = "entry-meta ifs-generated-at";
    source.textContent = `Kaynak: ${payload.source_name || payload.source_path}`;
    if (payload?.source_path) {
      source.title = payload.source_path;
    }
    summary.appendChild(source);
  }

  const warningText = payload?.warning || summaryPayload.warning;
  if (warningText) {
    const warning = document.createElement("p");
    warning.className = "entry-meta warning ifs-generated-at";
    warning.textContent = warningText;
    summary.appendChild(warning);
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
    "Malzeme adÄ±",
    "Lokasyon",
    "Lot",
    "KullanÄ±labilir",
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

function renderPackageLabelChecklistTable(rows) {
  const tableWrap = document.createElement("div");
  tableWrap.className = "table-scroll";

  const table = document.createElement("table");
  table.className = "data-table package-label-checklist-table";

  const colgroup = document.createElement("colgroup");
  for (const column of PACKAGE_LABEL_CHECKLIST_ROW_SOURCES) {
    const col = document.createElement("col");
    col.className = column.colClassName;
    colgroup.appendChild(col);
  }

  const thead = document.createElement("thead");
  const headerRow = document.createElement("tr");
  for (const column of PACKAGE_LABEL_CHECKLIST_ROW_SOURCES) {
    const th = document.createElement("th");
    th.scope = "col";
    th.textContent = column.label;
    headerRow.appendChild(th);
  }
  thead.appendChild(headerRow);

  const tbody = document.createElement("tbody");
  for (const group of packageLabelChecklistGroups(rows)) {
    group.rows.forEach((renderedRow, rowIndex) => {
      const tr = document.createElement("tr");
      if (rowIndex === 0) {
        tr.classList.add("package-label-checklist-group-start");
      }
      renderedRow.values.forEach((value, columnIndex) => {
        const column = PACKAGE_LABEL_CHECKLIST_ROW_SOURCES[columnIndex];
        if (columnIndex < PACKAGE_LABEL_CHECKLIST_GROUP_COLUMN_COUNT) {
          if (rowIndex > 0) {
            return;
          }
          appendChecklistCell(
            tr,
            value,
            checklistCellClassName(column.className, "package-label-checklist-group-cell"),
            group.rows.length,
          );
          return;
        }
        appendChecklistCell(tr, value, column.className);
      });
      tbody.appendChild(tr);
    });
  }

  table.append(colgroup, thead, tbody);
  tableWrap.appendChild(table);
  return tableWrap;
}

function packageLabelChecklistGroups(rows) {
  const groups = [];
  const groupByKey = new Map();

  for (const row of rows) {
    const renderedRow = packageLabelChecklistRenderedRow(row);
    const key = packageLabelChecklistGroupKey(renderedRow);
    let group = groupByKey.get(key);
    if (!group) {
      group = { rows: [] };
      groupByKey.set(key, group);
      groups.push(group);
    }
    group.rows.push(renderedRow);
  }

  return groups;
}

function packageLabelChecklistRenderedRow(row) {
  return {
    values: PACKAGE_LABEL_CHECKLIST_ROW_SOURCES.map((column) =>
      packageLabelChecklistCellValue(row, column),
    ),
  };
}

function packageLabelChecklistGroupKey(renderedRow) {
  return renderedRow.values
    .slice(0, PACKAGE_LABEL_CHECKLIST_GROUP_COLUMN_COUNT)
    .map(checklistCellText)
    .join("\u0000");
}

function packageLabelChecklistRows(payload) {
  for (const key of [
    "checklist_rows",
    "rows",
    "items",
    "labels",
    "package_labels",
    "checklist",
  ]) {
    if (Array.isArray(payload?.[key])) {
      return payload[key];
    }
  }
  return [];
}

function packageLabelChecklistSummaryCounts(payload, rows) {
  const summaryPayload = payload?.summary || {};
  const rowCount = Number(
    payload?.checklist_count
      ?? payload?.row_count
      ?? summaryPayload.row_count
      ?? payload?.package_label_count
      ?? payload?.label_count
      ?? rows.length,
  ) || 0;
  const handlingUnitCount = Number(
    payload?.handling_unit_count ?? uniqueChecklistValueCount(rows, [
      "handling_unit",
      "handling_unit_id",
      "handling_unit_no",
      "handlingUnit",
      "handlingUnitId",
      "handlingUnitNo",
      "sscc",
      "package_id",
    ]),
  ) || 0;
  const labelOkCount = Number(
    payload?.label_ok_count
      ?? payload?.ok_label_count
      ?? summaryPayload.label_ok_count
      ?? rows.filter((row) => packageLabelChecklistStatus(row) === true).length,
  ) || 0;
  const missingCount = Number(
    payload?.missing_label_count
      ?? payload?.missing_count
      ?? payload?.label_missing_count
      ?? summaryPayload.missing_label_count
      ?? rows.filter((row) => packageLabelChecklistStatus(row) === false).length,
  ) || 0;
  const matchedCount = Number(summaryPayload.matched_count ?? 0) || 0;
  const ambiguousCount = Number(summaryPayload.ambiguous_count ?? 0) || 0;
  const notFoundCount = Number(summaryPayload.not_found_count ?? 0) || 0;
  const missingJobOrderCount = Number(
    summaryPayload.missing_job_order_count ?? 0,
  ) || 0;
  const operationLookupFailedCount = Number(
    summaryPayload.operation_lookup_failed_count ?? 0,
  ) || 0;

  return {
    rowCount,
    handlingUnitCount,
    labelOkCount,
    missingCount,
    matchedCount,
    ambiguousCount,
    notFoundCount,
    missingJobOrderCount,
    operationLookupFailedCount,
  };
}

function uniqueChecklistValueCount(rows, keys) {
  return new Set(
    rows
      .map((row) => checklistRowValue(row, keys))
      .filter((value) => value !== null && value !== undefined && value !== ""),
  ).size;
}

function packageLabelChecklistCellValue(row, column) {
  if (typeof column.value === "function") {
    return column.value(row, column);
  }
  const value = checklistRowValue(row, column.keys);
  if (value !== null) {
    return value;
  }
  return null;
}

function checklistRowValue(row, keys) {
  for (const key of keys) {
    const value = row?.[key];
    if (value !== null && value !== undefined && value !== "") {
      return value;
    }
  }
  return null;
}

function packageLabelChecklistStatusText(row) {
  const status = packageLabelChecklistStatus(row);
  if (status === true) {
    return "OK";
  }
  if (status === false) {
    return "Eksik";
  }
  return null;
}

function packageLabelChecklistHandlingUnitText(row, column) {
  const value = checklistRowValue(row, column.keys);
  if (value === null) {
    return null;
  }
  const text = String(value).trim();
  return /^\d{1,3}(\.\d{3})+$/.test(text) ? text.replace(/\./g, "") : text;
}

function packageLabelChecklistReceiptDateText(row, column) {
  const value = checklistRowValue(row, column.keys);
  return value === null ? null : formatTimestamp(value);
}

function packageLabelChecklistMachineText(row, column) {
  const status = String(
    row?.operation_match_status ?? row?.match_status ?? "",
  ).trim().toLowerCase();
  const machine = checklistRowValue(row, column.keys);
  if (status === "ambiguous") {
    return machine ?? "Belirsiz";
  }
  if (status === "lookup_failed") {
    return null;
  }
  return machine;
}

function packageLabelChecklistStatus(row) {
  const value = checklistRowValue(row, [
    "label_ok",
    "labelOk",
    "has_label",
    "label_found",
    "label_printed",
    "label_status",
  ]);
  if (typeof value === "boolean") {
    return value;
  }
  if (typeof value === "number") {
    return value > 0;
  }
  if (typeof value === "string") {
    const normalized = value.trim().toLowerCase();
    if (["ok", "yes", "true", "1", "var"].includes(normalized)) {
      return true;
    }
    if (["missing", "eksik", "no", "false", "0", "yok"].includes(normalized)) {
      return false;
    }
  }
  if (checklistRowValue(row, ["missing_reason", "label_missing_reason", "reason"])) {
    return false;
  }
  return null;
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
    "Ä°ÅŸ emri",
    "ÃœrÃ¼n",
    "Ã‡evrim",
    "Son kayÄ±t",
    "KayÄ±t",
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
  const processCombinationCount = payload?.process_combination_count
    ?? payload?.working_machine_count;
  const activeIfsCombinationCount = payload?.active_ifs_combination_count
    ?? payload?.active_ifs_machine_count;

  const items = [
    ["Tarih", payload?.process_date],
    ["DB eslesmesi", processCombinationCount],
    ["IFS kombinasyon", activeIfsCombinationCount],
    ["DB eksigi", payload?.missing_count],
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
    ["Ã‡izelge iÅŸ emri", payload?.planning_order_count],
    ["Ã‡izelge operasyon", payload?.planning_operation_count],
    [
      "Ã‡izelge HM-02/03/04",
      payload?.planning_used_part_count ?? payload?.planning_used_hm02_part_count,
    ],
    ["Toplam malzeme", payload?.used_material_count],
    [
      "Toplam HM-02/03/04",
      payload?.used_part_count ?? payload?.used_hm02_part_count,
    ],
    ["Ä°ade adayÄ±", payload?.return_candidate_count],
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
    planningSource.textContent = `Ã‡izelge dosyasÄ±: ${
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

function appendChecklistCell(row, value, className, rowSpan) {
  const cell = document.createElement("td");
  if (className) {
    cell.className = className;
  }
  if (rowSpan) {
    cell.rowSpan = rowSpan;
  }
  cell.textContent = checklistCellText(value);
  row.appendChild(cell);
}

function checklistCellText(value) {
  return value === null || value === undefined || value === ""
    ? ""
    : displayValue(value);
}

function checklistCellClassName(...classNames) {
  return classNames.filter(Boolean).join(" ");
}

function activatePrintArea(container) {
  for (const area of document.querySelectorAll(".print-only.print-active")) {
    if (area !== container) {
      area.classList.remove("print-active");
      area.setAttribute("aria-hidden", "true");
    }
  }
  container.classList.add("print-active");
  container.setAttribute("aria-hidden", "false");
}

function deactivatePrintArea(container) {
  container.classList.remove("print-active");
  container.setAttribute("aria-hidden", "true");
}

function appendShiftLossCell(rowElement, reportRow, shift) {
  const cell = document.createElement("td");
  cell.className = "production-loss-shift-cell";

  const metrics = [
    [
      "Gercek",
      shiftMetricValue(reportRow, shift, "actual_quantity", shift.legacyActualKey),
    ],
    ["Beklenen", shiftMetricValue(reportRow, shift, "optimum_quantity")],
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
    status.title = `Excel satÄ±rÄ± ${entry.excel_row_number}`;
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
    status.title = `Excel satÄ±rlarÄ± ${submission.excel_start_row}-${submission.excel_end_row}`;
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

function renderBreakdownRow(breakdown) {
  const row = document.createElement("article");
  row.className = "entry-row";

  const details = document.createElement("div");
  const title = document.createElement("p");
  title.className = "entry-title";
  title.textContent = breakdownTitle(breakdown);

  const meta = document.createElement("p");
  meta.className = "entry-meta";
  meta.textContent = breakdownMeta(breakdown);

  details.append(title, meta);

  const status = document.createElement("span");
  updateStatusPill(
    status,
    `${displayValue(breakdown.duration_minutes)} dk`,
    "warning",
  );

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
    payload.col_j ? `Toplam gÃ¶z ${payload.col_j}` : "",
    payload.col_k ? `Ã‡alÄ±ÅŸan gÃ¶z ${payload.col_k}` : "",
    entry.excel_row_number ? `Excel satÄ±rÄ± ${entry.excel_row_number}` : "",
    formatTimestamp(entry.submitted_at || entry.created_at),
  ].filter(Boolean);
  return pieces.join(" / ");
}

function auxiliarySubmissionTitle(submission) {
  return `YardÄ±mcÄ± sistemler / ${submission.recorded_date || "Tarih yok"}`;
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

function breakdownTitle(breakdown) {
  return [
    dateForDisplay(breakdown.record_date),
    breakdown.machine_code,
    breakdown.shift,
    breakdown.stop_reason || breakdown.reason,
  ].filter(Boolean).join(" / ");
}

function breakdownMeta(breakdown) {
  const pieces = [
    breakdown.job_order ? `Is emri: ${breakdown.job_order}` : "",
    breakdown.produced_product ? `Urun: ${breakdown.produced_product}` : "",
    breakdown.stopped_at ? `Baslangic: ${formatTimestamp(breakdown.stopped_at)}` : "",
    breakdown.resumed_at ? `Bitis: ${formatTimestamp(breakdown.resumed_at)}` : "",
    formatTimestamp(breakdown.created_at),
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
