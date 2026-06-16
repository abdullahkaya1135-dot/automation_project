import { renderEmptyState } from "./shared.js?v=20260615-render";
import { renderSyncStatusPill } from "./status.js?v=20260615-render";
import { formatTimestamp } from "../utils.js?v=20260612-refactor";

export function renderEntryList(container, entries, emptyText) {
  if (!container) {
    return;
  }

  if (!entries.length) {
    renderEmptyState(container, emptyText);
    return;
  }

  const fragment = document.createDocumentFragment();
  for (const entry of entries) {
    fragment.appendChild(renderEntryRow(entry));
  }
  container.replaceChildren(fragment);
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

  const statusTitle = entry.excel_row_number
    ? `Excel sat\u0131r\u0131 ${entry.excel_row_number}`
    : "";
  row.append(details, renderSyncStatusPill(entry.sync_status, statusTitle));
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
    payload.col_j ? `Toplam g\u00f6z ${payload.col_j}` : "",
    payload.col_k ? `\u00c7al\u0131\u015fan g\u00f6z ${payload.col_k}` : "",
    entry.excel_row_number ? `Excel sat\u0131r\u0131 ${entry.excel_row_number}` : "",
    formatTimestamp(entry.submitted_at || entry.created_at),
  ].filter(Boolean);
  return pieces.join(" / ");
}
