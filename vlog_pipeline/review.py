"""Review-decision overlay: human decisions layered over the engine EDL.

The engine's edit-decisions.json is never mutated. Everything the user does in
the studio (accept/reject cuts, nudge boundaries, add manual cuts, edit
captions) lives in runs/<name>/review-state.json and is composed with the
engine suggestions at read time — so "reset to engine suggestions" always
works and re-analyze never clobbers human work.

All timestamps in the overlay are ORIGINAL-footage seconds. Captions are
anchored to original time too and mapped through the current cut list only at
preview/export time, so changing cuts can never desync them.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REVIEW_VERSION = 1


def default_review() -> dict:
    return {
        "version": REVIEW_VERSION,
        "cuts": {},          # cut_id -> {status: accepted|rejected, start?, end?}
        "manual_cuts": [],   # [{id, start, end}]
        "captions": None,    # None = derive from engine; else [{id,start,end,text}]
        "caption_preset": "clean",
        "unreviewed": [],    # cut ids new since last re-analyze
        "export": {"loudnorm": True, "punch_in": False},
    }


def load_review(run_dir: Path) -> dict:
    p = Path(run_dir) / "review-state.json"
    if p.exists():
        data = json.loads(p.read_text())
        base = default_review()
        base.update(data)
        return base
    return default_review()


def save_review(run_dir: Path, review: dict):
    (Path(run_dir) / "review-state.json").write_text(json.dumps(review, indent=2))


def cut_id(i: int) -> str:
    return f"e{i}"


# --------------------------------------------------------------- composition
def decisions_view(cutlist: dict, review: dict) -> list[dict]:
    """Per-cut view for the UI: engine cuts + overlay + manual cuts.
    Preserves per-cut identity (no merging)."""
    out = []
    for i, r in enumerate(cutlist["removed"]):
        cid = cut_id(i)
        ov = review["cuts"].get(cid, {})
        out.append({
            "id": cid,
            "kind": r["kind"],
            "reason": r["reason"],
            "engine_start": r["start"],
            "engine_end": r["end"],
            "start": float(ov.get("start", r["start"])),
            "end": float(ov.get("end", r["end"])),
            "status": ov.get("status", "accepted"),
            "unreviewed": cid in review.get("unreviewed", []),
        })
    for m in review["manual_cuts"]:
        out.append({
            "id": m["id"], "kind": "manual", "reason": "manual cut",
            "engine_start": m["start"], "engine_end": m["end"],
            "start": float(m["start"]), "end": float(m["end"]),
            "status": "accepted", "unreviewed": False,
        })
    out.sort(key=lambda c: c["start"])
    return out


def effective_removals(cutlist: dict, review: dict, total: float) -> list[dict]:
    """Accepted cuts (with nudges) merged into disjoint removal intervals."""
    ivals = []
    for c in decisions_view(cutlist, review):
        if c["status"] != "accepted":
            continue
        a = max(0.0, min(c["start"], total))
        b = max(0.0, min(c["end"], total))
        if b - a > 0.005:
            ivals.append({"start": a, "end": b})
    ivals.sort(key=lambda r: r["start"])
    merged: list[dict] = []
    for r in ivals:
        if merged and r["start"] <= merged[-1]["end"] + 0.001:
            merged[-1]["end"] = max(merged[-1]["end"], r["end"])
        else:
            merged.append(dict(r))
    return merged


def effective_kept(cutlist: dict, review: dict, total: float) -> list[dict]:
    kept, cursor = [], 0.0
    for r in effective_removals(cutlist, review, total):
        if r["start"] > cursor + 0.01:
            kept.append({"start": round(cursor, 3), "end": round(r["start"], 3)})
        cursor = max(cursor, r["end"])
    if cursor < total - 0.01:
        kept.append({"start": round(cursor, 3), "end": round(total, 3)})
    return kept


def predicted_duration(cutlist: dict, review: dict, total: float,
                       fps: float | None = None) -> float:
    """Predicted duration of the RENDER. With fps given, each kept segment is
    quantized to the frame grid the way ffmpeg's trim slices it (frames with
    start <= pts < end), which is what the exported file actually measures —
    the raw EDL sum runs ~2 frames/minute short of reality."""
    kept = effective_kept(cutlist, review, total)
    if fps:
        import math
        frames = sum(math.ceil(s["end"] * fps - 1e-9)
                     - math.ceil(s["start"] * fps - 1e-9) for s in kept)
        return round(frames / fps, 3)
    return round(sum(s["end"] - s["start"] for s in kept), 3)


def map_orig_to_edit(t: float, kept: list[dict]) -> float | None:
    offset = 0.0
    for seg in kept:
        if seg["start"] <= t <= seg["end"]:
            return round(offset + (t - seg["start"]), 3)
        offset += seg["end"] - seg["start"]
    return None


def map_edit_to_orig(t: float, kept: list[dict]) -> float | None:
    offset = 0.0
    for seg in kept:
        d = seg["end"] - seg["start"]
        if t <= offset + d + 1e-9:
            return round(seg["start"] + (t - offset), 3)
        offset += d
    return None


# ------------------------------------------------------------------ captions
def derive_caption_lines(run_dir: Path, engine_cutlist: dict) -> list[dict]:
    """Default caption lines anchored to ORIGINAL-footage time.

    Primary source: word-level whisper output (exact). Fallback for runs whose
    work/ dir is gone: parse captions.srt (edited timeline) and inverse-map
    through the ENGINE cut list that produced it.
    """
    words_path = Path(run_dir) / "work" / "words-original.json"
    if words_path.exists():
        from .engine.captions import build_lines
        words = json.loads(words_path.read_text())
        lines = build_lines(words)
    else:
        srt_path = Path(run_dir) / "captions.srt"
        if not srt_path.exists():
            return []
        engine_kept = engine_cutlist["kept"]
        lines = []
        for start, end, text in _parse_srt(srt_path.read_text()):
            a = map_edit_to_orig(start, engine_kept)
            b = map_edit_to_orig(end, engine_kept)
            if a is not None and b is not None and b > a:
                lines.append({"start": a, "end": b, "text": text})
    return [{"id": f"l{i}", "start": round(ln["start"], 3),
             "end": round(ln["end"], 3), "text": ln["text"]}
            for i, ln in enumerate(lines)]


def _parse_srt(text: str) -> list[tuple[float, float, str]]:
    def ts(s: str) -> float:
        h, m, rest = s.split(":")
        sec, ms = rest.split(",")
        return int(h) * 3600 + int(m) * 60 + int(sec) + int(ms) / 1000
    cues = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = [l for l in block.splitlines() if l.strip()]
        if len(lines) >= 3 and "-->" in lines[1]:
            a, b = [ts(x.strip()) for x in lines[1].split("-->")]
            cues.append((a, b, " ".join(lines[2:])))
    return cues


def captions_for_export(lines: list[dict], kept: list[dict]) -> list[dict]:
    """Project original-time caption lines onto the current edited timeline."""
    out = []
    for ln in lines:
        # clamp the line into visible (kept) time before mapping
        vis = [(max(ln["start"], s["start"]), min(ln["end"], s["end"]))
               for s in kept
               if s["start"] < ln["end"] and s["end"] > ln["start"]]
        if not vis:
            continue
        a = map_orig_to_edit(vis[0][0], kept)
        b = map_orig_to_edit(vis[-1][1], kept)
        if a is None or b is None or b - a < 0.15:
            continue
        out.append({"start": a, "end": b, "text": ln["text"]})
    return out


# ---------------------------------------------------------------- re-analyze
def match_decisions(old_removed: list[dict], review: dict,
                    new_removed: list[dict]) -> tuple[dict, dict]:
    """Carry decisions across a re-analyze by time-overlap matching.

    A new engine cut inherits the old cut's decision when they overlap by
    >= 50% of the shorter interval. Unmatched new cuts are marked unreviewed.
    Manual cuts and captions always persist (original-time anchored).
    """
    new_review = {**review, "cuts": {}, "unreviewed": []}
    stats = {"inherited": 0, "new_unreviewed": 0, "old_decisions": len(review["cuts"])}

    old = []
    for i, r in enumerate(old_removed):
        ov = review["cuts"].get(cut_id(i), {})
        old.append({
            "start": float(ov.get("start", r["start"])),
            "end": float(ov.get("end", r["end"])),
            "ov": ov,
        })

    for j, r in enumerate(new_removed):
        best, best_olap = None, 0.0
        for o in old:
            olap = min(o["end"], r["end"]) - max(o["start"], r["start"])
            if olap > best_olap:
                best, best_olap = o, olap
        shorter = min(r["end"] - r["start"],
                      (best["end"] - best["start"]) if best else 0.0)
        cid = cut_id(j)
        if best is not None and shorter > 0 and best_olap >= 0.5 * shorter:
            if best["ov"]:
                inherited = dict(best["ov"])
                # keep a nudge only if it still overlaps the new suggestion
                if "start" in inherited or "end" in inherited:
                    ns = float(inherited.get("start", r["start"]))
                    ne = float(inherited.get("end", r["end"]))
                    if min(ne, r["end"]) - max(ns, r["start"]) <= 0:
                        inherited.pop("start", None)
                        inherited.pop("end", None)
                new_review["cuts"][cid] = inherited
            stats["inherited"] += 1
        else:
            new_review["unreviewed"].append(cid)
            stats["new_unreviewed"] += 1
    return new_review, stats
