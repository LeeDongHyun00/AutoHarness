import { client } from "./client.js";
import { formatWhen, seatsSummary, setText } from "./ui.js";

const list = document.getElementById("event-list");
const status = document.getElementById("events-status");

function renderEvent(event) {
  const item = document.createElement("li");
  item.className = "event-card";
  const link = document.createElement("a");
  link.href = `/event.html?slug=${encodeURIComponent(event.slug)}`;
  link.textContent = event.title;
  const when = document.createElement("p");
  when.className = "muted";
  when.textContent = formatWhen(event.starts_at);
  const seats = document.createElement("p");
  seats.className = "seats";
  seats.textContent = seatsSummary(event);
  item.append(link, when, seats);
  return item;
}

async function load() {
  try {
    const { events } = await client.events();
    list.replaceChildren(...events.map(renderEvent));
    if (events.length === 0) setText(status, "No upcoming events.");
  } catch (err) {
    setText(status, err.message);
  }
}

load();
