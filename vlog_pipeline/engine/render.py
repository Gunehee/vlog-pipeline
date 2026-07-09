"""ffmpeg rendering: jump-cut assembly with click-free audio joins."""
from __future__ import annotations

import json as _json
import re as _re
import subprocess as _sp
from pathlib import Path

from ..config import Config
from ..ffmpeg import ffprobe_json, run

PUNCH_ZOOM = 1.08  # punch-in alternation zoom factor


def render_cut(src: str | Path, kept: list[dict], dst: str | Path, cfg: Config,
               work_dir: str | Path, chunk: int = 90, punch_in: bool = False):
    """Re-assemble kept segments. Frame-accurate trim + 10 ms audio fades at
    every join so cuts never click. Chunks the filter graph for long EDLs.

    punch_in: alternate a subtle center zoom (100% <-> ~108%) between
    consecutive kept segments to visually mask jump cuts."""
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    dims = None
    if punch_in:
        info = ffprobe_json(src)
        v = next(s for s in info["streams"] if s["codec_type"] == "video")
        dims = (v["width"], v["height"])
    if len(kept) <= chunk:
        _render_chunk(src, kept, dst, cfg, work_dir / "filter-main.txt",
                      dims=dims, seg_offset=0)
        return
    parts = []
    for i in range(0, len(kept), chunk):
        part = work_dir / f"part-{i//chunk:03d}.mp4"
        _render_chunk(src, kept[i:i + chunk], part, cfg,
                      work_dir / f"filter-{i//chunk:03d}.txt",
                      dims=dims, seg_offset=i)
        parts.append(part)
    concat_list = work_dir / "concat.txt"
    concat_list.write_text("".join(f"file '{p.resolve()}'\n" for p in parts))
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
         "-c", "copy", "-movflags", "+faststart", str(dst)], "concat parts")


def _render_chunk(src, kept, dst, cfg: Config, script_path: Path,
                  dims=None, seg_offset: int = 0):
    f = cfg.audio_fade
    lines, pairs = [], []
    for i, seg in enumerate(kept):
        a, b = seg["start"], seg["end"]
        dur = b - a
        zoom = ""
        if dims is not None and (seg_offset + i) % 2 == 1:
            w, h = dims
            zoom = (f",crop=trunc(iw/{PUNCH_ZOOM}/2)*2:trunc(ih/{PUNCH_ZOOM}/2)*2,"
                    f"scale={w}:{h}:flags=lanczos")
        lines.append(
            f"[0:v]trim=start={a:.3f}:end={b:.3f},setpts=PTS-STARTPTS{zoom}[v{i}];")
        lines.append(
            f"[0:a]atrim=start={a:.3f}:end={b:.3f},asetpts=PTS-STARTPTS,"
            f"afade=t=in:st=0:d={f},afade=t=out:st={max(0.0, dur - f):.3f}:d={f}[a{i}];")
        pairs.append(f"[v{i}][a{i}]")
    lines.append(f"{''.join(pairs)}concat=n={len(kept)}:v=1:a=1[vout][aout]")
    script_path.write_text("\n".join(lines))
    run([
        "ffmpeg", "-y", "-i", str(src),
        "-filter_complex_script", str(script_path),
        "-map", "[vout]", "-map", "[aout]",
        "-c:v", "libx264", "-crf", str(cfg.crf), "-preset", cfg.preset,
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", cfg.audio_bitrate, "-ar", "48000",
        "-movflags", "+faststart", str(dst),
    ], "render cut")


