import React, { useEffect, useRef, useCallback, useState } from "react";
import { tc, mapOrigToEdit, effectiveRemovals } from "./util.js";

/*
 * Render-free preview: plays the ORIGINAL source and skips removed segments
 * in real time from the current decision state. The skip check runs on a
 * requestAnimationFrame loop (~60 Hz -> worst-case overshoot ~17 ms, well
 * inside the 50 ms boundary target; measured by the E2E suite).
 *
 * The active skip windows are exposed on the video element as
 * __skipLog (E2E instrumentation): [{at, from, to}] wall-clock skip events.
 */
export default function Player({ src, cuts, duration, mode, onModeChange,
                                 playhead, onTime, videoRef, kept }) {
  const rafRef = useRef(0);
  const removalsRef = useRef([]);
  const modeRef = useRef(mode);
  const [playing, setPlaying] = useState(false);
  const [rate, setRate] = useState(1);

  removalsRef.current = effectiveRemovals(cuts, duration);
  modeRef.current = mode;

  const tick = useCallback(() => {
    const v = videoRef.current;
    if (v && !v.paused && modeRef.current === "edited") {
      const t = v.currentTime;
      const r = removalsRef.current.find((x) => t >= x.start - 0.005 && t < x.end);
      if (r) {
        if (r.end >= duration - 0.05) {
          v.pause();
        } else {
          v.currentTime = r.end + 0.001;
          (v.__skipLog = v.__skipLog || []).push({
            at: performance.now(), from: t, to: r.end,
          });
        }
      }
    }
    if (v) onTime(v.currentTime);
    rafRef.current = requestAnimationFrame(tick);
  }, [duration, onTime, videoRef]);

  useEffect(() => {
    rafRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafRef.current);
  }, [tick]);

  useEffect(() => {
    const v = videoRef.current;
    if (v) v.playbackRate = rate;
  }, [rate, videoRef]);

  // external seeks (timeline clicks) — in edited mode, land outside removals
  useEffect(() => {
    const v = videoRef.current;
    if (!v || playhead == null) return;
    let t = playhead;
    if (modeRef.current === "edited") {
      const r = removalsRef.current.find((x) => t >= x.start && t < x.end);
      if (r) t = r.end + 0.001;
    }
    if (Math.abs(v.currentTime - t) > 0.02) v.currentTime = t;
  }, [playhead, videoRef]);

  const editedNow = mapOrigToEdit(
    Math.min(videoRef.current?.currentTime ?? 0, duration), kept);

  if (!src) {
    return (
      <div className="player-wrap">
        <div className="error-state">
          <span className="glyph">🎞</span>
          <span className="headline">Original footage isn't on this machine</span>
          <span className="muted">Preview and export need the source file; reports remain viewable.</span>
        </div>
      </div>
    );
  }

  return (
    <>
      <div className="player-wrap">
        <video
          ref={videoRef}
          src={src}
          data-testid="player"
          onPlay={() => setPlaying(true)}
          onPause={() => setPlaying(false)}
          onClick={() => (videoRef.current.paused ? videoRef.current.play() : videoRef.current.pause())}
        />
      </div>
      <div className="transport">
        <button
          className="btn"
          data-testid="play"
          onClick={() => (videoRef.current.paused ? videoRef.current.play() : videoRef.current.pause())}
        >
          {playing ? "❚❚" : "▶"} <kbd>space</kbd>
        </button>
        <span className="mono tc-live" data-testid="tc-orig">{tc(videoRef.current?.currentTime ?? 0)}</span>
        <span className="muted mono">
          {mode === "edited"
            ? `edited ${tc(editedNow ?? 0)}`
            : `source ${tc(duration, false)}`}
        </span>
        <span className="spacer" style={{ flex: 1 }} />
        <select className="input" value={rate} onChange={(e) => setRate(Number(e.target.value))}
                aria-label="playback speed" style={{ width: 64 }}>
          {[1, 1.25, 1.5, 2].map((r) => <option key={r} value={r}>{r}×</option>)}
        </select>
        <div className="toggle" role="group" aria-label="preview mode">
          <button className={mode === "edited" ? "on" : ""} data-testid="mode-edited"
                  onClick={() => onModeChange("edited")}>preview edited</button>
          <button className={mode === "original" ? "on" : ""} data-testid="mode-original"
                  onClick={() => onModeChange("original")}>play original</button>
        </div>
      </div>
    </>
  );
}
