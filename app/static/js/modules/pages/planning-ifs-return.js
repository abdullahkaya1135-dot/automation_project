import { apiJson } from "../../api.js?v=20260612-refactor";
import {
  renderIfsReturnCandidates,
  renderIfsReturnPrintArea,
} from "../render/ifs-return.js?v=20260615-render";
import {
  renderListError,
  renderLoading,
} from "../render/shared.js?v=20260615-render";
import { setButtonBusy, setMessage } from "../utils.js?v=20260612-refactor";

let latestIfsReturnCandidatesPayload = null;

export async function handleIfsReturnCandidates(event) {
  const button = event.currentTarget;
  const message = document.querySelector("#ifs-return-message");
  const container = document.querySelector("#ifs-return-results");

  setMessage(message, "IFS kontrolü çalışıyor...", "");
  renderLoading(container, "IFS verileri okunuyor...");
  setIfsReturnPrintPayload(null);
  setButtonBusy(button, true, "Kontrol ediliyor");

  try {
    const payload = await apiJson("/api/ifs/u1-return-candidates");
    renderIfsReturnCandidates(container, payload);
    setIfsReturnPrintPayload(payload);
    const candidateCount = Number(payload.return_candidate_count || 0);
    if (candidateCount > 0) {
      setMessage(message, `${candidateCount} iade adayı bulundu.`, "warning");
    } else {
      setMessage(message, "İade adayı bulunmadı.", "success");
    }
  } catch (error) {
    setMessage(message, `IFS kontrolü başarısız: ${error.message}`, "error");
    renderListError(container, `IFS kontrolü başarısız: ${error.message}`);
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
