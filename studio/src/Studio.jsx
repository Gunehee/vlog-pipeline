import React, { useEffect, useReducer, useRef, useState, useCallback, useMemo } from "react";
import { api } from "./api.js";
import { reducer, initialState } from "./state.js";
import { tc, debounce } from "./util.js";
import Player from "./Player.jsx";
import Timeline from "./Timeline.jsx";
import CutList from "./CutList.jsx";
import CaptionEditor from "./CaptionEditor.jsx";
import SettingsDrawer from "./SettingsDrawer.jsx";
import ExportModal from "./ExportModal.jsx";
import ShortcutOverlay from "./ShortcutOverlay.jsx";

export default function Studio({ runName, onBack }) {
  const [state, dispatch] = useReducer(reducer, undefined, initialState);
  const [loadError, setLoadError] = useState(null);
  const [waveform, setWaveform] = useState(null);
  const [playhead, setPlayhead] = useState(0);
  const [seekTo, setSeekTo] = useState(null);
  const [mode, setMode] = useState("edited");
  const [tab, setTab] = useState("cuts");
  const [addMode, setAddMode] = useState(false);
  const [overlay, setOverlay] = useState(null); // 'shortcuts' | 'settings' | 'export'
  const videoRef = useRef(null);
  const stateRef = useRef(state);
  stateRef.current = state;

  useEffect(() => {
    api.getRun(runName).then((p) => dispatch({ type: "LOAD", payload: p }))
      .catch(setLoadError);
    api.waveform(runName).then(setWaveform).catch(() => setWaveform(null));
  }, [runName]);

  // ---- autosave (debounced) -------------------------------------------------
  const save = useMemo(() => debounce(async () => {
    const s = stateRef.current;
    if (!s.review) return;
    dispatch({ type: "SAVING" });
    try {
      const resp = await api.saveReview(runName, s.review);
      dispatch({ type: "SAVED" });
      if (Math.abs(resp.predicted_duration - s.predicted) > 0.005) {
        // client math must mirror the server exactly; loud if it ever drifts
        console.warn("predicted-duration mismatch", resp.predicted_duration, s.predicted);
      }
    } catch {
      dispatch({ type: "SAVE_ERROR" });
    }
  }, 700), [runName]);

  useEffect(() => {
    if (state.dirty) save();
  }, [state.review]); // eslint-disable-line react-hooks/exhaustive-deps

  // ---- selection helpers ------------------------------------------------------
  const toggleCut = useCallback((id) => {
    const c = stateRef.current.cuts.find((k) => k.id === id);
    if (!c) return;
    dispatch({ type: "SET_CUT_STATUS", id,
               status: c.status === "accepted" ? "rejected" : "accepted" });
  }, []);

  const select = useCallback((id, opts) => {
    dispatch({ type: "SELECT", id });
    if (opts?.toggle) toggleCut(id);
  }, [toggleCut]);

  const stepCut = useCallback((dir) => {
    const s = stateRef.current;
    if (!s.cuts.length) return;
    const i = s.cuts.findIndex((c) => c.id === s.selection);
    const ni = i < 0
      ? (dir > 0 ? 0 : s.cuts.length - 1)
      : Math.min(s.cuts.length - 1, Math.max(0, i + dir));
    const target = s.cuts[ni];
    dispatch({ type: "SELECT", id: target.id });
    setSeekTo(Math.max(0, target.start - 1.0)); // land 1s before the cut
    setMode("original");
  }, []);

  // ---- keyboard layer -----------------------------------------------------------
  useEffect(() => {
    const onKey = (e) => {
      const tag = e.target.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || e.target.isContentEditable) return;
      const v = videoRef.current;
      const s = stateRef.current;
      const mod = e.metaKey || e.ctrlKey;

      if (mod && e.key.toLowerCase() === "z") {
        e.preventDefault();
        dispatch({ type: e.shiftKey ? "REDO" : "UNDO" });
        return;
      }
      switch (e.key) {
        case " ":
          e.preventDefault();
          if (v) v.paused ? v.play() : v.pause();
          break;
        case "ArrowLeft":
        case "ArrowRight": {
          e.preventDefault();
          const dir = e.key === "ArrowRight" ? 1 : -1;
          if (e.altKey && s.selection) {
            dispatch({ type: "NUDGE_CUT", id: s.selection,
                       edge: e.shiftKey ? "end" : "start", delta: dir * 0.05 });
          } else if (v) {
            const step = e.shiftKey ? 5 : e.altKey ? 0.1 : 1;
            setSeekTo(Math.max(0, Math.min(v.currentTime + dir * step, s.run.duration)));
          }
          break;
        }
        case "x":
          if (s.selection) toggleCut(s.selection);
          break;
        case "n": stepCut(1); break;
        case "p": stepCut(-1); break;
        case "c": setAddMode((m) => !m); break;
        case "e": setMode((m) => (m === "edited" ? "original" : "edited")); break;
        case "?": setOverlay((o) => (o === "shortcuts" ? null : "shortcuts")); break;
        case "Escape":
          setOverlay(null);
          setAddMode(false);
          dispatch({ type: "SELECT", id: null });
          break;
        default:
          return;
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [stepCut, toggleCut]);

  // seekTo is one-shot: pass to player, then clear
  useEffect(() => {
    if (seekTo != null) {
      const id = setTimeout(() => setSeekTo(null), 60);
      return () => clearTimeout(id);
    }
  }, [seekTo]);

  if (loadError) {
    return (
      <div className="frame">
        <div className="header">
          <button className="btn quiet" onClick={onBack}>‹ library</button>
          <span className="title">{runName}</span>
        </div>
        <div className="error-state" style={{ flex: 1 }}>
          <span className="glyph">⚠</span>
          <span className="headline">Couldn't open this run</span>
          <details><summary>details</summary>{String(loadError.message)}</details>
          <button className="btn" onClick={onBack}>Back to library</button>
        </div>
      </div>
    );
  }
  if (!state.run) {
    return (
      <div className="frame">
        <div className="header"><button className="btn quiet" onClick={onBack}>‹ library</button>
          <span className="title">{runName}</span></div>
        <div className="loading-state" style={{ flex: 1 }}><div className="spinner" /> loading run…</div>
      </div>
    );
  }

  const { run, cuts, kept, predicted } = state;
  const removedTotal = run.duration - predicted;
  const saveLabel = { clean: "saved", saved: "saved", dirty: "unsaved…",
                      saving: "saving…", error: "save failed — retrying" }[state.saveState];

  return (
    <div className="frame">
      <div className="header">
        <button className="btn quiet" onClick={onBack}>‹ library</button>
        <span className="title">{run.name}</span>
        <span className="muted mono" data-testid="duration-math">
          {tc(run.duration, false)} → {tc(predicted, false)}
        </span>
        <span className="spacer" />
        <span className="save-dot" data-testid="save-state">
          <span className="dot" style={{
            background: state.saveState === "error" ? "var(--crit)"
              : state.dirty || state.saveState === "saving" ? "var(--warn)" : "var(--good)",
          }} />
          {saveLabel}
        </span>
        <button className="btn" onClick={() => setOverlay("settings")} data-testid="open-settings">
          settings
        </button>
        <button className="btn primary" onClick={() => setOverlay("export")} data-testid="open-export">
          Export
        </button>
      </div>

      <div className="studio-main" style={{ position: "relative" }}>
        <div className="stage">
          <Player
            src={run.media.original}
            cuts={cuts}
            kept={kept}
            duration={run.duration}
            mode={mode}
            onModeChange={setMode}
            playhead={seekTo}
            onTime={setPlayhead}
            videoRef={videoRef}
          />
        </div>
        <div className="inspector">
          <div className="tabs">
            <button className={`tab ${tab === "cuts" ? "active" : ""}`}
                    onClick={() => setTab("cuts")} data-testid="tab-cuts">Cuts</button>
            <button className={`tab ${tab === "captions" ? "active" : ""}`}
                    onClick={() => setTab("captions")} data-testid="tab-captions">Captions</button>
          </div>
          {tab === "cuts" ? (
            <CutList
              cuts={cuts}
              selection={state.selection}
              duration={run.duration}
              onSelect={(id) => { dispatch({ type: "SELECT", id }); }}
              onToggle={toggleCut}
              onBatch={(kinds, status) => dispatch({ type: "BATCH_STATUS", kinds, status })}
              dispatch={dispatch}
            />
          ) : (
            <CaptionEditor
              state={state}
              dispatch={dispatch}
              playhead={playhead}
              kept={kept}
              onSeek={(t) => { setMode("original"); setSeekTo(t); }}
            />
          )}
        </div>
        {overlay === "settings" && (
          <SettingsDrawer
            run={run}
            state={state}
            dispatch={dispatch}
            onClose={() => setOverlay(null)}
            onApplied={(payload) => dispatch({ type: "APPLY_SERVER", payload })}
          />
        )}
      </div>

      <div className="timeline-zone">
        <div className="timeline-tools">
          <div className="legend">
            <span><span className="dot" style={{ background: "var(--cut-silence)" }} />silence</span>
            <span><span className="dot" style={{ background: "var(--cut-filler)" }} />filler</span>
            <span><span className="dot" style={{ background: "var(--cut-mixed)" }} />mixed</span>
            <span><span className="dot" style={{ background: "var(--cut-manual)" }} />manual</span>
          </div>
          <span className="spacer" style={{ flex: 1 }} />
          <button className={`btn ${addMode ? "primary" : ""}`} data-testid="add-cut-mode"
                  onClick={() => setAddMode((m) => !m)}>
            {addMode ? "drag a range to cut…" : "add cut"} <kbd>c</kbd>
          </button>
          <button className="btn quiet" disabled={!state.undo.length}
                  data-testid="undo" onClick={() => dispatch({ type: "UNDO" })}>undo <kbd>⌘z</kbd></button>
          <button className="btn quiet" disabled={!state.redo.length}
                  data-testid="redo" onClick={() => dispatch({ type: "REDO" })}>redo</button>
          <span className="muted">scroll to zoom · shift+scroll to pan</span>
        </div>
        <Timeline
          duration={run.duration}
          waveform={waveform}
          cuts={cuts}
          restored={run.cutlist.restored}
          kept={kept}
          punchIn={!!state.review.export?.punch_in}
          playhead={playhead}
          selection={state.selection}
          addMode={addMode}
          onSeek={(t) => setSeekTo(t)}
          onSelect={select}
          onSetBounds={(id, start, end) => dispatch({ type: "SET_CUT_BOUNDS", id, start, end })}
          onAddManual={(a, b) => dispatch({ type: "ADD_MANUAL_CUT", start: a, end: b })}
          onExitAddMode={() => setAddMode(false)}
        />
      </div>

      <div className="statusbar">
        <span className="mono" data-testid="playhead-tc">{tc(playhead)}</span>
        <span data-testid="cut-math">
          removing {removedTotal.toFixed(1)}s across{" "}
          {cuts.filter((c) => c.status === "accepted").length} cuts
        </span>
        <span className="spacer" style={{ flex: 1 }} />
        <span>press <kbd>?</kbd> for shortcuts</span>
      </div>

      {overlay === "shortcuts" && <ShortcutOverlay onClose={() => setOverlay(null)} />}
      {overlay === "export" && (
        <ExportModal
          run={run}
          state={state}
          dispatch={dispatch}
          predicted={predicted}
          onClose={() => setOverlay(null)}
          flushSave={() => save.flush()}
        />
      )}
    </div>
  );
}
