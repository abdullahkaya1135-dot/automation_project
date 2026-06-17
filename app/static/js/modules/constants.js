export const ACTIVE_CONTEXT_KEY = "process.activeTourContext";

export const OFFLINE_DB_NAME = "process-offline-v1";
export const OFFLINE_DB_VERSION = 1;
export const OFFLINE_STATUS_QUEUED = "queued";
export const OFFLINE_STATUS_SYNCING = "syncing";
export const OFFLINE_STATUS_RETRYABLE = "retryable";
export const OFFLINE_STATUS_SERVER_SAVED = "server_saved";
export const OFFLINE_STATUS_VALIDATION_FAILED = "validation_failed";
export const OFFLINE_PENDING_STATUSES = new Set([
  OFFLINE_STATUS_QUEUED,
  OFFLINE_STATUS_SYNCING,
  OFFLINE_STATUS_RETRYABLE,
  OFFLINE_STATUS_VALIDATION_FAILED,
]);

export const ENTRY_PAYLOAD_SCHEMA_VERSION = 2;
export const ENTRY_PAYLOAD_FIELDS = [
  "col_f",
  "col_g",
  "col_h",
  "col_i",
  "col_j",
  "col_k",
  "col_l",
  "col_m",
  "col_n",
  "col_o",
  "col_p",
  "col_q",
  "col_r",
  "col_s",
  "col_t",
  "col_u",
  "col_v",
  "col_w",
  "col_x",
  "col_y",
];
export const TEMPERATURE_REPEAT_PAYLOAD_FIELDS = new Set([
  "col_r",
  "col_s",
  "col_x",
  "col_y",
]);
export const TEMPERATURE_SHORTHAND_SELECTORS = [
  "#injection-pressures",
  "#injection-speeds",
  "#oven-temps",
  "#mold-temps",
];

export const AMOUNT_CONTROL_SHIFTS = [
  "24.00-08.00",
  "08.00-16.00",
  "16.00-24.00",
];

export const AUXILIARY_PAYLOAD_FIELDS = [
  "tower_frequency",
  "tower_set_pressure",
  "tower_feedback_pressure",
  "chiller_motor_frequency",
  "chiller_motor_set_pressure",
  "chiller_motor_feedback_pressure",
  "termokar_chiller_1_temp_set",
  "termokar_chiller_1_inlet_temp",
  "termokar_chiller_1_outlet_temp",
  "termokar_chiller_2_temp_set",
  "termokar_chiller_2_inlet_temp",
  "termokar_chiller_2_outlet_temp",
  "planer_temp_set",
  "planer_inlet_temp",
  "planer_outlet_temp",
  "itech_temp_set",
  "itech_current_temp",
  "compressor_high_708_pressure",
  "compressor_high_709_pressure",
  "compressor_high_710_pressure",
  "compressor_high_711_pressure",
  "compressor_low_712_pressure",
  "compressor_low_713_pressure",
  "compressor_low_714_pressure",
  "compressor_low_715_pressure",
  "compressor_low_716_pressure",
  "oil_cooling_water_tank_checked",
  "chiller_water_tank_checked",
  "air_tank_1_drained",
  "air_tank_2_drained",
  "cleanliness_checked",
];
export const AUXILIARY_CHECK_FIELDS = [
  "oil_cooling_water_tank_checked",
  "chiller_water_tank_checked",
  "air_tank_1_drained",
  "air_tank_2_drained",
  "cleanliness_checked",
];

export const SYNC_LABELS = {
  synced: "Senkronize",
  pending_excel: "Beklemede",
  failed_excel: "Başarısız",
};
