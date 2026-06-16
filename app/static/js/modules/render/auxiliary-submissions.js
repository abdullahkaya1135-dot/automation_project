import { renderEmptyState } from "./shared.js?v=20260615-render";
import { renderSyncStatusPill } from "./status.js?v=20260615-render";
import { formatTimestamp } from "../utils.js?v=20260612-refactor";

export function renderAuxiliarySubmissionList(container, submissions, emptyText) {
  if (!container) {
    return;
  }

  if (!submissions.length) {
    renderEmptyState(container, emptyText);
    return;
  }

  const fragment = document.createDocumentFragment();
  for (const submission of submissions) {
    fragment.appendChild(renderAuxiliarySubmissionRow(submission));
  }
  container.replaceChildren(fragment);
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

  const statusTitle = submission.excel_start_row && submission.excel_end_row
    ? `Excel sat\u0131rlar\u0131 ${submission.excel_start_row}-${submission.excel_end_row}`
    : "";
  row.append(details, renderSyncStatusPill(submission.sync_status, statusTitle));
  return row;
}

function auxiliarySubmissionTitle(submission) {
  return `Yard\u0131mc\u0131 sistemler / ${submission.recorded_date || "Tarih yok"}`;
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
