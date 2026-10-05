import { api, getUserId, setUserId } from "./api.js";
import { formatDate, showMessage, statusLabel } from "./format.js";

const DEFAULT_PROJECT = "CORE";
const DEFAULTS = { status: "", sort: "created-desc" };

const els = {
  projectName: document.getElementById("project-name"),
  user: document.getElementById("acting-user"),
  userName: document.getElementById("user-name"),
  status: document.getElementById("status-filter"),
  sort: document.getElementById("sort-order"),
  list: document.getElementById("issue-list"),
  message: document.getElementById("list-message"),
  form: document.getElementById("new-issue-form"),
  formMessage: document.getElementById("form-message"),
};

const state = { projectKey: DEFAULT_PROJECT, ...DEFAULTS };

function readProjectFromUrl() {
  return new URLSearchParams(location.search).get("project") || DEFAULT_PROJECT;
}

function writeUrl() {
  const params = new URLSearchParams({ project: state.projectKey });
  if (state.status) params.set("status", state.status);
  if (state.sort !== DEFAULTS.sort) params.set("sort", state.sort);
  history.pushState(null, "", `?${params}`);
}

function syncControls() {
  els.status.value = state.status;
  els.sort.value = state.sort;
}

function renderIssue(issue) {
  const item = document.createElement("li");
  item.className = "issue";
  item.dataset.issueId = String(issue.id);

  const link = document.createElement("a");
  link.href = `/issue.html?project=${encodeURIComponent(state.projectKey)}&id=${issue.id}`;
  link.textContent = issue.title;

  const meta = document.createElement("span");
  meta.className = "muted";
  meta.textContent = `#${issue.id} · ${statusLabel(issue.status)} · ${formatDate(issue.created_at)}`;

  const badge = document.createElement("span");
  badge.className = `badge status-${issue.status}`;
  badge.textContent = statusLabel(issue.status);

  item.append(badge, link, meta);
  return item;
}

async function loadIssues() {
  showMessage(els.message, "");
  try {
    const { issues } = await api.listIssues(state.projectKey, state);
    els.list.replaceChildren(...issues.map(renderIssue));
    if (issues.length === 0) showMessage(els.message, "No issues match these filters.");
  } catch (err) {
    els.list.replaceChildren();
    showMessage(els.message, err.message);
  }
}

async function loadHeader() {
  try {
    const [{ user }, { projects }] = await Promise.all([api.me(), api.projects()]);
    els.userName.textContent = user.name;
    const project = projects.find((p) => p.key === state.projectKey);
    els.projectName.textContent = project ? `${project.name} issues` : "Issues";
  } catch (err) {
    els.userName.textContent = "";
    els.projectName.textContent = "Issues";
  }
}

els.status.addEventListener("change", () => {
  state.status = els.status.value;
  writeUrl();
  loadIssues();
});

els.sort.addEventListener("change", () => {
  state.sort = els.sort.value;
  writeUrl();
  loadIssues();
});

els.user.addEventListener("change", () => {
  if (!els.user.value) return;
  setUserId(els.user.value);
  loadHeader();
  loadIssues();
});

els.form.addEventListener("submit", async (event) => {
  event.preventDefault();
  showMessage(els.formMessage, "");
  const title = els.form.elements.title.value.trim();
  if (!title) {
    showMessage(els.formMessage, "Title is required.");
    return;
  }
  try {
    await api.createIssue(state.projectKey, { title, description: els.form.elements.description.value });
    els.form.reset();
    await loadIssues();
  } catch (err) {
    showMessage(els.formMessage, err.message);
  }
});

function init() {
  state.projectKey = readProjectFromUrl();
  els.user.value = getUserId();
  syncControls();
  loadHeader();
  loadIssues();
}

init();
