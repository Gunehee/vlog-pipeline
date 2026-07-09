import React, { useEffect, useState } from "react";
import { api } from "./api.js";
import { tc } from "./util.js";

export default function Library({ onOpen }) {
  const [runs, setRuns] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.listRuns().then(setRuns).catch((e) => setError(e));
  }, []);

  return (
    <div className="frame">
      <div className="header">
        <span className="title">vlog-pipeline studio</span>
        <span className="spacer" />
        <span className="badge"><span className="dot" style={{ background: "var(--good)" }} />local · $0</span>
      </div>
      <div style={{ flex: 1, overflowY: "auto" }}>
        <div className="library">
          <h1>Runs</h1>
          <p className="sub">Review the engine's proposed cuts, fix captions, export — all on this machine.</p>

          {error && (
            <div className="error-state">
              <span className="glyph">⚠</span>
              <span className="headline">Couldn't load runs</span>
              <details><summary>details</summary>{String(error.message)}</details>
              <button className="btn" onClick={() => { setError(null); api.listRuns().then(setRuns).catch(setError); }}>Retry</button>
            </div>
          )}

          {!error && runs === null && (
            <div className="loading-state"><div className="spinner" /> loading runs…</div>
          )}

          {!error && runs !== null && runs.length === 0 && (
            <div className="empty-state">
              <span className="glyph">🎬</span>
              <div>No runs yet.</div>
              <div className="muted">
                Process footage first: <span className="mono">vlog-pipeline run --footage clip.mp4 --topic "…"</span>
              </div>
            </div>
          )}

          {runs?.map((r) => (
            <button key={r.name} className="run-card" onClick={() => onOpen(r.name)}>
              <div className="name">{r.name}</div>
              <div className="topic">{r.topic}</div>
              <div className="meta">
                <span className="mono">{tc(r.original_duration, false)} → {tc(r.engine_duration, false)}</span>
                <span>{r.cut_count} suggested cuts</span>
                {r.reviewed && <span className="badge"><span className="dot" style={{ background: "var(--accent)" }} />reviewed</span>}
                {!r.footage_available && (
                  <span className="badge"><span className="dot" style={{ background: "var(--warn)" }} />footage missing</span>
                )}
              </div>
            </button>
          ))}
        </div>
      </div>
      <div className="statusbar">
        <span>vlog-pipeline studio</span>
        <span className="spacer" style={{ flex: 1 }} />
        <span>fully offline — no CDN, no API calls</span>
      </div>
    </div>
  );
}
