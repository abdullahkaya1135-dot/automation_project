const TEMPERATURE_SHORTHAND_SELECTORS = [
  "#injection-pressures",
  "#injection-speeds",
  "#oven-temps",
  "#mold-temps",
];

export function initializeTemperatureShorthandInputs() {
  for (const selector of TEMPERATURE_SHORTHAND_SELECTORS) {
    const input = document.querySelector(selector);
    if (!input) {
      continue;
    }
    input.addEventListener("blur", () => {
      input.value = expandTemperatureShorthand(input.value);
    });
  }
}

export function normalizeTemperatureShorthandForm(form) {
  for (const selector of TEMPERATURE_SHORTHAND_SELECTORS) {
    const input = form.querySelector(selector);
    if (input) {
      input.value = expandTemperatureShorthand(input.value);
    }
  }
}

export function expandTemperatureShorthand(value) {
  const text = String(value || "").trim();
  if (!text || !/[xX]/.test(text)) {
    return text;
  }

  const tokens = text.split(",").map((token) => token.trim()).filter(Boolean);
  if (!tokens.length) {
    return text;
  }

  const expanded = [];
  for (const token of tokens) {
    const repeatMatch = token.match(/^([+-]?\d+(?:\.\d+)?)\s*[xX]\s*([1-9]\d*)$/);
    if (repeatMatch) {
      const repeatCount = Number(repeatMatch[2]);
      if (!Number.isSafeInteger(repeatCount) || repeatCount > 200) {
        return text;
      }
      for (let index = 0; index < repeatCount; index += 1) {
        expanded.push(repeatMatch[1]);
      }
      continue;
    }

    if (/^[+-]?\d+(?:\.\d+)?$/.test(token)) {
      expanded.push(token);
      continue;
    }

    return text;
  }

  return expanded.join("-");
}
