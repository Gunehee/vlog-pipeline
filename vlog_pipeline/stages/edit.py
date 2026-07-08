"""Stage 3 — edit (local, deterministic): the core engine coordinator.

Stage-gate pattern: each sub-module (transcribe, fillers, cutlist, render,
highlights) must pass its own validation before the coordinator proceeds.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import StageError
from ..config import Config
from ..engine import cutlist as cl
from ..engine import fillers, highlights, transcribe
from ..ffmpeg import extract_wav, is_valid_media, stream_durations
from ..engine.render import render_cut


def _gate(name: str, problems: list[str]):
    if problems:
        raise StageError(f"[{name}] validation failed: " + "; ".join(problems))


def run(ctx: dict) -> tuple[list[str], list[str], float]:
    run_dir: Path = ctx["run_dir"]
    cfg: Config = ctx["cfg"]
    footage = ctx["footage"]
    work = run_dir / "work"
    work.mkdir(exist_ok=True)
    notes = []

    ingest = json.loads((run_dir / "ingest-report.json").read_text())
    total_dur = ingest["duration_sec"]
    silences = ingest["silence_map"]["silences"]

    # -- transcribe (local whisper, word-level) ------------------------------
    src_wav = work / "source-16k.wav"
    extract_wav(footage, src_wav)
    words = transcribe.transcribe_words(src_wav, cfg.whisper_model)
    _gate("transcribe", transcribe.validate(words, total_dur))
    (work / "words-original.json").write_text(json.dumps(words, indent=2))
    notes.append(f"transcribed {len(words)} words ({cfg.whisper_model}, local)")

    # -- filler detection ----------------------------------------------------
    filler_cuts = fillers.detect_fillers(words, cfg.filler_pad)
    _gate("fillers", fillers.validate(filler_cuts, words))
    notes.append(f"{len(filler_cuts)} filler-word cuts")

    # -- cutlist with pacing rules -------------------------------------------
    cut = cl.build_cutlist(total_dur, silences, filler_cuts, cfg)
    _gate("cutlist", cl.validate(cut, cfg))
    notes.append(
        f"cutlist: {cut['original_duration']}s -> {cut['edited_duration']}s "
        f"({len(cut['kept'])} segments, {len(cut['removed'])} cuts, "
        f"{len(cut['restored'])} restored for pacing)")

    # -- render the 16:9 master edit -----------------------------------------
    master = run_dir / "edited-169.mp4"
    render_cut(footage, cut["kept"], master, cfg, work)
    ok, why = is_valid_media(master)
    if not ok:
        raise StageError(f"[render] edited master invalid: {why}")
    durs = stream_durations(master)
    v, a = durs.get("video"), durs.get("audio")
    if v is None or a is None:
        raise StageError(f"[render] missing stream durations: {durs}")
    if abs(v - a) > 0.15:
        raise StageError(f"[render] A/V desync: video={v:.3f}s audio={a:.3f}s")
    if abs(v - cut["edited_duration"]) > 0.5:
        raise StageError(
            f"[render] duration mismatch: rendered {v:.2f}s vs EDL {cut['edited_duration']}s")
    notes.append(f"master edit: {v:.2f}s, A/V delta {abs(v-a)*1000:.0f}ms")

    # -- remap words onto the edited timeline (captions sync by construction) -
    words_edited = cl.remap_words(words, cut["kept"])
    _gate("remap", transcribe.validate(words_edited, cut["edited_duration"]))
    (work / "words-edited.json").write_text(json.dumps(words_edited, indent=2))

    # -- highlight scoring on the edited cut -----------------------------------
    edited_wav = work / "edited-16k.wav"
    extract_wav(master, edited_wav)
    hl = highlights.score_highlights(edited_wav, words_edited, cfg)
    _gate("highlights", highlights.validate(hl, cfg))
    notes.append(
        f"highlight window {hl['window'][0]}-{hl['window'][1]}s "
        f"({hl['window_duration']}s)")

    # -- decisions + human-readable diff report --------------------------------
    decisions = {
        "config": cfg.to_dict(),
        "cutlist": cut,
        "filler_cuts": filler_cuts,
        "highlight": {k: hl[k] for k in ("window", "window_duration", "edited_duration")},
        "highlight_curve": hl["curve"],
    }
    dec_path = run_dir / "edit-decisions.json"
    dec_path.write_text(json.dumps(decisions, indent=2))
    report = _write_report(run_dir, cut, filler_cuts, hl, v, a)

    return [str(master), str(dec_path), str(report)], notes, 0.0


def _write_report(run_dir: Path, cut: dict, filler_cuts: list, hl: dict,
                  vdur: float, adur: float) -> Path:
    removed_total = sum(r["dur"] for r in cut["removed"])
    lines = [
        "# Edit report",
        "",
        f"| | |",
        f"|---|---|",
        f"| Original duration | {cut['original_duration']:.2f}s |",
        f"| Edited duration | {cut['edited_duration']:.2f}s |",
        f"| Removed | {removed_total:.2f}s across {len(cut['removed'])} cuts |",
        f"| Kept segments | {len(cut['kept'])} |",
        f"| Filler words cut | {len([r for r in cut['removed'] if r['kind'] != 'silence'])} |",
        f"| Cuts cancelled for pacing | {len(cut['restored'])} |",
        f"| Rendered A/V durations | video {vdur:.3f}s / audio {adur:.3f}s "
        f"(delta {abs(vdur-adur)*1000:.0f}ms) |",
        f"| Highlight window (edited timeline) | {hl['window'][0]}s - {hl['window'][1]}s |",
        "",
        "## What was cut and why",
        "",
        "| # | start | end | dur | reason |",
        "|---|-------|-----|-----|--------|",
    ]
    for i, r in enumerate(cut["removed"], 1):
        lines.append(f"| {i} | {r['start']:.2f}s | {r['end']:.2f}s | "
                     f"{r['dur']:.2f}s | {r['reason']} |")
    if cut["restored"]:
        lines += ["", "## Cuts cancelled to protect pacing", ""]
        for r in cut["restored"]:
            lines.append(f"- {r['start']:.2f}-{r['end']:.2f}s ({r['reason']}): "
                         f"{r['restored_because']}")
    lines += ["", "## Kept segments", "",
              "| # | source start | source end | dur |",
              "|---|--------------|------------|-----|"]
    for i, s in enumerate(cut["kept"], 1):
        lines.append(f"| {i} | {s['start']:.2f}s | {s['end']:.2f}s | "
                     f"{s['end']-s['start']:.2f}s |")
    out = run_dir / "edit-report.md"
    out.write_text("\n".join(lines) + "\n")
    return out
