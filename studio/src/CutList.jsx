import React, { useEffect, useRef } from "react";
import { tc, cutColor } from "./util.js";

export default function CutList({ cuts, selection, onSelect, onToggle, onBatch,
                                  dispatch, duration }) {
  const listRef = useRef(null);
  const selected = cuts.find((c) => c.id === selection);

  useEffect(() => {
    if (!selection || !listRef.current) return;
    const el = listRef.current.querySelector(`[data-cut="${selection}"]`);
    el?.scrollIntoView({ block: "nearest" });
  }, [selection]);

  const counts = {};
  for (const c of cuts) counts[c.kind] = (counts[c.kind] || 0) + 1;

  return (
    <>
      <div className="panel-title">
        <span>Cuts <span className="muted">({cuts.length})</span></span>
        <span className="muted" style={{ fontSize: "var(--fs-xs)" }}>
          {cuts.filter((c) => c.status === "rejected").length} rejected
        </span>
      </div>
      <div className="batch-row">
        {counts.silence > 0 && (
          <button className="btn" style={{ height: 24, fontSize: "var(--fs-xs)" }}
                  onClick={() => onBatch(["silence", "mixed"], "accepted")}>
            accept silences
          </button>
        )}
        {counts.filler > 0 && (
          <>
            <button className="btn" style={{ height: 24, fontSize: "var(--fs-xs)" }}
                    data-testid="reject-fillers"
                    onClick={() => onBatch(["filler"], "rejected")}>
              reject all filler
            </button>
            <button className="btn" style={{ height: 24, fontSize: "var(--fs-xs)" }}
                    onClick={() => onBatch(["filler"], "accepted")}>
              accept all filler
            </button>
          </>
        )}
        <button className="btn" style={{ height: 24, fontSize: "var(--fs-xs)" }}
                onClick={() => onBatch(["silence", "filler", "mixed", "manual"], "accepted")}>
          accept all
        </button>
      </div>

      <div className="panel-scroll" ref={listRef} data-testid="cut-list">
        {cuts.length === 0 && (
          <div className="empty-state">
            <span className="glyph">✂</span>
            <div className="muted">No cuts — the engine found nothing to remove.<br />
              Drag on the timeline in add-cut mode (<kbd>c</kbd>) to cut manually.</div>
          </div>
        )}
        {cuts.map((c) => (
          <div key={c.id} data-cut={c.id}
               className={`cut-row ${c.id === selection ? "selected" : ""} ${c.status === "rejected" ? "rejected" : ""}`}
               onClick={() => onSelect(c.id)}>
            <span className="dot" style={{ background: cutColor(c.kind) }} />
            <span className="mono times">{tc(c.start)}</span>
            <span className="mono muted times">{(c.end - c.start).toFixed(2)}s</span>
            <span className="reason" title={c.reason}>{c.reason}</span>
            {c.unreviewed && <span className="new-badge">NEW</span>}
            <button className="btn quiet" style={{ height: 22, padding: "0 6px" }}
                    title={c.status === "accepted" ? "keep this content (reject cut)" : "remove this content (accept cut)"}
                    data-testid={`toggle-${c.id}`}
                    onClick={(e) => { e.stopPropagation(); onToggle(c.id); }}>
              {c.status === "accepted" ? "✂" : "↩"}
            </button>
          </div>
        ))}
      </div>

      {selected && (
        <div className="inspector-detail" data-testid="inspector">
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span className="dot" style={{ background: cutColor(selected.kind) }} />
            <strong style={{ flex: 1 }}>{selected.reason}</strong>
            <button className="btn" data-testid="inspector-toggle"
                    onClick={() => onToggle(selected.id)}>
              {selected.status === "accepted" ? "reject" : "accept"} <kbd>x</kbd>
            </button>
          </div>
          <div className="detail-grid">
            <span className="k">in</span>
            <span className="mono" data-testid="sel-start">{tc(selected.start)}</span>
            <span className="k">out</span>
            <span className="mono" data-testid="sel-end">{tc(selected.end)}</span>
            <span className="k">removes</span>
            <span className="mono">{(selected.end - selected.start).toFixed(3)}s</span>
            {(selected.start !== selected.engineStart || selected.end !== selected.engineEnd) && (
              <>
                <span className="k">engine</span>
                <span className="mono muted">
                  {tc(selected.engineStart)} – {tc(selected.engineEnd)}
                </span>
              </>
            )}
          </div>
          <div className="nudge-row">
            <span className="muted" style={{ fontSize: "var(--fs-xs)", width: 26 }}>in</span>
            <button className="btn" data-testid="nudge-start-left"
                    onClick={() => dispatch({ type: "NUDGE_CUT", id: selected.id, edge: "start", delta: -0.05 })}>−50ms</button>
            <button className="btn" data-testid="nudge-start-right"
                    onClick={() => dispatch({ type: "NUDGE_CUT", id: selected.id, edge: "start", delta: 0.05 })}>+50ms</button>
            <span className="muted" style={{ fontSize: "var(--fs-xs)", width: 26, marginLeft: 8 }}>out</span>
            <button className="btn"
                    onClick={() => dispatch({ type: "NUDGE_CUT", id: selected.id, edge: "end", delta: -0.05 })}>−50ms</button>
            <button className="btn" data-testid="nudge-end-right"
                    onClick={() => dispatch({ type: "NUDGE_CUT", id: selected.id, edge: "end", delta: 0.05 })}>+50ms</button>
          </div>
          {selected.id.startsWith("e") &&
            (selected.start !== selected.engineStart || selected.end !== selected.engineEnd) && (
            <div style={{ marginTop: 8 }}>
              <button className="btn quiet" onClick={() => dispatch({ type: "RESET_CUT", id: selected.id })}>
                reset to engine suggestion
              </button>
            </div>
          )}
        </div>
      )}
    </>
  );
}
