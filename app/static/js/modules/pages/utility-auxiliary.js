import { loadAuxiliarySubmissions } from "../lists.js?v=20260612-refactor";
import {
  queueOfflineRecord,
  syncOutbox,
} from "../offline/outbox-sync.js?v=20260616-offline-split";
import {
  auxiliaryRequestBody,
  hasAuxiliaryMeasurement,
} from "../payloads.js?v=20260612-refactor";
import {
  createClientRequestId,
  setButtonBusy,
  setMessage,
} from "../utils.js?v=20260612-refactor";

export async function handleAuxiliarySubmit(event) {
  event.preventDefault();

  const form = event.currentTarget;
  const message = document.querySelector("#auxiliary-message");
  const button = form.querySelector("button[type='submit']");

  if (!form.reportValidity()) {
    return;
  }

  const recordedAt = new Date();
  const body = offlineAuxiliaryRequestBody(form, recordedAt);
  if (!hasAuxiliaryMeasurement(body.payload)) {
    setMessage(message, "En az bir yardimci sistem olcumu girin.", "error");
    return;
  }

  setMessage(message, "Yardimci sistemler telefona kaydediliyor...", "");
  setButtonBusy(button, true, "Gonderiliyor");

  try {
    await queueOfflineRecord("auxiliary_submission", body);
    form.reset();
    setMessage(
      message,
      "Yardimci sistemler telefona kaydedildi. Baglanti gelince senkronize edilecek.",
      "warning",
    );
    await syncOutbox({ reason: "auxiliary_submit" });
    await loadAuxiliarySubmissions();
  } catch (error) {
    setMessage(
      message,
      `Yardimci sistemler telefona kaydedilemedi: ${error.message}`,
      "error",
    );
  } finally {
    setButtonBusy(button, false);
  }
}

function offlineAuxiliaryRequestBody(form, recordedAt) {
  const body = auxiliaryRequestBody(form, recordedAt);
  body.client_request_id = createClientRequestId();
  body.client_recorded_at = recordedAt.toISOString();
  return body;
}
