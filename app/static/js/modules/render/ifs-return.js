import { renderEmptyState } from "./shared.js?v=20260615-render";
import { displayValue, formatTimestamp } from "../utils.js?v=20260612-refactor";

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
    empty.textContent = "\u0130ade aday\u0131 yok.";
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
    renderEmptyState(container, "\u0130ade aday\u0131 yok.");
    return;
  }

  container.replaceChildren(renderIfsReturnCandidateTable(candidates));
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
    "Malzeme ad\u0131",
    "Lokasyon",
    "Lot",
    "Kullan\u0131labilir",
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
    ["\u00c7izelge i\u015f emri", payload?.planning_order_count],
    ["\u00c7izelge operasyon", payload?.planning_operation_count],
    ["\u00c7izelge HM-02", payload?.planning_used_hm02_part_count],
    ["Toplam malzeme", payload?.used_material_count],
    ["Toplam HM-02", payload?.used_hm02_part_count],
    ["\u0130ade aday\u0131", payload?.return_candidate_count],
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
    planningSource.textContent = `\u00c7izelge dosyas\u0131: ${
      payload.planning_source_name || payload.planning_source_path
    }`;
    if (payload?.planning_source_path) {
      planningSource.title = payload.planning_source_path;
    }
    summary.appendChild(planningSource);
  }

  return summary;
}

function appendTableCell(row, value) {
  const cell = document.createElement("td");
  cell.textContent = displayValue(value);
  row.appendChild(cell);
}
