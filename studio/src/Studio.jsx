import React, { useEffect, useState } from "react";
import { api } from "./api.js";
import { tc } from "./util.js";

// Phase 1 shell: loads the run payload and proves the data plumbing.
// Timeline/player/editing arrive in later phases.
export default function Studio({ runName, onBack }) {
  const [run, setRun] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.getRun(runName).then(setRun).catch(setError);
  }, [runName]);

  return (
    <div className="frame">
      <div className="header">
        <button className="btn quiet" onClick={onBack}>‹ library</button>
        <span className="title">{runName}</span>
        {run && <span className="muted mono">{tc(run.duration, false)}</span>}
        <span className="spacer" />
      </div>
      <div className="studio-main">
        <div className="stage">
          {error && (
            <div className="error-state">
              <span className="glyph">⚠</span>
              <span className="headline">Couldn't open this run</span>
              <details><summary>details</summary>{String(error.message)}</details>
              <button className="btn" onClick={onBack}>Back to library</button>
            </div>
          )}
          {!error && !run && <div className="loading-state"><div className="spinner" /> loading run…</div>}
          {run && (
            <div className="empty-state">
              <div className="dim">
                {run.cuts.length} suggested cuts · predicted {tc(run.predicted_duration, false)}
              </div>
              <div className="muted">studio surface lands in the next phase</div>
            </div>
          )}
        </div>
      </div>
      <div className="statusbar"><span>{runName}</span></div>
    </div>
  );
}
