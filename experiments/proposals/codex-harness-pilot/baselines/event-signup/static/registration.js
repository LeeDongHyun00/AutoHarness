import { client } from "./client.js";
import { setText, statusText } from "./ui.js";

const params = new URLSearchParams(location.search);
const registrationId = Number(params.get("id"));
const token = params.get("token") || "";

const els = {
  status: document.getElementById("registration-status"),
  section: document.getElementById("registration"),
  event: document.getElementById("registration-event"),
  state: document.getElementById("registration-state"),
  position: document.getElementById("registration-position"),
  cancel: document.getElementById("cancel-button"),
  cancelError: document.getElementById("cancel-error"),
};

function render(registration) {
  els.event.textContent = registration.event.title;
  els.state.textContent = statusText(registration.status);
  setText(
    els.position,
    registration.waitlist_position ? `You are number ${registration.waitlist_position} on the waitlist.` : "",
  );
  els.cancel.hidden = registration.status === "cancelled";
  els.section.hidden = false;
}

els.cancel.addEventListener("click", async () => {
  setText(els.cancelError, "");
  els.cancel.disabled = true;
  try {
    const { registration } = await client.cancel(registrationId, token);
    render(registration);
  } catch (err) {
    setText(els.cancelError, err.message);
  } finally {
    els.cancel.disabled = false;
  }
});

async function init() {
  try {
    const { registration } = await client.registration(registrationId, token);
    render(registration);
  } catch (err) {
    setText(els.status, err.status === 404 ? "Registration not found." : err.message);
  }
}

init();
