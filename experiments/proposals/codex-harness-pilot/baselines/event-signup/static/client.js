// All network calls go through send() so error bodies ({"detail", "code"})
// are turned into RequestError in one place.
export class RequestError extends Error {
  constructor(status, code, detail) {
    super(detail);
    this.status = status;
    this.code = code;
  }
}

async function send(method, path, { body, token } = {}) {
  const headers = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (token) headers["X-Registration-Token"] = token;
  let response;
  try {
    response = await fetch(path, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
  } catch (err) {
    throw new RequestError(0, "network_error", "Could not reach the server.");
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new RequestError(response.status, data.code || "unknown", data.detail || response.statusText);
  }
  return data;
}

export const client = {
  events: () => send("GET", "/api/events"),
  event: (slug) => send("GET", `/api/events/${encodeURIComponent(slug)}`),
  waitlist: (slug) => send("GET", `/api/events/${encodeURIComponent(slug)}/waitlist`),
  register: (slug, fields) => send("POST", `/api/events/${encodeURIComponent(slug)}/registrations`, { body: fields }),
  registration: (id, token) => send("GET", `/api/registrations/${id}`, { token }),
  cancel: (id, token) => send("POST", `/api/registrations/${id}/cancel`, { token }),
};
