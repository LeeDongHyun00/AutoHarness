const STATUS_TEXT = {
  confirmed: "Confirmed",
  waitlisted: "On the waitlist",
  cancelled: "Cancelled",
};

export function statusText(status) {
  return STATUS_TEXT[status] || status;
}

export function formatWhen(iso) {
  return new Date(iso).toISOString().replace("T", " ").slice(0, 16) + " UTC";
}

export function setText(element, text) {
  element.textContent = text;
  element.hidden = !text;
}

export function seatsSummary(event) {
  if (event.seats_left > 0) return `${event.seats_left} of ${event.capacity} seats left`;
  return `Full · ${event.waitlist_count} on the waitlist`;
}
