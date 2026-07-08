"""ffmpeg rendering: jump-cut assembly with click-free audio joins."""
from __future__ import annotations

from pathlib import Path

from ..config import Config
from ..ffmpeg import run


def render_cut(src: str | Path, kept: list[dict], dst: str | Path, cfg: Config,
               work_dir: str | Path, chunk: int = 90):
    """Re-assemble kept segments. Frame-accurate trim + 10 ms audio fades at
    every join so cuts never click. Chunks the filter graph for long EDLs."""
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    if len(kept) <= chunk:
        _render_chunk(src, kept, dst, cfg, work_dir / "filter-main.txt")
        return
    parts = []
    for i in range(0, len(kept), chunk):
        part = work_dir / f"part-{i//chunk:03d}.mp4"
        _render_chunk(src, kept[i:i + chunk], part, cfg,
                      work_dir / f"filter-{i//chunk:03d}.txt")
        parts.append(part)
    concat_list = work_dir / "concat.txt"
    concat_list.write_text("".join(f"file '{p.resolve()}'\n" for p in parts))
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
         "-c", "copy", "-movflags", "+faststart", str(dst)], "concat parts")


def _render_chunk(src, kept, dst, cfg: Config, script_path: Path):
    f = cfg.audio_fade
    lines, pairs = [], []
    for i, seg in enumerate(kept):
        a, b = seg["start"], seg["end"]
        dur = b - a
        lines.append(
            f"[0:v]trim=start={a:.3f}:end={b:.3f},setpts=PTS-STARTPTS[v{i}];")
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


def burn_captions(src: str | Path, ass_path: str | Path, dst: str | Path, cfg: Config):
    ass = str(Path(ass_path).resolve()).replace("'", r"\'")
    run([
        "ffmpeg", "-y", "-i", str(src),
        "-vf", f"subtitles=filename='{ass}'",
        "-c:v", "libx264", "-crf", str(cfg.crf), "-preset", cfg.preset,
        "-pix_fmt", "yuv420p", "-c:a", "copy",
        "-movflags", "+faststart", str(dst),
    ], "burn captions")


def render_short(src: str | Path, window: tuple[float, float], sendcmd_file: str | Path,
                 crop_w: int, crop_h: int, first_x: int, ass_path: str | Path,
                 dst: str | Path, cfg: Config, script_path: str | Path):
    """One-pass 9:16 export: trim highlight window from the edited master,
    apply the time-varying smart crop, scale to 1080x1920, burn shorts captions."""
    a, b = window
    f = cfg.audio_fade
    dur = b - a
    cmds = str(Path(sendcmd_file).resolve()).replace("'", r"\'")
    ass = str(Path(ass_path).resolve()).replace("'", r"\'")
    script = (
        f"[0:v]trim=start={a:.3f}:end={b:.3f},setpts=PTS-STARTPTS,"
        f"sendcmd=f='{cmds}',crop={crop_w}:{crop_h}:{first_x}:0,"
        f"scale=1080:1920:flags=lanczos,setsar=1,"
        f"subtitles=filename='{ass}'[vout];\n"
        f"[0:a]atrim=start={a:.3f}:end={b:.3f},asetpts=PTS-STARTPTS,"
        f"afade=t=in:st=0:d={f},afade=t=out:st={max(0.0, dur - f):.3f}:d={f}[aout]"
    )
    Path(script_path).write_text(script)
    run([
        "ffmpeg", "-y", "-i", str(src),
        "-filter_complex_script", str(script_path),
        "-map", "[vout]", "-map", "[aout]",
        "-c:v", "libx264", "-crf", str(cfg.crf), "-preset", cfg.preset,
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", cfg.audio_bitrate, "-ar", "48000",
        "-movflags", "+faststart", str(dst),
    ], "render short")
