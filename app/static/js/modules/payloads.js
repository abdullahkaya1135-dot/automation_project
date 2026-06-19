import {
  AUXILIARY_CHECK_FIELDS,
  AUXILIARY_PAYLOAD_FIELDS,
  ENTRY_PAYLOAD_FIELDS,
  ENTRY_PAYLOAD_SCHEMA_VERSION,
  TEMPERATURE_REPEAT_PAYLOAD_FIELDS,
} from "./constants.js?v=20260619-frontend-cleanup";
import { localIsoDate } from "./dates.js?v=20260619-frontend-cleanup";
import { selectedShopOrderOption } from "./shop-orders.js?v=20260619-frontend-cleanup";
import { expandTemperatureShorthand } from "./temperature.js?v=20260619-frontend-cleanup";
import {
  cleanOptional,
  cleanRequired,
  numericContextId,
} from "./utils.js?v=20260619-frontend-cleanup";

export function entryRequestBody(form, contextId) {
  const formData = new FormData(form);
  const selectedOption = selectedShopOrderOption();
  const payload = {};
  for (const fieldName of ENTRY_PAYLOAD_FIELDS) {
    const value = TEMPERATURE_REPEAT_PAYLOAD_FIELDS.has(fieldName)
      ? expandTemperatureShorthand(formData.get(fieldName))
      : formData.get(fieldName);
    payload[fieldName] = cleanOptional(value);
  }
  if (selectedOption) {
    payload.col_h = selectedOption.orderNo;
  }

  return {
    payload_schema_version: ENTRY_PAYLOAD_SCHEMA_VERSION,
    tour_context_id: numericContextId(contextId),
    payload,
    status: cleanOptional(formData.get("status")),
    notes: cleanOptional(formData.get("notes")),
    mold_info: cleanOptional(formData.get("mold_info")),
  };
}

export function auxiliaryRequestBody(form, recordedAt = new Date()) {
  const formData = new FormData(form);
  const payload = {};
  for (const fieldName of AUXILIARY_PAYLOAD_FIELDS) {
    if (AUXILIARY_CHECK_FIELDS.includes(fieldName)) {
      payload[fieldName] = formData.get(fieldName) === "on";
    } else {
      payload[fieldName] = cleanOptional(formData.get(fieldName));
    }
  }

  return {
    recorded_date: localIsoDate(recordedAt) || cleanRequired(formData.get("recorded_date")),
    payload,
  };
}

export function hasAuxiliaryMeasurement(payload) {
  return AUXILIARY_PAYLOAD_FIELDS.some((fieldName) => (
    !AUXILIARY_CHECK_FIELDS.includes(fieldName)
    && Boolean(cleanOptional(payload[fieldName]))
  ));
}
