import { automaticTourTimingForRequest } from "../dates.js?v=20260612-refactor";
import {
  queueOfflineRecord,
  syncOutbox,
} from "../offline/outbox-sync.js?v=20260616-offline-split";
import {
  applyAutomaticTourTiming,
  applyTourContext,
  storeTourContext,
} from "../tour-context.js?v=20260612-refactor";
import {
  cleanRequired,
  createClientRequestId,
  setButtonBusy,
  setMessage,
} from "../utils.js?v=20260612-refactor";

export async function handleTourContextSubmit(event) {
  event.preventDefault();

  const form = event.currentTarget;
  const message = document.querySelector("#tour-context-message");
  const button = form.querySelector("button[type='submit']");
  if (!form.reportValidity()) {
    return;
  }

  setMessage(message, "Tur bilgileri telefona kaydediliyor...", "");
  setButtonBusy(button, true, "Kaydediliyor");

  try {
    const recordedAt = new Date();
    const automaticTiming = automaticTourTimingForRequest(recordedAt);
    applyAutomaticTourTiming(automaticTiming);
    const clientRequestId = createClientRequestId();
    const body = tourContextRequestBody(form, automaticTiming, clientRequestId, recordedAt);

    await queueOfflineRecord("tour_context", body);
    const context = localTourContext(body, clientRequestId);

    applyTourContext(context);
    storeTourContext(context);
    setMessage(
      message,
      "Tur bilgileri telefona kaydedildi. Baglanti gelince senkronize edilecek.",
      "warning",
    );
    await syncOutbox({ reason: "tour_context_submit" });
  } catch (error) {
    setMessage(message, `Tur bilgileri kaydedilemedi: ${error.message}`, "error");
  } finally {
    setButtonBusy(button, false);
  }
}

function tourContextRequestBody(form, automaticTiming, clientRequestId, recordedAt) {
  const formData = new FormData(form);
  return {
    date: automaticTiming.date,
    ambient_temp: cleanRequired(formData.get("ambient_temp")),
    production_engineer: cleanRequired(formData.get("production_engineer")),
    shift_chief: cleanRequired(formData.get("shift_chief")),
    shift: automaticTiming.shift,
    client_request_id: clientRequestId,
    client_recorded_at: recordedAt.toISOString(),
  };
}

function localTourContext(body, clientRequestId) {
  return {
    id: `local:${clientRequestId}`,
    client_request_id: clientRequestId,
    client_recorded_at: body.client_recorded_at,
    ...body,
  };
}
