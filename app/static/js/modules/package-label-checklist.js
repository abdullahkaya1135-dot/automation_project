import { apiJson } from "../api.js?v=20260629-label-material-availability-v1";
import {
  renderListError,
  renderLoading,
  renderPackageLabelChecklist,
  renderPackageLabelChecklistPrintArea,
} from "./render.js?v=20260629-label-material-availability-v1";
import { setButtonBusy, setMessage } from "./utils.js?v=20260629-label-material-availability-v1";

let latestPackageLabelChecklistPayload = null;

export async function handlePackageLabelChecklist(event) {
  const button = event.currentTarget;
  const message = document.querySelector("#package-label-checklist-message");
  const container = document.querySelector("#package-label-checklist-results");

  setMessage(message, "Package Label Checklist kontrolu calisiyor...", "");
  renderLoading(container, "IFS paket etiketleri okunuyor...");
  setPackageLabelChecklistPrintPayload(null);
  setButtonBusy(button, true, "Kontrol ediliyor");

  try {
    const payload = await apiJson("/api/ifs/package-label-checklist");
    const rows = packageLabelChecklistRows(payload);
    const rowCount = packageLabelChecklistCount(payload, rows);
    const issueCount = packageLabelChecklistIssueCount(payload, rows);

    renderPackageLabelChecklist(container, payload);
    setPackageLabelChecklistPrintPayload(payload);

    if (rowCount > 0) {
      const issueText = issueCount ? ` ${issueCount} satir kontrol gerektiriyor.` : "";
      setMessage(
        message,
        `${rowCount} checklist satiri hazir.${issueText}`,
        issueCount ? "warning" : "success",
      );
    } else {
      setMessage(message, "Checklist satiri bulunmadi.", "warning");
    }
  } catch (error) {
    setMessage(
      message,
      `Package Label Checklist kontrolu basarisiz: ${error.message}`,
      "error",
    );
    renderListError(
      container,
      `Package Label Checklist kontrolu basarisiz: ${error.message}`,
    );
    setPackageLabelChecklistPrintPayload(null);
  } finally {
    setButtonBusy(button, false);
  }
}

export function handlePrintPackageLabelChecklist() {
  if (!latestPackageLabelChecklistPayload) {
    return;
  }

  renderPackageLabelChecklistPrintArea(latestPackageLabelChecklistPayload);
  window.print();
}

export function setPackageLabelChecklistPrintPayload(payload) {
  latestPackageLabelChecklistPayload = payload;
  renderPackageLabelChecklistPrintArea(payload);

  const printButton = document.querySelector("#print-package-label-checklist");
  if (printButton) {
    printButton.disabled = !payload;
  }
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

function packageLabelChecklistCount(payload, rows) {
  const summary = payload?.summary || {};
  const count = payload?.checklist_count
    ?? payload?.row_count
    ?? payload?.package_label_count
    ?? payload?.label_count
    ?? summary.row_count
    ?? summary.stock_count;
  return Number(count ?? rows.length) || 0;
}

function packageLabelChecklistMissingCount(payload, rows) {
  const summary = payload?.summary || {};
  const count = payload?.missing_label_count
    ?? payload?.missing_count
    ?? payload?.label_missing_count
    ?? summary.missing_label_count
    ?? summary.missing_count;
  if (count !== null && count !== undefined && count !== "") {
    return Number(count) || 0;
  }
  return rows.filter((row) => labelIsMissing(row)).length;
}

function packageLabelChecklistIssueCount(payload, rows) {
  const summary = payload?.summary || {};
  const count = Number(summary.ambiguous_count || 0)
    + Number(summary.not_found_count || 0)
    + Number(summary.missing_job_order_count || 0)
    + Number(summary.operation_lookup_failed_count || 0);
  if (count > 0) {
    return count;
  }
  return packageLabelChecklistMissingCount(payload, rows);
}

function labelIsMissing(row) {
  const status = row?.label_ok
    ?? row?.labelOk
    ?? row?.has_label
    ?? row?.label_found
    ?? row?.label_printed
    ?? row?.label_status;
  if (status === false) {
    return true;
  }
  if (typeof status === "string") {
    const normalized = status.trim().toLowerCase();
    return ["missing", "eksik", "no", "false", "0"].includes(normalized);
  }
  return Boolean(row?.missing_reason || row?.label_missing_reason);
}
