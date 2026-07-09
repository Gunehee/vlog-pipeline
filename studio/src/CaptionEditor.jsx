import React, { useEffect, useRef, useState } from "react";
import { currentCaptions } from "./state.js";
import { tc, mapOrigToEdit } from "./util.js";

/*
 * Captions are anchored to ORIGINAL-footage time (see review.py), so cut
 * changes can never desync them. A line whose whole span falls inside
 * removed content is shown dimmed — it won't appear in the export.
 */
export default function CaptionEditor({ state, dispatch, playhead, kept, onSeek }) {
  const lines = currentCaptions(state);
  const [editing, setEditing] = useState(null); // line id
  const [draft, setDraft] = useState("");
  const listRef = useRef(null);
  const activeRef = useRef(null);

  const activeId = lines.find((l) => playhead >= l.start && playhead <= l.end)?.id;

  useEffect(() => {
    activeRef.current?.scrollIntoView({ block: "nearest" });
  }, [activeId]);

  const commit = (id) => {
    const line = lines.find((l) => l.id === id);
    if (line && draft.trim() && draft !== line.text) {
      dispatch({ type: "SET_CAPTION_TEXT", id, text: draft.trim() });
    }
    setEditing(null);
  };

  return (
    <>
      <div className="panel-title">
        <span>Captions <span className="muted">({lines.length})</span></span>
        {state.review.captions && (
          <button className="btn quiet" style={{ height: 22, fontSize: "var(--fs-xs)" }}
                  onClick={() => dispatch({ type: "RESET_CAPTIONS" })}
                  title="discard all caption edits">
            reset to ASR
          </button>
        )}
      </div>
      <div className="batch-row">
        <span className="muted" style={{ fontSize: "var(--fs-xs)" }}>
          click line to seek · double-click to edit · edits burn in at export
        </span>
      </div>
      <div className="panel-scroll" ref={listRef} data-testid="caption-list">
        {lines.length === 0 && (
          <div className="empty-state">
            <span className="glyph">💬</span>
            <div className="muted">No transcript available for this run.</div>
          </div>
        )}
        {lines.map((l, i) => {
          const visible = mapOrigToEdit((l.start + l.end) / 2, kept) !== null;
          return (
            <div key={l.id}
                 ref={l.id === activeId ? activeRef : null}
                 data-testid={`cap-${i}`}
                 className={`cap-row ${l.id === activeId ? "active" : ""} ${visible ? "" : "hidden-cap"}`}
                 title={visible ? "" : "entirely inside removed content — will not export"}
                 onClick={() => onSeek(l.start + 0.01)}
                 onDoubleClick={(e) => { e.stopPropagation(); setEditing(l.id); setDraft(l.text); }}>
              <span className="cap-tc mono">{tc(l.start, false)}</span>
              {editing === l.id ? (
                <input
                  className="cap-text-input"
                  data-testid={`cap-input-${i}`}
                  autoFocus
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  onBlur={() => commit(l.id)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") commit(l.id);
                    if (e.key === "Escape") setEditing(null);
                    e.stopPropagation();
                  }}
                  onClick={(e) => e.stopPropagation()}
                />
              ) : (
                <span className="cap-text">{l.text}</span>
              )}
              {editing !== l.id && (
                <span className="cap-actions" onClick={(e) => e.stopPropagation()}>
                  <button className="btn quiet" title="split this line in half"
                          data-testid={`cap-split-${i}`}
                          onClick={() => dispatch({ type: "SPLIT_CAPTION", id: l.id })}>split</button>
                  {i + 1 < lines.length && (
                    <button className="btn quiet" title="merge with the next line"
                            data-testid={`cap-merge-${i}`}
                            onClick={() => dispatch({ type: "MERGE_CAPTION", id: l.id })}>join</button>
                  )}
                </span>
              )}
            </div>
          );
        })}
      </div>
      <div className="inspector-detail">
        <div className="field" style={{ marginBottom: 0 }}>
          <label>Style preset (burned in at export)</label>
          <select className="input" style={{ width: "100%" }}
                  data-testid="caption-preset"
                  value={state.review.caption_preset || "clean"}
                  onChange={(e) => dispatch({ type: "SET_PRESET", preset: e.target.value })}>
            <option value="clean">Clean — outline + soft box</option>
            <option value="boxed">Boxed — solid backing box</option>
            <option value="large">Large — +22% type</option>
            <option value="high">High — raised further above 9:16 UI zone</option>
          </select>
          <div className="hint">9:16 presets keep captions clear of the Shorts progress bar and buttons.</div>
        </div>
      </div>
    </>
  );
}
