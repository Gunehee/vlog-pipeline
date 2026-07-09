import React, { useEffect, useState } from "react";
import { api, watchJob } from "./api.js";
import { tc } from "./util.js";

export default function ExportModal({ run, state, dispatch, predicted, onClose, flushSave }) {
  const [job, setJob] = useState(null);
  const opts = state.review.export || {};

  // decisions must be persisted before the server renders from them
  useEffect(() => { flushSave(); }, [flushSave]);

  const start = async () => {
    const resp = await api.exportRun(run.name, {
      export: { loudnorm: !!opts.loudnorm, punch_in: !!opts.punch_in },
      caption_preset: state.review.caption_preset || "clean",
    });
    const j = { id: resp.job, lines: [], status: "running", error: null, result: null };
    setJob({ ...j });
    watchJob(resp.job, {
      onLog: (msg) => setJob((prev) => ({ ...prev, lines: [...prev.lines, msg] })),
      onDone: (result) => setJob((prev) => ({ ...prev, status: "done", result })),
      onFail: (error) => setJob((prev) => ({ ...prev, status: "failed", error })),
    });
  };

  return (
    <div className="modal-scrim" onClick={job?.status === "running" ? undefined : onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()} data-testid="export-modal">
        <h2>Export</h2>

        {!job && (
          <>
            <div className="detail-grid" style={{ marginBottom: "var(--sp-4)" }}>
              <span className="k">predicted duration</span>
              <span className="mono" data-testid="export-predicted">{tc(predicted)}</span>
              <span className="k">formats</span>
              <span>16:9 long-form + 9:16 highlight short</span>
              <span className="k">captions</span>
              <span>{state.review.captions ? "edited" : "ASR"} · preset “{state.review.caption_preset || "clean"}”</span>
            </div>

            <label style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: "var(--sp-2)" }}>
              <input type="checkbox" checked={opts.loudnorm !== false}
                     data-testid="opt-loudnorm"
                     onChange={(e) => dispatch({ type: "SET_EXPORT_OPT", key: "loudnorm", value: e.target.checked })} />
              <span>Loudness normalize to −14 LUFS <span className="muted">(two-pass, YouTube target)</span></span>
            </label>
            <label style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: "var(--sp-2)" }}>
              <input type="checkbox" checked={!!opts.punch_in}
                     data-testid="opt-punchin"
                     onChange={(e) => dispatch({ type: "SET_EXPORT_OPT", key: "punch_in", value: e.target.checked })} />
              <span>Punch-in on alternate segments <span className="muted">(subtle 108% zoom masks jump cuts — badges shown on timeline)</span></span>
            </label>

            <div className="actions">
              <button className="btn" onClick={onClose}>cancel</button>
              <button className="btn primary" data-testid="start-export" onClick={start}>
                Render both formats
              </button>
            </div>
          </>
        )}

        {job && (
          <>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: "var(--sp-3)" }}>
              {job.status === "running" && <div className="spinner" />}
              {job.status === "done" && <span className="dot" style={{ background: "var(--good)", width: 10, height: 10 }} />}
              {job.status === "failed" && <span className="dot" style={{ background: "var(--crit)", width: 10, height: 10 }} />}
              <strong data-testid="export-status">
                {job.status === "running" ? "Rendering… (local ffmpeg, $0)"
                  : job.status === "done" ? "Export complete" : "Export failed"}
              </strong>
            </div>
            <div className="job-log" data-testid="export-log">{job.lines.join("\n")}{job.error ? `\n✗ ${job.error}` : ""}</div>

            {job.status === "done" && job.result && (
              <div className="detail-grid" style={{ marginTop: "var(--sp-3)" }}>
                <span className="k">16:9</span><span className="mono">{job.result.long}</span>
                <span className="k">9:16</span><span className="mono">{job.result.short}</span>
                <span className="k">duration</span>
                <span className="mono" data-testid="export-final-duration">
                  {tc(job.result.exported_duration)} (predicted {tc(job.result.predicted_duration)})
                </span>
                <span className="k">report</span>
                <span><a href={`/runs-static/${run.name}/report.html`} target="_blank"
                         rel="noreferrer" data-testid="report-link"
                         style={{ color: "var(--accent)" }} className="mono">
                  {job.result.report}</a></span>
              </div>
            )}

            <div className="actions">
              {job.status !== "running" && (
                <button className="btn" onClick={onClose}>close</button>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
