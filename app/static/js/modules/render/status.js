const SYNC_LABELS = {
  synced: "Senkronize",
  pending_excel: "Beklemede",
  failed_excel: "Ba\u015far\u0131s\u0131z",
};

export function statusClass(syncStatus) {
  if (syncStatus === "synced") {
    return "status-success";
  }
  if (syncStatus === "failed_excel") {
    return "status-error";
  }
  return "status-warning";
}

export function renderSyncStatusPill(syncStatus, title = "") {
  const status = document.createElement("span");
  status.className = `status-pill ${statusClass(syncStatus)}`;
  status.textContent = SYNC_LABELS[syncStatus] || syncStatus || "Bilinmiyor";
  if (title) {
    status.title = title;
  }
  return status;
}
