"""Studio export: render final videos honoring the review-decision overlay.

Reuses the deterministic engine (render, captions, highlights, croptrack) —
zero LLM involvement. Writes the canonical final/ outputs and regenerates
report.html so the batch artifacts stay coherent.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import report
from . import review as rv
from .config import Config
from .engine import captions as caps
from .engine import croptrack, highlights
from .engine.cutlist import remap_words
from .engine.render import burn_captions, render_cut, render_short, loudnorm_two_pass
from .ffmpeg import extract_thumbnails, extract_wav, is_valid_media, stream_durations


class ExportError(RuntimeError):
    pass


def export_run(run_dir: Path, on_progress=lambda msg: None) -> dict:
    run_dir = Path(run_dir)
    state = json.loads((run_dir / "state.json").read_text())
    decisions = json.loads((run_dir / "edit-decisions.json").read_text())
    ingest = json.loads((run_dir / "ingest-report.json").read_text())
    review = rv.load_review(run_dir)
    cfg = Config(**{k: v for k, v in decisions.get("config", {}).items()
                    if k in Config().__dict__})
    footage = state["footage"]
    total = ingest["duration_sec"]
    work = run_dir / "work"
    final = run_dir / "final"
    work.mkdir(exist_ok=True)
    final.mkdir(exist_ok=True)
    opts = review.get("export", {})

    if not Path(footage).exists():
        raise ExportError(f"original footage not found: {footage}")

    kept = rv.effective_kept(decisions["cutlist"], review, total)
    if not kept:
        raise ExportError("decision state removes everything — nothing to export")
    fps = ingest.get("video", {}).get("fps")
    predicted = rv.predicted_duration(decisions["cutlist"], review, total, fps)
    on_progress(f"decision state: {len(kept)} kept segments, "
                f"predicted duration {predicted:.2f}s")

    # -- master edit ---------------------------------------------------------
    master = work / "studio-master.mp4"
    on_progress("rendering master edit (jump-cut assembly)...")
    render_cut(footage, kept, master, cfg, work,
               punch_in=bool(opts.get("punch_in", False)))
    ok, why = is_valid_media(master)
    if not ok:
        raise ExportError(f"master render invalid: {why}")
    durs = stream_durations(master)
    v, a = durs.get("video"), durs.get("audio")
    if v is None or a is None or abs(v - a) > 0.15:
        raise ExportError(f"A/V desync in master: {durs}")
    if abs(v - predicted) > 0.5:
        raise ExportError(f"master {v:.2f}s != predicted {predicted:.2f}s")
    on_progress(f"master: {v:.2f}s, A/V delta {abs(v - a) * 1000:.0f}ms")

    # -- captions (original-time anchored -> current edited timeline) ---------
    lines = review.get("captions") or rv.derive_caption_lines(
        run_dir, decisions["cutlist"])
    exp_lines = rv.captions_for_export(lines, kept)
    preset = review.get("caption_preset", "clean")
    on_progress(f"burning {len(exp_lines)} caption lines (preset: {preset})...")
    overlays = caps.render_caption_pngs(exp_lines, work / "studio-cap169",
                                        vertical=False, preset=preset)
    long_out = final / "long-169.mp4"
    burn_captions(master, overlays, long_out, cfg, work / "filter-studio169.txt")

    # -- loudness normalization (two-pass, YouTube target) --------------------
    if opts.get("loudnorm", True):
        on_progress("loudness normalization pass (target -14 LUFS)...")
        stats_169 = loudnorm_two_pass(long_out, work / "studio-ln169.mp4")
        (work / "studio-ln169.mp4").replace(long_out)
        on_progress(f"long-form loudness: {stats_169['input_i']} -> "
                    f"{stats_169['target_i']} LUFS")
    _check(long_out, "long-169")

    # -- shorts: re-score highlight on the reviewed cut -----------------------
    on_progress("scoring highlight window on the reviewed cut...")
    words_path = work / "words-original.json"
    if words_path.exists():
        words = json.loads(words_path.read_text())
        words_edited = remap_words(words, kept)
    else:
        words_edited = [{"word": l["text"].split()[0] if l["text"] else "",
                         "start": l["start"], "end": l["end"], "prob": 1.0}
                        for l in exp_lines]
    edited_wav = work / "studio-edited-16k.wav"
    extract_wav(master, edited_wav)
    hl = highlights.score_highlights(edited_wav, words_edited, cfg)
    win = tuple(hl["window"])
    on_progress(f"highlight window {win[0]:.1f}-{win[1]:.1f}s; smart-crop tracking...")

    track = croptrack.track_crop(master, win)
    cmds = work / "studio-sendcmd.txt"
    croptrack.write_sendcmd(track, cmds)
    short_lines = [l for l in exp_lines
                   if win[0] <= (l["start"] + l["end"]) / 2 <= win[1]]
    short_overlays = caps.render_caption_pngs(
        short_lines, work / "studio-cap916", vertical=True, offset=win[0],
        preset=preset)
    short_out = final / "short-916.mp4"
    on_progress("rendering 9:16 export...")
    render_short(master, win, cmds, track["crop_w"], track["height"],
                 track["keyframes"][0][1], short_overlays, short_out, cfg,
                 work / "filter-studio916.txt")
    if opts.get("loudnorm", True):
        stats_916 = loudnorm_two_pass(short_out, work / "studio-ln916.mp4")
        (work / "studio-ln916.mp4").replace(short_out)
    _check(short_out, "short-916")

    # -- srt + thumbnails + report --------------------------------------------
    srt = run_dir / "captions.srt"
    caps.write_srt(exp_lines, srt)
    on_progress("extracting thumbnails + regenerating report.html...")
    extract_thumbnails(long_out, run_dir / "thumbnails", 8)
    extract_thumbnails(short_out, run_dir / "thumbnails" / "short", 4)
    report.generate(run_dir)

    out_durs = stream_durations(long_out)
    result = {
        "long": str(long_out), "short": str(short_out), "srt": str(srt),
        "report": str(run_dir / "report.html"),
        "predicted_duration": predicted,
        "exported_duration": round(out_durs.get("video", 0), 3),
        "highlight_window": list(win),
    }
    on_progress(f"done: {result['exported_duration']:.2f}s exported "
                f"(predicted {predicted:.2f}s)")
    return result


def _check(path: Path, label: str):
    ok, why = is_valid_media(path)
    if not ok:
        raise ExportError(f"{label} invalid: {why}")
    durs = stream_durations(path)
    v, a = durs.get("video"), durs.get("audio")
    if v is None or a is None or abs(v - a) > 0.15:
        raise ExportError(f"{label} A/V desync: {durs}")
