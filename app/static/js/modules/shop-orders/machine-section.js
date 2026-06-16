export function machineSection(machine) {
  const match = String(machine || "").match(/\d+/);
  if (!match) {
    return "";
  }
  const code = Number(match[0]);
  if (code === 271 || (code >= 100 && code <= 199)) {
    return "first";
  }
  if (code >= 200 && code <= 599) {
    return "second";
  }
  return "first";
}

export function applyMachineSection(machine) {
  const section = machineSection(machine);
  const sectionFields = document.querySelectorAll("[data-section-field]");
  for (const container of sectionFields) {
    const visible = section && container.dataset.sectionField === section;
    container.hidden = !visible;
    for (const input of container.querySelectorAll("input, select, textarea")) {
      input.disabled = !visible;
      if (!visible) {
        input.value = "";
      }
    }
  }
}
