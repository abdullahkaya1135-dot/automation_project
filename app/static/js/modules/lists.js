import { apiJson } from "../api.js?v=20260629-shift-manager-labels-v1";
import {
  renderAmountControlShiftList,
  renderAuxiliarySubmissionList,
  renderBreakdownList,
  renderEntryList,
  renderListError,
} from "./render.js?v=20260629-shift-manager-labels-v1";
import { entryTime } from "./utils.js?v=20260629-shift-manager-labels-v1";

export async function loadEntryLists() {
  await Promise.all([loadRecentEntries(), loadPendingEntries()]);
}

export async function loadRecentEntries() {
  const container = document.querySelector("#recent-entries");
  try {
    const payload = await apiJson("/api/entries?sort=recent&limit=10");
    renderEntryList(
      container,
      Array.isArray(payload.entries) ? payload.entries : [],
      "Son kayÄ±t yok.",
    );
  } catch (error) {
    renderListError(container, `Son kayÄ±tlar yÃ¼klenemedi: ${error.message}`);
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

    renderEntryList(container, entries, "Bekleyen kayÄ±t yok.");
  } catch (error) {
    renderListError(container, `Bekleyen kayÄ±tlar yÃ¼klenemedi: ${error.message}`);
  }
}

export async function loadAuxiliarySubmissions() {
  const container = document.querySelector("#auxiliary-submissions");
  try {
    const payload = await apiJson("/api/auxiliary-systems/submissions?limit=20");
    renderAuxiliarySubmissionList(
      container,
      Array.isArray(payload.submissions) ? payload.submissions : [],
      "Son gÃ¶nderim yok.",
    );
  } catch (error) {
    renderListError(
      container,
      `YardÄ±mcÄ± sistemler gÃ¶nderimleri yÃ¼klenemedi: ${error.message}`,
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

export async function loadBreakdowns() {
  const container = document.querySelector("#breakdown-submissions");
  try {
    const payload = await apiJson("/api/breakdowns?limit=20");
    const breakdowns = Array.isArray(payload.breakdowns)
      ? payload.breakdowns
      : Array.isArray(payload.items)
        ? payload.items
        : [];
    renderBreakdownList(container, breakdowns, "Son ariza kaydi yok.");
  } catch (error) {
    renderListError(container, `Ariza kayitlari yuklenemedi: ${error.message}`);
  }
}
