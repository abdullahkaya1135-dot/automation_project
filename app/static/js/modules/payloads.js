import {
  auxiliaryCheckFields,
  auxiliaryPayloadFields,
  entryPayloadSchemaVersion,
  processEntryPayloadFields,
  temperatureRepeatPayloadFields,
} from "./field-definitions.js?v=20260615-fields";
import { localIsoDate } from "./dates.js?v=20260612-refactor";
import { selectedShopOrderOption } from "./shop-orders/dropdowns.js?v=20260615-shop-orders";
import { expandTemperatureShorthand } from "./temperature.js?v=20260612-refactor";
import {
  cleanOptional,
  cleanRequired,
  numericContextId,
} from "./utils.js?v=20260612-refactor";

export function entryRequestBody(form, contextId) {
  const formData = new FormData(form);
  const selectedOption = selectedShopOrderOption();
  const repeatFields = temperatureRepeatPayloadFields();
  const payload = {};
  for (const fieldName of processEntryPayloadFields()) {
    const value = repeatFields.has(fieldName)
      ? expandTemperatureShorthand(formData.get(fieldName))
      : formData.get(fieldName);
    payload[fieldName] = cleanOptional(value);
  }
  if (selectedOption) {
    payload.col_h = selectedOption.orderNo;
  }

  return {
    payload_schema_version: entryPayloadSchemaVersion(),
    tour_context_id: numericContextId(contextId),
    payload,
    status: cleanOptional(formData.get("status")),
    notes: cleanOptional(formData.get("notes")),
    mold_info: cleanOptional(formData.get("mold_info")),
  };
}

export function auxiliaryRequestBody(form, recordedAt = new Date()) {
  const formData = new FormData(form);
  const checkFields = auxiliaryCheckFields();
  const payload = {};
  for (const fieldName of auxiliaryPayloadFields()) {
    if (checkFields.includes(fieldName)) {
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
  const checkFields = auxiliaryCheckFields();
  return auxiliaryPayloadFields().some((fieldName) => (
    !checkFields.includes(fieldName)
    && Boolean(cleanOptional(payload[fieldName]))
  ));
}
