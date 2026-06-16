let currentFieldDefinitions = null;

export function applyFieldDefinitions(definitions) {
  if (!definitions || typeof definitions !== "object") {
    return;
  }

  const processEntry = definitions.process_entry || {};
  const auxiliary = definitions.auxiliary || {};
  const nextDefinitions = {
    processEntry: {
      payloadSchemaVersion: Number(processEntry.payload_schema_version || 2),
      payloadFields: arrayOfStrings(processEntry.payload_fields),
      temperatureRepeatFields: new Set(
        arrayOfStrings(processEntry.temperature_repeat_fields),
      ),
    },
    auxiliary: {
      payloadFields: arrayOfStrings(auxiliary.payload_fields),
      checkFields: arrayOfStrings(auxiliary.check_fields),
      measurementFields: arrayOfStrings(auxiliary.measurement_fields),
    },
  };

  if (
    nextDefinitions.processEntry.payloadFields.length
    && nextDefinitions.auxiliary.payloadFields.length
  ) {
    currentFieldDefinitions = nextDefinitions;
  }
}

export function entryPayloadSchemaVersion() {
  return loadedDefinitions().processEntry.payloadSchemaVersion;
}

export function processEntryPayloadFields() {
  return loadedDefinitions().processEntry.payloadFields;
}

export function temperatureRepeatPayloadFields() {
  return loadedDefinitions().processEntry.temperatureRepeatFields;
}

export function auxiliaryPayloadFields() {
  return loadedDefinitions().auxiliary.payloadFields;
}

export function auxiliaryCheckFields() {
  return loadedDefinitions().auxiliary.checkFields;
}

export function auxiliaryMeasurementFields() {
  return loadedDefinitions().auxiliary.measurementFields;
}

function loadedDefinitions() {
  if (!currentFieldDefinitions) {
    throw new Error("Alan tanimlari henuz yuklenmedi.");
  }
  return currentFieldDefinitions;
}

function arrayOfStrings(value) {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter((item) => typeof item === "string" && item);
}
