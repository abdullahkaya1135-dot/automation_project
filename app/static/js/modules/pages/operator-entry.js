import {
  queueOfflineRecord,
  syncOutbox,
} from "../offline/outbox-sync.js?v=20260616-offline-split";
import { entryRequestBody } from "../payloads.js?v=20260612-refactor";
import { resetShopOrderDropdowns } from "../shop-orders/dropdowns.js?v=20260615-shop-orders";
import { normalizeTemperatureShorthandForm } from "../temperature.js?v=20260612-refactor";
import { readStoredTourContext } from "../tour-context.js?v=20260612-refactor";
import {
  createClientRequestId,
  setButtonBusy,
  setMessage,
} from "../utils.js?v=20260612-refactor";

export async function handleEntrySubmit(event) {
  event.preventDefault();

  const form = event.currentTarget;
  const message = document.querySelector("#entry-message");
  const button = form.querySelector("button[type='submit']");
  const contextId = document.querySelector("#tour-context-id")?.value;
  const activeContext = readStoredTourContext();

  if (!contextId) {
    setMessage(message, "Kayit gondermeden once tur bilgilerini kaydedin.", "error");
    document.querySelector("#tour-context-heading")?.scrollIntoView({
      behavior: "smooth",
      block: "start",
    });
    return;
  }

  if (!form.reportValidity()) {
    return;
  }

  normalizeTemperatureShorthandForm(form);
  const body = offlineEntryRequestBody(form, contextId);
  const dependsOnClientRequestId = pendingContextClientId(activeContext);

  setMessage(message, "Kayit telefona kaydediliyor...", "");
  setButtonBusy(button, true, "Gonderiliyor");

  try {
    await queueOfflineRecord("entry", body, dependsOnClientRequestId);
    form.reset();
    resetShopOrderDropdowns();
    setMessage(
      message,
      "Kayit telefona kaydedildi. Baglanti gelince senkronize edilecek.",
      "warning",
    );
    await syncOutbox({ reason: "entry_submit" });
  } catch (error) {
    setMessage(message, `Kayit telefona kaydedilemedi: ${error.message}`, "error");
  } finally {
    setButtonBusy(button, false);
  }
}

function offlineEntryRequestBody(form, contextId) {
  const recordedAt = new Date();
  const body = entryRequestBody(form, contextId);
  body.client_request_id = createClientRequestId();
  body.client_recorded_at = recordedAt.toISOString();
  return body;
}

function pendingContextClientId(activeContext) {
  return activeContext?.client_request_id
    && String(activeContext.id || "").startsWith("local:")
    ? activeContext.client_request_id
    : null;
}
