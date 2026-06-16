import {
  handleIfsReturnCandidates,
  handlePrintIfsReturnCandidates,
} from "./planning-ifs-return.js?v=20260616-planning-ifs";
import { setMessage } from "../utils.js?v=20260612-refactor";
import {
  loadBootstrapPayload,
  updateHeaderStatuses,
} from "../bootstrap.js?v=20260612-refactor";
import { handleCreateCycleReport } from "./planning-cycle-report.js?v=20260616-planning-cycle";

export function initPlanningPage() {
  const cycleReportButton = document.querySelector("#create-cycle-report");
  if (cycleReportButton) {
    cycleReportButton.addEventListener("click", handleCreateCycleReport);
  }

  const ifsReturnButton = document.querySelector("#run-ifs-return-candidates");
  if (ifsReturnButton) {
    ifsReturnButton.addEventListener("click", handleIfsReturnCandidates);
  }

  const ifsReturnPrintButton = document.querySelector("#print-ifs-return-candidates");
  if (ifsReturnPrintButton) {
    ifsReturnPrintButton.disabled = true;
    ifsReturnPrintButton.addEventListener("click", handlePrintIfsReturnCandidates);
  }

  void initializePlanning();
}

async function initializePlanning() {
  try {
    const payload = await loadBootstrapPayload();
    updateHeaderStatuses(payload);
  } catch (error) {
    setMessage(
      document.querySelector("#cycle-report-message"),
      `Baslatma basarisiz: ${error.message}`,
      "error",
    );
  }
}
