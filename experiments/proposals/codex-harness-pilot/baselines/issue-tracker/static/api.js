// Thin wrapper around fetch: every call goes through request() so the
// X-User-Id header and the {"error": {...}} envelope are handled in one place.
const USER_KEY = "issueTracker.userId";

export function getUserId() {
  return localStorage.getItem(USER_KEY) || "1";
}

export function setUserId(id) {
  localStorage.setItem(USER_KEY, String(id));
}

export class ApiError extends Error {
  constructor(status, code, message) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

export async function request(method, path, body) {
  const headers = { "X-User-Id": getUserId() };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const response = await fetch(path, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = data.error || {};
    throw new ApiError(response.status, error.code || "unknown", error.message || response.statusText);
  }
  return data;
}

const issuesPath = (projectKey) => `/api/projects/${encodeURIComponent(projectKey)}/issues`;

export const api = {
  me: () => request("GET", "/api/me"),
  projects: () => request("GET", "/api/projects"),
  members: (projectKey) => request("GET", `/api/projects/${encodeURIComponent(projectKey)}/members`),
  listIssues(projectKey, { status, sort }) {
    const query = new URLSearchParams();
    if (status) query.set("status", status);
    if (sort) query.set("sort", sort);
    return request("GET", `${issuesPath(projectKey)}?${query}`);
  },
  getIssue: (projectKey, id) => request("GET", `${issuesPath(projectKey)}/${id}`),
  createIssue: (projectKey, fields) => request("POST", issuesPath(projectKey), fields),
  changeStatus: (projectKey, id, status) => request("PATCH", `${issuesPath(projectKey)}/${id}/status`, { status }),
};