def loudnorm_two_pass(src: str | Path, dst: str | Path, i: float = -14.0,
                      tp: float = -1.5, lra: float = 11.0) -> dict:
    """Two-pass EBU R128 loudness normalization to a YouTube-appropriate
    target. Video stream is copied; only audio is re-encoded."""
    spec = f"I={i}:TP={tp}:LRA={lra}"
    p1 = _sp.run(
        ["ffmpeg", "-hide_banner", "-i", str(src), "-vn",
         "-af", f"loudnorm={spec}:print_format=json", "-f", "null", "-"],
        capture_output=True, text=True)
    m = _re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", p1.stderr, _re.S)
    if not m:
        raise RuntimeError(f"loudnorm pass 1 gave no measurement: {p1.stderr[-800:]}")
    meas = _json.loads(m.group(0))
    filt = (f"loudnorm={spec}:measured_I={meas['input_i']}"
            f":measured_TP={meas['input_tp']}:measured_LRA={meas['input_lra']}"
            f":measured_thresh={meas['input_thresh']}"
            f":offset={meas['target_offset']}:linear=true")
    run(["ffmpeg", "-y", "-i", str(src), "-c:v", "copy",
         "-af", filt, "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
         "-movflags", "+faststart", str(dst)], "loudnorm pass 2")
    return {"input_i": meas["input_i"], "target_i": i}


def _overlay_chain(base: str, overlays: list[dict], first_input: int) -> tuple[str, str]:
    """Chain of timed caption overlays. Returns (filter_lines, out_label)."""
    lines, cur = [], base
    for j, ov in enumerate(overlays):
        nxt = f"ov{j}"
        lines.append(
            f"[{cur}][{first_input + j}:v]overlay={ov['x']}:{ov['y']}:"
            f"enable='between(t,{ov['start']:.3f},{ov['end']:.3f})'[{nxt}];")
        cur = nxt
    return "\n".join(lines), cur


def burn_captions(src: str | Path, overlays: list[dict], dst: str | Path,
                  cfg: Config, script_path: str | Path):
    """Burn PIL-rendered caption PNGs (ffmpeg here has no libass; overlay
    with enable=between gives the same burned-in result)."""
    chain, out = _overlay_chain("0:v", overlays, 1)
    Path(script_path).write_text(chain.rstrip(";") if overlays else "[0:v]null[capped]")
    out_label = out if overlays else "capped"
    cmd = ["ffmpeg", "-y", "-i", str(src)]
    for ov in overlays:
        cmd += ["-i", ov["file"]]
    cmd += [
        "-filter_complex_script", str(script_path),
        "-map", f"[{out_label}]", "-map", "0:a",
        "-c:v", "libx264", "-crf", str(cfg.crf), "-preset", cfg.preset,
        "-pix_fmt", "yuv420p", "-c:a", "copy",
        "-movflags", "+faststart", str(dst),
    ]
    run(cmd, "burn captions")


def render_short(src: str | Path, window: tuple[float, float], sendcmd_file: str | Path,
                 crop_w: int, crop_h: int, first_x: int, overlays: list[dict],
                 dst: str | Path, cfg: Config, script_path: str | Path):
    """One-pass 9:16 export: trim highlight window from the edited master,
    apply the time-varying smart crop, scale to 1080x1920, burn shorts captions."""
    a, b = window
    f = cfg.audio_fade
    dur = b - a
    cmds = str(Path(sendcmd_file).resolve()).replace("'", r"\'")
    base = (
        f"[0:v]trim=start={a:.3f}:end={b:.3f},setpts=PTS-STARTPTS,"
        f"sendcmd=f='{cmds}',crop={crop_w}:{crop_h}:{first_x}:0,"
        f"scale=1080:1920:flags=lanczos,setsar=1[scaled];\n"
    )
    chain, out = _overlay_chain("scaled", overlays, 1)
    audio = (
        f"\n[0:a]atrim=start={a:.3f}:end={b:.3f},asetpts=PTS-STARTPTS,"
        f"afade=t=in:st=0:d={f},afade=t=out:st={max(0.0, dur - f):.3f}:d={f}[aout]"
    )
    out_label = out if overlays else "scaled"
    Path(script_path).write_text(base + chain + audio)
    cmd = ["ffmpeg", "-y", "-i", str(src)]
    for ov in overlays:
        cmd += ["-i", ov["file"]]
    cmd += [
        "-filter_complex_script", str(script_path),
        "-map", f"[{out_label}]", "-map", "[aout]",
        "-c:v", "libx264", "-crf", str(cfg.crf), "-preset", cfg.preset,
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", cfg.audio_bitrate, "-ar", "48000",
        "-movflags", "+faststart", str(dst),
    ]
    run(cmd, "render short")
