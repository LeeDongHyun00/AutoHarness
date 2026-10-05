import { api } from "./api.js";
import { formatDate, showMessage, statusLabel } from "./format.js";

const params = new URLSearchParams(location.search);
const projectKey = params.get("project") || "CORE";
const issueId = Number(params.get("id"));

const els = {
  back: document.getElementById("back-link"),
  userName: document.getElementById("user-name"),
  message: document.getElementById("issue-message"),
  article: document.getElementById("issue"),
  title: document.getElementById("issue-title"),
  meta: document.getElementById("issue-meta"),
  description: document.getElementById("issue-description"),
  form: document.getElementById("status-form"),
  select: document.getElementById("status-select"),
  statusMessage: document.getElementById("status-message"),
};

function render(issue) {
  document.title = issue.title;
  els.title.textContent = issue.title;
  els.meta.textContent = `#${issue.id} · ${statusLabel(issue.status)} · reported by ${issue.reporter.name} on ${formatDate(issue.created_at)}`;
  els.description.textContent = issue.description || "No description.";
  els.select.value = issue.status;
  els.article.hidden = false;
}

async function load() {
  els.back.href = `/?project=${encodeURIComponent(projectKey)}`;
  if (!Number.isInteger(issueId) || issueId <= 0) {
    showMessage(els.message, "Issue not found.");
    return;
  }
  try {
    const [{ issue }, { user }] = await Promise.all([api.getIssue(projectKey, issueId), api.me()]);
    els.userName.textContent = user.name;
    render(issue);
  } catch (err) {
    showMessage(els.message, err.message);
  }
}

els.form.addEventListener("submit", async (event) => {
  event.preventDefault();
  showMessage(els.statusMessage, "");
  try {
    const { issue } = await api.changeStatus(projectKey, issueId, els.select.value);
    render(issue);
  } catch (err) {
    showMessage(els.statusMessage, err.message);
  }
});

load();
