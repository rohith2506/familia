// Thin JSON client. A 401 means the session lapsed — bounce to the login page.

async function request(method, path, body) {
  const res = await fetch(path, {
    method,
    headers: body === undefined ? {} : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  if (res.status === 401) {
    location.href = "/login";
    throw new Error("Signed out");
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const payload = await res.json();
      if (payload.detail) detail = typeof payload.detail === "string"
        ? payload.detail
        : JSON.stringify(payload.detail);
    } catch { /* non-JSON error body */ }
    throw new Error(detail);
  }
  return res.status === 204 ? null : res.json();
}

export const api = {
  review: () => request("GET", "/api/review"),
  dismiss: (key, days) => request("POST", "/api/review/dismiss", { key, days }),

  people: (includeArchived = false) =>
    request("GET", `/api/people?include_archived=${includeArchived}`),
  person: (id) => request("GET", `/api/people/${id}`),
  createPerson: (data) => request("POST", "/api/people", data),
  updatePerson: (id, data) => request("PATCH", `/api/people/${id}`, data),
  deletePerson: (id) => request("DELETE", `/api/people/${id}`),

  createThread: (personId, data) => request("POST", `/api/people/${personId}/threads`, data),
  updateThread: (id, data) => request("PATCH", `/api/threads/${id}`, data),
  deleteThread: (id) => request("DELETE", `/api/threads/${id}`),

  createEntry: (personId, data) => request("POST", `/api/people/${personId}/entries`, data),
  deleteEntry: (id) => request("DELETE", `/api/entries/${id}`),

  createEvent: (personId, data) => request("POST", `/api/people/${personId}/events`, data),
  updateEvent: (id, data) => request("PATCH", `/api/events/${id}`, data),
  deleteEvent: (id) => request("DELETE", `/api/events/${id}`),

  search: (q) => request("GET", `/api/search?q=${encodeURIComponent(q)}`),
  settings: () => request("GET", "/api/settings"),
  saveSettings: (data) => request("PATCH", "/api/settings", data),
};
