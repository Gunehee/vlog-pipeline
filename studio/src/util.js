// Pure decision math — mirrors vlog_pipeline/review.py exactly.
// The E2E suite cross-checks client predictions against server numbers.

export function deriveCuts(cutlist, review) {
  const out = cutlist.removed.map((r, i) => {
    const id = `e${i}`;
    const ov = review.cuts[id] || {};
    return {
      id,
      kind: r.kind,
      reason: r.reason,
      engineStart: r.start,
      engineEnd: r.end,
      start: ov.start ?? r.start,
      end: ov.end ?? r.end,
      status: ov.status || "accepted",
      unreviewed: (review.unreviewed || []).includes(id),
    };
  });
  for (const m of review.manual_cuts) {
    out.push({
      id: m.id, kind: "manual", reason: "manual cut",
      engineStart: m.start, engineEnd: m.end,
      start: m.start, end: m.end, status: "accepted", unreviewed: false,
    });
  }
  out.sort((a, b) => a.start - b.start);
  return out;
}

export function effectiveRemovals(cuts, total) {
  const ivals = cuts
    .filter((c) => c.status === "accepted")
    .map((c) => ({
      start: Math.max(0, Math.min(c.start, total)),
      end: Math.max(0, Math.min(c.end, total)),
    }))
    .filter((r) => r.end - r.start > 0.005)
    .sort((a, b) => a.start - b.start);
  const merged = [];
  for (const r of ivals) {
    if (merged.length && r.start <= merged[merged.length - 1].end + 0.001) {
      merged[merged.length - 1].end = Math.max(merged[merged.length - 1].end, r.end);
    } else merged.push({ ...r });
  }
  return merged;
}

export function keptSegments(cuts, total) {
  const kept = [];
  let cursor = 0;
  for (const r of effectiveRemovals(cuts, total)) {
    if (r.start > cursor + 0.01) kept.push({ start: cursor, end: r.start });
    cursor = Math.max(cursor, r.end);
  }
  if (cursor < total - 0.01) kept.push({ start: cursor, end: total });
  return kept;
}

export function predictedDuration(cuts, total) {
  return keptSegments(cuts, total).reduce((s, k) => s + (k.end - k.start), 0);
}

export function mapOrigToEdit(t, kept) {
  let offset = 0;
  for (const seg of kept) {
    if (t >= seg.start && t <= seg.end) return offset + (t - seg.start);
    offset += seg.end - seg.start;
  }
  return null;
}

export function mapEditToOrig(t, kept) {
  let offset = 0;
  for (const seg of kept) {
    const d = seg.end - seg.start;
    if (t <= offset + d + 1e-9) return seg.start + (t - offset);
    offset += d;
  }
  return null;
}

// ---- formatting -----------------------------------------------------------
export function tc(t, ms = true) {
  if (t == null || Number.isNaN(t)) return "-:--.---";
  const sign = t < 0 ? "-" : "";
  t = Math.abs(t);
  const m = Math.floor(t / 60);
  const s = Math.floor(t % 60);
  if (!ms) return `${sign}${m}:${String(s).padStart(2, "0")}`;
  const msec = Math.round((t % 1) * 1000);
  return `${sign}${m}:${String(s).padStart(2, "0")}.${String(msec).padStart(3, "0")}`;
}

export const CUT_COLORS = {
  silence: "var(--cut-silence)",
  filler: "var(--cut-filler)",
  mixed: "var(--cut-mixed)",
  manual: "var(--cut-manual)",
};

export const CUT_HEX = {
  silence: "#3987e5",
  filler: "#199e70",
  mixed: "#c98500",
  manual: "#d55181",
};

export function cutColor(kind) {
  return CUT_COLORS[kind] || "var(--cut-mixed)";
}

export function debounce(fn, ms) {
  let t;
  const wrapped = (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...args), ms);
  };
  wrapped.flush = (...args) => { clearTimeout(t); fn(...args); };
  return wrapped;
}
