import { apiJson } from "../api.js?v=20260612-refactor";
import { applyFieldDefinitions } from "./field-definitions.js?v=20260615-fields";
import {
  readBootstrapCache,
  writeBootstrapCache,
} from "./offline/outbox-db.js?v=20260616-offline-split";
import {
  formatTimestamp,
  setMessage,
} from "./utils.js?v=20260612-refactor";

export async function loadBootstrapPayload({
  cacheMessageSelector = null,
} = {}) {
  try {
    const payload = await apiJson("/api/bootstrap");
    applyFieldDefinitions(payload.field_definitions);
    try {
      await writeBootstrapCache(payload);
    } catch (_cacheError) {
      // The live bootstrap payload is enough; offline cache is an extra safety net.
    }
    return payload;
  } catch (error) {
    const cachedBootstrap = await readBootstrapCache();
    if (!cachedBootstrap) {
      throw error;
    }
    const payload = cachedBootstrap.payload;
    applyFieldDefinitions(payload.field_definitions);
    if (payload?.shop_order_source) {
      payload.shop_order_source.offline_cached_at = cachedBootstrap.updated_at;
    }
    if (cacheMessageSelector) {
      setMessage(
        document.querySelector(cacheMessageSelector),
        `Cevrimdisi mod: son liste kullaniliyor (${formatTimestamp(cachedBootstrap.updated_at)}).`,
        "warning",
      );
    }
    return payload;
  }
}

export function updateHeaderStatuses(payload) {
  updateExcelStatus(payload?.excel);
  updateAuxiliarySystemsStatus(payload?.auxiliary_systems);
}

export function updateExcelStatus(excel) {
  const status = document.querySelector("#excel-status");
  if (!status) {
    return;
  }

  status.classList.remove(
    "status-muted",
    "status-success",
    "status-warning",
    "status-error",
  );
  if (excel && excel.available) {
    status.textContent = "Excel hazir";
    status.title = "";
    status.classList.add("status-success");
    return;
  }

  status.textContent = "Excel kullanilamiyor";
  status.title = excel?.last_error || "";
  status.classList.add("status-warning");
}

export function updateAuxiliarySystemsStatus(auxiliarySystems) {
  const status = document.querySelector("#auxiliary-systems-status");
  if (!status) {
    return;
  }

  status.classList.remove(
    "status-muted",
    "status-success",
    "status-warning",
    "status-error",
  );
  if (auxiliarySystems?.target_available && auxiliarySystems?.form_available) {
    status.textContent = "Yardimci hazir";
    status.title = "";
    status.classList.add("status-success");
    return;
  }

  if (auxiliarySystems?.target_available) {
    status.textContent = "Form dosyasi yok";
    status.title = auxiliarySystems?.form_error || "";
    status.classList.add("status-warning");
    return;
  }

  status.textContent = "Yardimci Excel yok";
  status.title = auxiliarySystems?.target_error || auxiliarySystems?.form_error || "";
  status.classList.add("status-warning");
}

export function applyAuxiliaryDate(value) {
  const dateInput = document.querySelector("#auxiliary-date");
  const dateLabel = document.querySelector("#auxiliary-date-label");
  if (dateInput) {
    dateInput.value = value || "";
  }
  if (dateLabel) {
    dateLabel.textContent = value ? `Tarih: ${value}` : "";
  }
}
