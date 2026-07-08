"""Cutlist assembly: merge silence + filler removals into a paced jump-cut EDL."""
from __future__ import annotations

from ..config import Config


def build_cutlist(total_dur: float, silences: list[dict], fillers: list[dict],
                  cfg: Config) -> dict:
    """Compose removals into kept segments with pacing rules applied.

    Returns {'kept': [...], 'removed': [...], 'restored': [...],
             'original_duration': D, 'edited_duration': d}
    """
    removals: list[dict] = []

    for s in silences:
        start, end = s["start"], s["end"] if s["end"] is not None else total_dur
        # keep breathing room, except at the very edges of the footage.
        # Edge cuts snap to the true clip boundary: silencedetect's timestamps
        # can sit a few ms inside the container duration (codec padding), and
        # a sub-perceptual leftover fragment must not survive as "footage".
        a = 0.0 if start < 0.05 else start + cfg.keep_pad
        b = total_dur if end > total_dur - 0.05 else end - cfg.keep_pad
        if b - a >= cfg.min_cut:
            removals.append({"start": round(a, 3), "end": round(b, 3),
                             "reason": f"silence ({s['dur'] if s['dur'] else 'trailing'}s dead air)",
                             "kind": "silence"})

    for f in fillers:
        removals.append({"start": f["start"], "end": min(f["end"], total_dur),
                         "reason": f["why"], "kind": "filler"})

    removals.sort(key=lambda r: r["start"])

    # union of overlapping removals
    merged: list[dict] = []
    for r in removals:
        if merged and r["start"] <= merged[-1]["end"] + 0.001:
            last = merged[-1]
            last["end"] = max(last["end"], r["end"])
            if r["reason"] not in last["reason"]:
                last["reason"] += " + " + r["reason"]
                last["kind"] = "mixed"
        else:
            merged.append(dict(r))

    # pacing: cancel removals that would strand a too-short kept segment
    restored: list[dict] = []
    changed = True
    while changed:
        changed = False
        kept = _complement(merged, total_dur)
        for seg in kept:
            if seg["end"] - seg["start"] >= cfg.min_segment:
                continue
            neighbors = [r for r in merged
                         if abs(r["end"] - seg["start"]) < 0.01
                         or abs(r["start"] - seg["end"]) < 0.01]
            if not neighbors:
                continue
            at_edge = seg["start"] < 0.01 or seg["end"] > total_dur - 0.01
            if at_edge:
                # a too-short fragment at the clip boundary is dead-air fringe:
                # absorb it into the adjacent cut for a clean in/out point
                # (restoring the cut would resurrect the whole edge silence)
                victim = neighbors[0]
                victim["start"] = min(victim["start"], seg["start"])
                victim["end"] = max(victim["end"], seg["end"])
                if "absorbed edge fragment" not in victim["reason"]:
                    victim["reason"] += " + absorbed edge fragment"
            else:
                # mid-clip: prefer restoring silence over restoring a filler word
                neighbors.sort(key=lambda r: (r["kind"] == "filler",
                                              r["end"] - r["start"]))
                victim = neighbors[0]
                merged.remove(victim)
                victim["restored_because"] = (
                    f"kept segment {seg['start']:.2f}-{seg['end']:.2f}s would be "
                    f"{seg['end']-seg['start']:.2f}s < min {cfg.min_segment}s")
                restored.append(victim)
            changed = True
            break

    kept = _complement(merged, total_dur)
    kept = [s for s in kept if s["end"] - s["start"] > 0.01]
    for r in merged:
        r["dur"] = round(r["end"] - r["start"], 3)

    return {
        "original_duration": round(total_dur, 3),
        "edited_duration": round(sum(s["end"] - s["start"] for s in kept), 3),
        "kept": kept,
        "removed": merged,
        "restored": restored,
    }


def _complement(removals: list[dict], total: float) -> list[dict]:
    kept, cursor = [], 0.0
    for r in sorted(removals, key=lambda x: x["start"]):
        if r["start"] > cursor:
            kept.append({"start": round(cursor, 3), "end": round(r["start"], 3)})
        cursor = max(cursor, r["end"])
    if cursor < total:
        kept.append({"start": round(cursor, 3), "end": round(total, 3)})
    return kept


def map_time(t: float, kept: list[dict]) -> float | None:
    """Original-timeline t -> edited-timeline t, or None if t was cut."""
    offset = 0.0
    for seg in kept:
        if seg["start"] <= t <= seg["end"]:
            return round(offset + (t - seg["start"]), 3)
        offset += seg["end"] - seg["start"]
    return None


def remap_words(words: list[dict], kept: list[dict]) -> list[dict]:
    """Project word timestamps onto the edited timeline; drop cut words."""
    out = []
    for w in words:
        mid = (w["start"] + w["end"]) / 2
        seg = next((s for s in kept if s["start"] <= mid <= s["end"]), None)
        if seg is None:
            continue
        a = max(w["start"], seg["start"])
        b = min(w["end"], seg["end"])
        na, nb = map_time(a, kept), map_time(b, kept)
        if na is None or nb is None or nb <= na:
            continue
        out.append({**w, "start": na, "end": nb})
    return out


def validate(cut: dict, cfg: Config) -> list[str]:
    problems = []
    kept = cut["kept"]
    if not kept:
        problems.append("cutlist kept nothing")
        return problems
    if cut["edited_duration"] < 10.0:
        problems.append(f"edited duration {cut['edited_duration']}s < 10s — over-cutting")
    if cut["edited_duration"] < 0.25 * cut["original_duration"]:
        problems.append("cut removed more than 75% of footage — thresholds look wrong")
    prev_end = -1.0
    for s in kept:
        if s["start"] < prev_end:
            problems.append(f"overlapping kept segments near {s['start']}s")
        if s["end"] - s["start"] < cfg.min_segment - 0.05:
            problems.append(
                f"kept segment {s['start']}-{s['end']}s violates min_segment")
        prev_end = s["end"]
    return problems
