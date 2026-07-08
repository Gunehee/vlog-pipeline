"""Stage 4 — caption (local): SRT + styled ASS burn-in + both final exports.

Caption timestamps come from the edit stage's word-level whisper transcript
remapped through the cutlist, so they are synced to the edited cut by
construction (no second transcription pass, no drift).
"""
from __future__ import annotations

import json
from pathlib import Path

from . import StageError
from ..config import Config
from ..engine import captions, croptrack
from ..engine.render import burn_captions, render_short
from ..ffmpeg import extract_thumbnails, is_valid_media, stream_durations


def _gate(name: str, problems: list[str]):
    if problems:
        raise StageError(f"[{name}] validation failed: " + "; ".join(problems))


def _check_export(path: Path, label: str, notes: list[str]):
    ok, why = is_valid_media(path)
    if not ok:
        raise StageError(f"[{label}] invalid media: {why}")
    durs = stream_durations(path)
    v, a = durs.get("video"), durs.get("audio")
    if v is None or a is None or abs(v - a) > 0.15:
        raise StageError(f"[{label}] A/V desync or missing stream: {durs}")
    notes.append(f"{label}: {v:.2f}s, A/V delta {abs(v-a)*1000:.0f}ms, decodes clean")
    return v


def run(ctx: dict) -> tuple[list[str], list[str], float]:
    run_dir: Path = ctx["run_dir"]
    cfg: Config = ctx["cfg"]
    work = run_dir / "work"
    final = run_dir / "final"
    final.mkdir(exist_ok=True)
    notes: list[str] = []

    words_edited = json.loads((work / "words-edited.json").read_text())
    decisions = json.loads((run_dir / "edit-decisions.json").read_text())
    edited_dur = decisions["cutlist"]["edited_duration"]
    hl_window = tuple(decisions["highlight"]["window"])
    master = run_dir / "edited-169.mp4"

    # -- caption lines + SRT ---------------------------------------------------
    lines = captions.build_lines(words_edited)
    _gate("captions", captions.validate(lines, edited_dur))
    srt = run_dir / "captions.srt"
    captions.write_srt(lines, srt)
    ass_169 = work / "captions-169.ass"
    captions.write_ass(lines, ass_169, vertical=False)
    notes.append(f"{len(lines)} caption lines -> captions.srt + styled ASS")

    # -- burn 16:9 long-form -----------------------------------------------------
    long_out = final / "long-169.mp4"
    burn_captions(master, ass_169, long_out, cfg)
    _check_export(long_out, "long-169", notes)

    # -- smart-crop track over the highlight window ------------------------------
    track = croptrack.track_crop(master, hl_window)
    _gate("croptrack", croptrack.validate(track, hl_window))
    (work / "croptrack.json").write_text(json.dumps(
        {k: track[k] for k in ("width", "height", "fps", "crop_w", "stats")}
        | {"keyframes": track["keyframes"]}, indent=2))
    st = track["stats"]
    notes.append(
        f"crop tracking: {st['samples']} samples "
        f"({st['face_pct']}% face, {st['motion_pct']}% motion, {st['hold_pct']}% hold), "
        f"x range {st['x_range']}")
    cmds = work / "crop-sendcmd.txt"
    croptrack.write_sendcmd(track, cmds)

    # -- shorts captions (window-relative, 9:16 styling) --------------------------
    short_words = [w for w in words_edited
                   if hl_window[0] <= (w["start"] + w["end"]) / 2 <= hl_window[1]]
    short_lines = captions.build_lines(short_words, max_chars=18, max_words=4,
                                       max_dur=2.5)
    _gate("short-captions", captions.validate(short_lines, hl_window[1]))
    ass_916 = work / "captions-916.ass"
    captions.write_ass(short_lines, ass_916, vertical=True, offset=hl_window[0])

    # -- render 9:16 short ---------------------------------------------------------
    short_out = final / "short-916.mp4"
    render_short(master, hl_window, cmds, track["crop_w"], track["height"],
                 track["keyframes"][0][1], ass_916, short_out, cfg,
                 work / "filter-short.txt")
    vdur = _check_export(short_out, "short-916", notes)
    if abs(vdur - (hl_window[1] - hl_window[0])) > 0.5:
        raise StageError(f"[short-916] duration {vdur:.2f}s != window "
                         f"{hl_window[1]-hl_window[0]:.2f}s")

    # -- thumbnail frames for eyeball validation -----------------------------------
    thumbs = extract_thumbnails(long_out, run_dir / "thumbnails", 8)
    thumbs += extract_thumbnails(short_out, run_dir / "thumbnails" / "short", 4)
    notes.append(f"{len(thumbs)} thumbnail frames extracted")

    return ([str(long_out), str(short_out), str(srt)] + thumbs), notes, 0.0
