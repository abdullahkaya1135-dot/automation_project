import { apiJson } from "../../api.js?v=20260612-refactor";
import {
  OFFLINE_PENDING_STATUSES,
  OFFLINE_STATUS_SERVER_SAVED,
} from "./constants.js?v=20260616-offline-split";
import { updateStatusPill } from "../utils.js?v=20260612-refactor";
import { getAllOfflineRecords } from "./outbox-db.js?v=20260616-offline-split";

export async function updatePhoneSyncStatus() {
  const pendingStatus = document.querySelector("#phone-pending-count");
  const serverStatus = document.querySelector("#phone-server-saved-count");
  try {
    const records = await getAllOfflineRecords();
    const pendingCount = records.filter((record) => OFFLINE_PENDING_STATUSES.has(record.status)).length;
    const serverSavedCount = records.filter((record) => record.status === OFFLINE_STATUS_SERVER_SAVED).length;
    updateStatusPill(
      pendingStatus,
      `Telefon bekleyen: ${pendingCount}`,
      pendingCount ? "warning" : "success",
    );
    updateStatusPill(serverStatus, `Sunucuya kaydedilen: ${serverSavedCount}`, "success");
  } catch (error) {
    updateStatusPill(pendingStatus, "Telefon veritaban\u0131 yok", "error");
    updateStatusPill(serverStatus, error.message, "error");
  }
}

export async function loadExcelPendingCount() {
  const excelStatus = document.querySelector("#excel-pending-count");
  if (!excelStatus) {
    return;
  }
  try {
    const [
      pendingEntries,
      failedEntries,
      pendingAuxiliary,
      failedAuxiliary,
    ] = await Promise.all([
      apiJson("/api/entries?sync_status=pending_excel&limit=200"),
      apiJson("/api/entries?sync_status=failed_excel&limit=200"),
      apiJson("/api/auxiliary-systems/submissions?sync_status=pending_excel&limit=200"),
      apiJson("/api/auxiliary-systems/submissions?sync_status=failed_excel&limit=200"),
    ]);
    const count = [
      ...(pendingEntries.entries || []),
      ...(failedEntries.entries || []),
      ...(pendingAuxiliary.submissions || []),
      ...(failedAuxiliary.submissions || []),
    ].length;
    updateStatusPill(excelStatus, `Excel bekleyen: ${count}`, count ? "warning" : "success");
  } catch (_error) {
    updateStatusPill(excelStatus, "Excel bekleyen: offline", "warning");
  }
}
