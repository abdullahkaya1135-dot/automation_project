export function renderEmptyState(container, text, className = "empty-state") {
  if (!container) {
    return;
  }
  const empty = document.createElement("p");
  empty.className = className;
  empty.textContent = text;
  container.replaceChildren(empty);
}

export function renderLoading(container, text) {
  renderEmptyState(container, text);
}

export function renderListError(container, text) {
  renderEmptyState(container, text, "empty-state error");
}
