import React, { useEffect, useRef, useState, useCallback } from "react";
import { CUT_HEX, tc } from "./util.js";

const RULER_H = 20;
const WAVE_H = 62;
const TRACK_H = 30;
const PAD = 8;
const HEIGHT = RULER_H + WAVE_H + TRACK_H + PAD * 2 + 6;
const HANDLE_PX = 6;

const INK1 = "#f2f2f4", INK3 = "#6c6c79", BG0 = "#101013", BG2 = "#1d1d23",
  BORDER = "#2c2c35", ACCENT = "#9085e9", WAVE = "#4a4a56", WAVE_CUT = "#33333d",
  PACING = "#008300", WARN = "#fab219";

export default function Timeline({
  duration, waveform, cuts, restored, playhead, selection, punchIn, kept,
  addMode, onSeek, onSelect, onSetBounds, onAddManual, onExitAddMode,
}) {
  const canvasRef = useRef(null);
  const wrapRef = useRef(null);
  const [view, setView] = useState({ t0: 0, t1: null }); // null = full
  const dragRef = useRef(null);
  const [drag, setDrag] = useState(null); // live drag visual state
  const [hoverT, setHoverT] = useState(null);

  const t0 = view.t0, t1 = view.t1 ?? duration;

  const xOf = useCallback(
    (t, w) => ((t - t0) / (t1 - t0)) * w,
    [t0, t1]);
  const tOf = useCallback(
    (x, w) => t0 + (x / w) * (t1 - t0),
    [t0, t1]);

  // ---- drawing -------------------------------------------------------------
  useEffect(() => {
    const canvas = canvasRef.current;
    const wrap = wrapRef.current;
    if (!canvas || !wrap) return;
    const w = wrap.clientWidth;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = w * dpr;
    canvas.height = HEIGHT * dpr;
    canvas.style.height = `${HEIGHT}px`;
    const g = canvas.getContext("2d");
    g.scale(dpr, dpr);

    g.fillStyle = BG0;
    g.fillRect(0, 0, w, HEIGHT);

    const waveTop = RULER_H + PAD;
    const trackTop = waveTop + WAVE_H + 6;

    // ruler
    const span = t1 - t0;
    const step = niceStep(span, w);
    g.font = "10px ui-monospace, Menlo, monospace";
    g.textBaseline = "top";
    for (let t = Math.ceil(t0 / step) * step; t <= t1; t += step) {
      const x = xOf(t, w);
      g.fillStyle = BORDER;
      g.fillRect(x, RULER_H - 6, 1, 6);
      g.fillStyle = INK3;
      g.fillText(tc(t, false), x + 3, 3);
    }
    g.fillStyle = BORDER;
    g.fillRect(0, RULER_H, w, 1);

    // waveform (dimmed inside accepted cuts)
    if (waveform) {
      const { peaks, bins } = waveform;
      const mid = waveTop + WAVE_H / 2;
      const acc = drawableCuts(cuts, drag).filter((c) => c.status === "accepted");
      for (let px = 0; px < w; px += 1) {
        const t = tOf(px, w);
        if (t < 0 || t > duration) continue;
        const bin = Math.min(bins - 1, Math.floor((t / duration) * bins));
        const amp = peaks[bin] * (WAVE_H / 2 - 3);
        const inCut = acc.some((c) => t >= c.start && t <= c.end);
        g.fillStyle = inCut ? WAVE_CUT : WAVE;
        g.fillRect(px, mid - amp, 1, Math.max(1, amp * 2));
      }
    }

    // kept-segment punch-in badges (alternate segments zoom when enabled)
    if (punchIn && kept) {
      g.font = "9px ui-monospace, Menlo, monospace";
      kept.forEach((seg, i) => {
        if (i % 2 !== 1) return;
        const x = xOf(seg.start, w), x2 = xOf(seg.end, w);
        if (x2 < 0 || x > w || x2 - x < 18) return;
        g.fillStyle = "rgba(144,133,233,0.16)";
        g.fillRect(x, waveTop, x2 - x, 10);
        g.fillStyle = ACCENT;
        g.fillText("⤢ 108%", x + 3, waveTop + 1);
      });
    }

    // cut regions
    for (const c of drawableCuts(cuts, drag)) {
      const x = xOf(c.start, w), x2 = xOf(c.end, w);
      if (x2 < 0 || x > w) continue;
      const cw = Math.max(2, x2 - x);
      const hex = CUT_HEX[c.kind] || CUT_HEX.mixed;
      const accepted = c.status === "accepted";

      // tint over waveform
      g.fillStyle = hexA(hex, accepted ? 0.20 : 0.06);
      g.fillRect(x, waveTop, cw, WAVE_H);

      // cut track block
      g.fillStyle = hexA(hex, accepted ? 0.55 : 0.14);
      g.fillRect(x, trackTop, cw, TRACK_H - 8);
      g.fillStyle = accepted ? hex : hexA(hex, 0.4);
      g.fillRect(x, trackTop, cw, 2);
      if (!accepted) {
        g.strokeStyle = hexA(hex, 0.5);
        g.beginPath();
        g.moveTo(x, trackTop + (TRACK_H - 8) / 2);
        g.lineTo(x + cw, trackTop + (TRACK_H - 8) / 2);
        g.stroke(); // strikethrough = rejected
      }
      if (c.unreviewed) {
        g.fillStyle = WARN;
        g.beginPath();
        g.arc(x + 4, trackTop + 6, 2.5, 0, Math.PI * 2);
        g.fill();
      }
      if (c.id === selection) {
        g.strokeStyle = ACCENT;
        g.lineWidth = 1.5;
        g.strokeRect(x - 0.75, trackTop - 2.5, cw + 1.5, TRACK_H - 3);
        g.lineWidth = 1;
        // boundary handles
        g.fillStyle = ACCENT;
        g.fillRect(x - 2, waveTop, 3, WAVE_H + TRACK_H - 2);
        g.fillRect(x2 - 1, waveTop, 3, WAVE_H + TRACK_H - 2);
      }
    }

    // pacing-guard restored regions: hatched info marks (engine kept these)
    for (const r of restored || []) {
      const x = xOf(r.start, w), x2 = xOf(r.end, w);
      if (x2 < 0 || x > w) continue;
      g.save();
      g.beginPath();
      g.rect(x, trackTop + TRACK_H - 8, x2 - x, 5);
      g.clip();
      g.strokeStyle = PACING;
      for (let hx = x - 6; hx < x2 + 6; hx += 5) {
        g.beginPath();
        g.moveTo(hx, trackTop + TRACK_H + 2);
        g.lineTo(hx + 6, trackTop + TRACK_H - 10);
        g.stroke();
      }
      g.restore();
    }

    // manual-cut range preview
    if (drag?.type === "add") {
      const a = Math.min(drag.a, drag.b), b = Math.max(drag.a, drag.b);
      const x = xOf(a, w), x2 = xOf(b, w);
      g.fillStyle = hexA(CUT_HEX.manual, 0.25);
      g.fillRect(x, waveTop, x2 - x, WAVE_H + TRACK_H);
      g.strokeStyle = CUT_HEX.manual;
      g.strokeRect(x + 0.5, waveTop + 0.5, x2 - x - 1, WAVE_H + TRACK_H - 1);
    }

    // add-mode hint bar
    if (addMode) {
      g.fillStyle = hexA(CUT_HEX.manual, 0.12);
      g.fillRect(0, RULER_H + 1, w, 2);
    }

    // playhead
    if (playhead != null && playhead >= t0 && playhead <= t1) {
      const x = xOf(playhead, w);
      g.fillStyle = INK1;
      g.fillRect(x - 0.5, RULER_H - 4, 1.5, HEIGHT - RULER_H);
      g.beginPath();
      g.moveTo(x - 4, RULER_H - 4);
      g.lineTo(x + 4, RULER_H - 4);
      g.lineTo(x, RULER_H + 3);
      g.fill();
    }

    // hover time tooltip (lightweight)
    if (hoverT != null && !drag) {
      const x = xOf(hoverT, w);
      g.fillStyle = BG2;
      const label = tc(hoverT);
      const tw = g.measureText(label).width + 10;
      const bx = Math.min(Math.max(x - tw / 2, 2), w - tw - 2);
      g.fillRect(bx, HEIGHT - 16, tw, 14);
      g.fillStyle = INK3;
      g.fillText(label, bx + 5, HEIGHT - 13);
    }
  });

  // ---- interactions ----------------------------------------------------------
  const hitTest = useCallback((x, y, w) => {
    const waveTop = RULER_H + PAD;
    const trackTop = waveTop + WAVE_H + 6;
    if (selection) {
      const c = cuts.find((k) => k.id === selection);
      if (c) {
        const hx1 = xOf(c.start, w), hx2 = xOf(c.end, w);
        if (y >= waveTop && Math.abs(x - hx1) <= HANDLE_PX) return { type: "handle", id: c.id, edge: "start" };
        if (y >= waveTop && Math.abs(x - hx2) <= HANDLE_PX) return { type: "handle", id: c.id, edge: "end" };
      }
    }
    if (y >= trackTop && y <= trackTop + TRACK_H) {
      const t = tOf(x, w);
      const hit = [...cuts].reverse().find((c) => t >= c.start && t <= c.end);
      if (hit) return { type: "cut", id: hit.id };
    }
    return { type: "scrub" };
  }, [cuts, selection, tOf, xOf]);

  const onPointerDown = (e) => {
    const w = wrapRef.current.clientWidth;
    const rect = canvasRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left, y = e.clientY - rect.top;
    const t = clamp(tOf(x, w), 0, duration);
    canvasRef.current.setPointerCapture(e.pointerId);

    if (addMode) {
      dragRef.current = { type: "add", a: t, b: t };
      setDrag(dragRef.current);
      return;
    }
    const hit = hitTest(x, y, w);
    if (hit.type === "handle") {
      const c = cuts.find((k) => k.id === hit.id);
      dragRef.current = { type: "handle", id: hit.id, edge: hit.edge,
                          start: c.start, end: c.end };
      setDrag(dragRef.current);
    } else if (hit.type === "cut") {
      onSelect(hit.id);
    } else {
      dragRef.current = { type: "scrub" };
      onSeek(t);
    }
  };

  const onPointerMove = (e) => {
    const w = wrapRef.current.clientWidth;
    const rect = canvasRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const t = clamp(tOf(x, w), 0, duration);
    setHoverT(t);
    const d = dragRef.current;
    if (!d) return;
    if (d.type === "scrub") onSeek(t);
    else if (d.type === "add") {
      d.b = t;
      setDrag({ ...d });
    } else if (d.type === "handle") {
      if (d.edge === "start") d.start = Math.min(t, d.end - 0.05);
      else d.end = Math.max(t, d.start + 0.05);
      setDrag({ ...d });
    }
  };

  const onPointerUp = () => {
    const d = dragRef.current;
    dragRef.current = null;
    setDrag(null);
    if (!d) return;
    if (d.type === "add") {
      onAddManual(Math.min(d.a, d.b), Math.max(d.a, d.b));
      onExitAddMode();
    } else if (d.type === "handle") {
      onSetBounds(d.id, d.start, d.end);
    }
  };

  const onDblClick = (e) => {
    const w = wrapRef.current.clientWidth;
    const rect = canvasRef.current.getBoundingClientRect();
    const hit = hitTest(e.clientX - rect.left, e.clientY - rect.top, w);
    if (hit.type === "cut") onSelect(hit.id, { toggle: true });
  };

  // wheel zoom/pan (non-passive to own the gesture)
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const onWheel = (e) => {
      e.preventDefault();
      const w = wrapRef.current.clientWidth;
      const rect = canvas.getBoundingClientRect();
      const span = t1 - t0;
      if (e.shiftKey || Math.abs(e.deltaX) > Math.abs(e.deltaY)) {
        const dt = ((e.deltaX || e.deltaY) / w) * span;
        const nt0 = clamp(t0 + dt, 0, Math.max(0, duration - span));
        setView({ t0: nt0, t1: nt0 + span });
      } else {
        const cursorT = t0 + ((e.clientX - rect.left) / w) * span;
        const factor = Math.exp(e.deltaY * 0.0015);
        const newSpan = clamp(span * factor, 1.5, duration);
        let nt0 = cursorT - ((cursorT - t0) / span) * newSpan;
        nt0 = clamp(nt0, 0, Math.max(0, duration - newSpan));
        setView(newSpan >= duration - 0.01 ? { t0: 0, t1: null } : { t0: nt0, t1: nt0 + newSpan });
      }
    };
    canvas.addEventListener("wheel", onWheel, { passive: false });
    return () => canvas.removeEventListener("wheel", onWheel);
  }, [t0, t1, duration]);

  return (
    <div ref={wrapRef} style={{ position: "relative" }}>
      <canvas
        ref={canvasRef}
        className="timeline-canvas"
        data-testid="timeline"
        style={{ cursor: addMode ? "copy" : drag?.type === "handle" ? "ew-resize" : "crosshair" }}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerLeave={() => setHoverT(null)}
        onDoubleClick={onDblClick}
      />
    </div>
  );
}

function drawableCuts(cuts, drag) {
  if (!drag || drag.type !== "handle") return cuts;
  return cuts.map((c) =>
    c.id === drag.id ? { ...c, start: drag.start, end: drag.end } : c);
}

function niceStep(span, w) {
  const target = span / (w / 90);
  for (const s of [0.5, 1, 2, 5, 10, 15, 30, 60, 120, 300])
    if (s >= target) return s;
  return 600;
}

function hexA(hex, a) {
  const r = parseInt(hex.slice(1, 3), 16), g = parseInt(hex.slice(3, 5), 16),
    b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r},${g},${b},${a})`;
}

function clamp(v, lo, hi) {
  return Math.min(Math.max(v, lo), hi);
}
