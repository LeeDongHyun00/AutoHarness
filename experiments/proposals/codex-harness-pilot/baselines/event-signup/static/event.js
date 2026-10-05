import { client } from "./client.js";
import { formatWhen, seatsSummary, setText, statusText } from "./ui.js";
import { validateSignup } from "./validation.js";

const slug = new URLSearchParams(location.search).get("slug") || "";

const els = {
  status: document.getElementById("event-status"),
  details: document.getElementById("event-details"),
  title: document.getElementById("event-title"),
  when: document.getElementById("event-when"),
  seats: document.getElementById("event-seats"),
  form: document.getElementById("signup-form"),
  formError: document.getElementById("form-error"),
  submit: document.getElementById("submit-button"),
  confirmation: document.getElementById("confirmation"),
  confirmationTitle: document.getElementById("confirmation-title"),
  confirmationDetail: document.getElementById("confirmation-detail"),
  manageLink: document.getElementById("manage-link"),
};

const FIELDS = ["name", "email", "affiliation", "note"];

function readForm() {
  return Object.fromEntries(FIELDS.map((name) => [name, els.form.elements[name].value]));
}

function showFieldErrors(errors) {
  for (const name of FIELDS) {
    const target = els.form.querySelector(`[data-error-for="${name}"]`);
    setText(target, errors[name] || "");
    els.form.elements[name].setAttribute("aria-invalid", errors[name] ? "true" : "false");
  }
}

function describeError(err) {
  if (err.code === "already_registered") return "This email is already registered for this event.";
  if (err.code === "invalid_input") return err.message;
  return "Sorry, we could not complete your signup. Please try again.";
}

function renderEvent(event) {
  document.title = event.title;
  els.title.textContent = event.title;
  els.when.textContent = formatWhen(event.starts_at);
  els.seats.textContent = seatsSummary(event);
  els.details.hidden = false;
  els.form.hidden = false;
}

function showConfirmation(registration) {
  els.confirmationTitle.textContent = statusText(registration.status);
  els.confirmationDetail.textContent =
    registration.status === "waitlisted"
      ? `You are number ${registration.waitlist_position} on the waitlist.`
      : `See you there, ${registration.name}!`;
  els.manageLink.href = `/registration.html?id=${registration.id}&token=${encodeURIComponent(registration.token)}`;
  els.confirmation.hidden = false;
}

async function refreshEvent() {
  const { event } = await client.event(slug);
  renderEvent(event);
}

els.form.addEventListener("submit", async (event) => {
  event.preventDefault();
  setText(els.formError, "");
  const values = readForm();
  const errors = validateSignup(values);
  showFieldErrors(errors);
  if (Object.keys(errors).length > 0) return;

  els.submit.disabled = true;
  try {
    const { registration } = await client.register(slug, values);
    showConfirmation(registration);
    els.submit.disabled = false;
    await refreshEvent();
  } catch (err) {
    setText(els.formError, describeError(err));
  } finally {
    els.form.reset();
  }
});

async function init() {
  try {
    await refreshEvent();
  } catch (err) {
    setText(els.status, err.status === 404 ? "Event not found." : err.message);
  }
}

init();
