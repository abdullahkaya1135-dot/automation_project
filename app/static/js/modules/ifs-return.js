import { apiJson } from "../api.js?v=20260626-breakdown-context-v2";
import {
  renderIfsReturnCandidates,
  renderIfsReturnPrintArea,
  renderListError,
  renderLoading,
} from "./render.js?v=20260626-breakdown-context-v2";
import { setButtonBusy, setMessage } from "./utils.js?v=20260626-breakdown-context-v2";

let latestIfsReturnCandidatesPayload = null;

export async function handleIfsReturnCandidates(event) {
  const button = event.currentTarget;
  const message = document.querySelector("#ifs-return-message");
  const container = document.querySelector("#ifs-return-results");

  setMessage(message, "IFS kontrolÃ¼ Ã§alÄ±ÅŸÄ±yor...", "");
  renderLoading(container, "IFS verileri okunuyor...");
  setIfsReturnPrintPayload(null);
  setButtonBusy(button, true, "Kontrol ediliyor");

  try {
    const payload = await apiJson("/api/ifs/u1-return-candidates");
    renderIfsReturnCandidates(container, payload);
    setIfsReturnPrintPayload(payload);
    const candidateCount = Number(payload.return_candidate_count || 0);
    if (candidateCount > 0) {
      setMessage(message, `${candidateCount} iade adayÄ± bulundu.`, "warning");
    } else {
      setMessage(message, "Ä°ade adayÄ± bulunmadÄ±.", "success");
    }
  } catch (error) {
    setMessage(message, `IFS kontrolÃ¼ baÅŸarÄ±sÄ±z: ${error.message}`, "error");
    renderListError(container, `IFS kontrolÃ¼ baÅŸarÄ±sÄ±z: ${error.message}`);
    setIfsReturnPrintPayload(null);
  } finally {
    setButtonBusy(button, false);
  }
}

export function handlePrintIfsReturnCandidates() {
  if (!latestIfsReturnCandidatesPayload) {
    return;
  }

  renderIfsReturnPrintArea(latestIfsReturnCandidatesPayload);
  window.print();
}

export function setIfsReturnPrintPayload(payload) {
  latestIfsReturnCandidatesPayload = payload;
  renderIfsReturnPrintArea(payload);

  const printButton = document.querySelector("#print-ifs-return-candidates");
  if (printButton) {
    printButton.disabled = !payload;
  }
}
