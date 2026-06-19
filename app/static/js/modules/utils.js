export function setInputValue(selector, value) {
  const input = document.querySelector(selector);
  if (input) {
    input.value = value == null ? "" : String(value);
  }
}

export function setMessage(element, text, kind) {
  if (!element) {
    return;
  }
  element.textContent = text;
  element.classList.remove("error", "success", "warning");
  if (kind) {
    element.classList.add(kind);
  }
}

export function setButtonBusy(button, busy, busyText) {
  if (!button) {
    return;
  }
  if (!button.dataset.defaultText) {
    button.dataset.defaultText = button.textContent;
  }
  button.disabled = busy;
  button.textContent = busy
    ? busyText || button.dataset.defaultText
    : button.dataset.defaultText;
}

export function updateStatusPill(element, text, kind) {
  if (!element) {
    return;
  }
  element.textContent = text;
  element.classList.add("status-pill");
  element.classList.remove(
    "status-muted",
    "status-success",
    "status-warning",
    "status-error",
  );
  if (kind) {
    element.classList.add(`status-${kind}`);
  }
}

export function numericContextId(value) {
  const numericValue = Number(value);
  return Number.isFinite(numericValue) && numericValue > 0 ? numericValue : null;
}

export function cleanRequired(value) {
  return String(value || "").trim();
}

export function cleanOptional(value) {
  const text = String(value || "").trim();
  return text || null;
}

export function uniqueSorted(values) {
  return Array.from(new Set(values.filter(Boolean))).sort(compareOptionText);
}

export function compareOptionText(left, right) {
  return String(left).localeCompare(String(right), "tr", {
    numeric: true,
    sensitivity: "base",
  });
}

export function displayValue(value) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  if (typeof value === "number") {
    return new Intl.NumberFormat("tr-TR", {
      maximumFractionDigits: 3,
    }).format(value);
  }
  return String(value);
}

export function formatTimestamp(value) {
  if (!value) {
    return "";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return String(value);
  }
  return new Intl.DateTimeFormat("tr-TR", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(parsed);
}

export function entryTime(entry) {
  const value = entry.submitted_at || entry.created_at || "";
  const parsed = Date.parse(value);
  return Number.isNaN(parsed) ? 0 : parsed;
}

export function createClientRequestId() {
  if (crypto?.randomUUID) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export function downloadTextFile(filename, text, contentType) {
  const blob = new Blob([text], { type: `${contentType};charset=utf-8` });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
