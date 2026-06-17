import { apiJson } from "../api.js?v=20260612-refactor";
import {
  renderAmountControlShiftList,
  renderAuxiliarySubmissionList,
  renderEntryList,
  renderListError,
} from "./render.js?v=20260617-amount-control";
import { entryTime } from "./utils.js?v=20260612-refactor";

export async function loadEntryLists() {
  await Promise.all([loadRecentEntries(), loadPendingEntries()]);
}

export async function loadRecentEntries() {
  const container = document.querySelector("#recent-entries");
  try {
    const payload = await apiJson("/api/entries?limit=10");
    renderEntryList(
      container,
      Array.isArray(payload.entries) ? payload.entries : [],
      "Son kayıt yok.",
    );
  } catch (error) {
    renderListError(container, `Son kayıtlar yüklenemedi: ${error.message}`);
  }
}

export async function loadPendingEntries() {
  const container = document.querySelector("#pending-entries");
  try {
    const [pendingPayload, failedPayload] = await Promise.all([
      apiJson("/api/entries?sync_status=pending_excel&limit=50"),
      apiJson("/api/entries?sync_status=failed_excel&limit=50"),
    ]);
    const entries = [
      ...(Array.isArray(pendingPayload.entries) ? pendingPayload.entries : []),
      ...(Array.isArray(failedPayload.entries) ? failedPayload.entries : []),
    ]
      .sort((left, right) => entryTime(right) - entryTime(left))
      .slice(0, 50);

    renderEntryList(container, entries, "Bekleyen kayıt yok.");
  } catch (error) {
    renderListError(container, `Bekleyen kayıtlar yüklenemedi: ${error.message}`);
  }
}

export async function loadAuxiliarySubmissions() {
  const container = document.querySelector("#auxiliary-submissions");
  try {
    const payload = await apiJson("/api/auxiliary-systems/submissions?limit=20");
    renderAuxiliarySubmissionList(
      container,
      Array.isArray(payload.submissions) ? payload.submissions : [],
      "Son gönderim yok.",
    );
  } catch (error) {
    renderListError(
      container,
      `Yardımcı sistemler gönderimleri yüklenemedi: ${error.message}`,
    );
  }
}

export async function loadAmountControlShifts() {
  const container = document.querySelector("#amount-control-submissions");
  try {
    const payload = await apiJson("/api/amount-control/shifts?limit=20");
    renderAmountControlShiftList(
      container,
      Array.isArray(payload.shifts) ? payload.shifts : [],
      "Son miktar kontrolu yok.",
    );
  } catch (error) {
    renderListError(
      container,
      `Miktar kontrolleri yuklenemedi: ${error.message}`,
    );
  }
}
