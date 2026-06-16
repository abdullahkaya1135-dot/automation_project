export function automaticTourTimingForRequest(value = new Date()) {
  const now = value;
  return {
    date: localIsoDate(now),
    shift: shiftForLocalTime(now),
  };
}

export function localIsoDate(value) {
  const localTime = value.getTime() - value.getTimezoneOffset() * 60000;
  return new Date(localTime).toISOString().slice(0, 10);
}

export function shiftForLocalTime(value) {
  const hour = value.getHours();
  if (hour < 8) {
    return "24.00-08.00";
  }
  if (hour < 16) {
    return "08.00-16.00";
  }
  return "16.00-24.00";
}

export function dateForRequest(value) {
  const text = String(value || "").trim();
  const displayMatch = text.match(/^(\d{2})\.(\d{2})\.(\d{4})$/);
  if (displayMatch) {
    const [, day, month, year] = displayMatch;
    return `${year}-${month}-${day}`;
  }
  return text;
}

export function dateForDisplay(value) {
  const text = String(value || "").trim();
  const isoMatch = text.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (isoMatch) {
    const [, year, month, day] = isoMatch;
    return `${day}.${month}.${year}`;
  }
  return text;
}
