import {
  applyTourContext,
  readStoredTourContext,
  storeTourContext,
} from "../tour-context.js?v=20260612-refactor";
import { setMessage } from "../utils.js?v=20260612-refactor";

export function resultPayloadForRecord(result) {
  if (result.type === "tour_context") {
    return {
      id: result.server_id,
      tour_context: result.tour_context,
    };
  }
  if (result.type === "entry") {
    return {
      entry: result.entry,
    };
  }
  if (result.type === "auxiliary_submission") {
    return {
      submission: result.submission,
    };
  }
  return {};
}

export function applyServerResultToUi(record, payload) {
  if (record.type !== "tour_context" || !payload?.tour_context) {
    return;
  }
  const activeContext = readStoredTourContext();
  if (activeContext?.client_request_id !== record.client_request_id) {
    return;
  }
  applyTourContext(payload.tour_context);
  storeTourContext(payload.tour_context);
  setMessage(
    document.querySelector("#tour-context-message"),
    "Tur bilgileri sunucuya kaydedildi.",
    "success",
  );
}
