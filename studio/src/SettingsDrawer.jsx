import React, { useState } from "react";
import { api, watchJob } from "./api.js";

/*
 * Re-analyze runs the LOCAL engine stages with new thresholds ($0).
 * Decisions are carried across by time-overlap matching server-side; when the
 * user has decisions at risk we say so explicitly before running.
 */
export default function SettingsDrawer({ run, state, dispatch, onClose, onApplied }) {
  const s = run.settings || {};
  const [silenceDb, setSilenceDb] = useState(s.silence_db ?? -35);
  const [minSilence, setMinSilence] = useState(s.min_silence ?? 0.45);
  const [minSegment, setMinSegment] = useState(s.min_segment ?? 0.6);
  const [fillers, setFillers] = useState("um, uh, uhm, umm, uhh, erm, hmm, mmm, ah, eh");
  const [confirming, setConfirming] = useState(false);
  const [job, setJob] = useState(null); // {id, lines, status, error, stats}

  const decisionCount = Object.keys(state.review.cuts).length
    + state.review.manual_cuts.length;

  const start = async () => {
    setConfirming(false);
    const resp = await api.reanalyze(run.name, {
      silence_db: Number(silenceDb),
      min_silence: Number(minSilence),
      min_segment: Number(minSegment),
      fillers: fillers.split(",").map((w) => w.trim()).filter(Boolean),
    });
    const j = { id: resp.job, lines: [], status: "running", error: null, stats: null };
    setJob({ ...j });
    watchJob(resp.job, {
      onLog: (msg) => setJob((prev) => ({ ...prev, lines: [...prev.lines, msg] })),
      onDone: (result) => {
        setJob((prev) => ({ ...prev, status: "done", stats: result.stats }));
        onApplied(result.run);
      },
      onFail: (error) => setJob((prev) => ({ ...prev, status: "failed", error })),
    });
  };

  return (
    <div className="drawer" data-testid="settings-drawer">
      <div className="panel-title">
        <span>Engine settings</span>
        <button className="btn quiet" onClick={onClose}>✕</button>
      </div>
      <div className="body">
        <div className="field">
          <label>Silence threshold — {silenceDb} dB</label>
          <input type="range" min={-60} max={-20} step={1} value={silenceDb}
                 data-testid="setting-silence-db"
                 onChange={(e) => setSilenceDb(e.target.value)} />
          <div className="hint">Quieter than this counts as dead air. Raised-floor footage
            auto-rescues regardless (peak-based).</div>
        </div>
        <div className="field">
          <label>Min silence — {Number(minSilence).toFixed(2)} s</label>
          <input type="range" min={0.2} max={2.0} step={0.05} value={minSilence}
                 onChange={(e) => setMinSilence(e.target.value)} />
          <div className="hint">Pauses shorter than this are never cut.</div>
        </div>
        <div className="field">
          <label>Min kept segment — {Number(minSegment).toFixed(2)} s</label>
          <input type="range" min={0.3} max={2.0} step={0.05} value={minSegment}
                 onChange={(e) => setMinSegment(e.target.value)} />
          <div className="hint">Pacing guard: never strand a clip shorter than this.</div>
        </div>
        <div className="field">
          <label>Filler words (always cut)</label>
          <textarea value={fillers} onChange={(e) => setFillers(e.target.value)}
                    data-testid="setting-fillers" />
          <div className="hint">Comma-separated. "like"/"so" stay contextual — only cut on
            hesitation signatures, never on confident use.</div>
        </div>

        {job && (
          <div className="field">
            <label>{job.status === "running" ? "Re-analyzing ($0, local)…"
              : job.status === "done" ? "Done" : "Failed"}</label>
            <div className="job-log" data-testid="reanalyze-log">
              {job.lines.join("\n")}
              {job.error ? `\n✗ ${job.error}` : ""}
              {job.stats
                ? `\n✓ ${job.stats.inherited} decisions carried over, `
                  + `${job.stats.new_unreviewed} new suggestions marked NEW`
                : ""}
            </div>
          </div>
        )}

        {confirming ? (
          <div className="field" style={{ border: "1px solid var(--warn)", borderRadius: "var(--r-md)", padding: "var(--sp-3)" }}>
            <label style={{ color: "var(--warn)" }}>You have {decisionCount} decision{decisionCount === 1 ? "" : "s"} on this run</label>
            <div className="hint" style={{ marginBottom: "var(--sp-2)" }}>
              Matching cuts keep your accept/reject/nudge choices. Cuts that no longer
              correspond get re-suggested and marked NEW — nothing is silently overridden,
              and manual cuts + caption edits always survive.
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              <button className="btn primary" data-testid="confirm-reanalyze" onClick={start}>Re-analyze</button>
              <button className="btn" onClick={() => setConfirming(false)}>Cancel</button>
            </div>
          </div>
        ) : (
          <button className="btn primary" style={{ width: "100%" }}
                  data-testid="reanalyze"
                  disabled={job?.status === "running"}
                  onClick={() => (decisionCount ? setConfirming(true) : start())}>
            Re-analyze with these settings ($0)
          </button>
        )}

        <div style={{ marginTop: "var(--sp-4)", borderTop: "1px solid var(--border-1)", paddingTop: "var(--sp-4)" }}>
          <button className="btn danger" style={{ width: "100%" }}
                  onClick={async () => {
                    if (!window.confirm("Discard ALL review decisions and caption edits for this run?")) return;
                    const resp = await api.resetReview(run.name);
                    onApplied(resp.run);
                    onClose();
                  }}>
            Reset everything to engine suggestions
          </button>
        </div>
      </div>
    </div>
  );
}
