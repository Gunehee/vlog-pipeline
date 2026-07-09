// Thin API client. All endpoints are same-origin (fully offline).

async function req(path, opts = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail || detail;
    } catch { /* non-JSON error body */ }
    const err = new Error(detail);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

export const api = {
  listRuns: () => req("/api/runs"),
  getRun: (name) => req(`/api/runs/${encodeURIComponent(name)}`),
  saveReview: (name, review) =>
    req(`/api/runs/${encodeURIComponent(name)}/review`, {
      method: "PUT",
      body: JSON.stringify(review),
    }),
  resetReview: (name) =>
    req(`/api/runs/${encodeURIComponent(name)}/review/reset`, { method: "POST", body: "{}" }),
  waveform: (name) => req(`/api/runs/${encodeURIComponent(name)}/waveform`),
  reanalyze: (name, settings) =>
    req(`/api/runs/${encodeURIComponent(name)}/reanalyze`, {
      method: "POST",
      body: JSON.stringify(settings),
    }),
  exportRun: (name, body) =>
    req(`/api/runs/${encodeURIComponent(name)}/export`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  job: (id) => req(`/api/jobs/${id}`),
};

// Subscribe to a job's SSE stream. Returns an unsubscribe function.
export function watchJob(id, { onLog, onDone, onFail }) {
  const es = new EventSource(`/api/jobs/${id}/events`);
  es.onmessage = (ev) => {
    const data = JSON.parse(ev.data);
    if (data.type === "log") onLog?.(data.msg);
    else if (data.type === "done") { onDone?.(data.result); es.close(); }
    else if (data.type === "failed") { onFail?.(data.error); es.close(); }
  };
  es.onerror = () => { /* server gone; snapshot polling is the fallback */ };
  return () => es.close();
}
