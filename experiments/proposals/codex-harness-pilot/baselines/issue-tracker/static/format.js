const STATUS_LABELS = { open: "Open", in_progress: "In progress", done: "Done" };

export function statusLabel(status) {
  return STATUS_LABELS[status] || status;
}

// Dates are rendered in UTC so every viewer sees the same day.
export function formatDate(iso) {
  return new Date(iso).toISOString().slice(0, 10);
}

export function showMessage(element, text) {
  element.textContent = text;
  element.hidden = !text;
}
