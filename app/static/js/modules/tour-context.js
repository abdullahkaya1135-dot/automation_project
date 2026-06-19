import { ACTIVE_CONTEXT_KEY } from "./constants.js?v=20260619-frontend-cleanup";
import {
  automaticTourTimingForRequest,
  dateForDisplay,
  dateForRequest,
} from "./dates.js?v=20260619-frontend-cleanup";
import { setInputValue } from "./utils.js?v=20260619-frontend-cleanup";

export function updateContextStatus(context) {
  const status = document.querySelector("#context-status");
  if (!status) {
    return;
  }

  status.classList.remove(
    "status-muted",
    "status-success",
    "status-warning",
    "status-error",
  );
  if (!context) {
    status.textContent = "Aktif tur yok";
    status.classList.add("status-muted");
    return;
  }

  status.textContent = `Tur ${dateForDisplay(context.date)} / ${context.shift}`;
  status.classList.add("status-success");
}

export function applyTourContext(context) {
  setInputValue("#tour-context-id", context.id);
  setInputValue("#tour-date", dateForRequest(context.date));
  setInputValue("#ambient-temp", context.ambient_temp);
  setInputValue("#production-engineer", context.production_engineer);
  setInputValue("#shift-chief", context.shift_chief);
  setInputValue("#shift", context.shift);
  updateContextStatus(context);
}

export function matchingTourContext(context, automaticTiming) {
  if (!context || !automaticTiming) {
    return null;
  }

  const sameDate = dateForDisplay(context.date) === dateForDisplay(automaticTiming.date);
  const sameShift = String(context.shift || "") === String(automaticTiming.shift || "");
  return sameDate && sameShift ? context : null;
}

export function applyAutomaticTourTiming(timing) {
  setInputValue("#tour-context-id", "");
  setInputValue("#tour-date", timing ? dateForRequest(timing.date) : "");
  setInputValue("#shift", timing ? timing.shift : "");
}

export function readStoredTourContext() {
  try {
    const raw = window.sessionStorage.getItem(ACTIVE_CONTEXT_KEY);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw);
    if (parsed && parsed.id) {
      return parsed;
    }
  } catch (_error) {
    return null;
  }
  return null;
}

export function storeTourContext(context) {
  try {
    window.sessionStorage.setItem(ACTIVE_CONTEXT_KEY, JSON.stringify(context));
  } catch (_error) {
    // Session storage is helpful for speed, but the saved backend context remains valid.
  }
}

export function clearStoredTourContext() {
  try {
    window.sessionStorage.removeItem(ACTIVE_CONTEXT_KEY);
  } catch (_error) {
    // Nothing to clear if the browser blocks session storage.
  }
}

export function initializeAutomaticTourTiming() {
  applyAutomaticTourTiming(automaticTourTimingForRequest());
}
