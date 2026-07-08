"""Thin ffmpeg/ffprobe wrappers used across stages."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path


class FFmpegError(RuntimeError):
    pass


def run(cmd: list[str], desc: str = "") -> subprocess.CompletedProcess:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise FFmpegError(
            f"{desc or cmd[0]} failed (rc={proc.returncode}):\n{proc.stderr[-2000:]}"
        )
    return proc


def ffprobe_json(path: str | Path) -> dict:
    proc = run([
        "ffprobe", "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", str(path),
    ], "ffprobe")
    return json.loads(proc.stdout)


def stream_durations(path: str | Path) -> dict[str, float]:
    """Return {'video': secs, 'audio': secs} decoded stream durations."""
    info = ffprobe_json(path)
    out: dict[str, float] = {}
    for s in info["streams"]:
        dur = s.get("duration")
        if dur is None and "tags" in s:
            dur = s["tags"].get("DURATION")
        if dur is not None:
            out[s["codec_type"]] = float(dur)
    if "duration" in info.get("format", {}):
        out.setdefault("container", float(info["format"]["duration"]))
    return out


def is_valid_media(path: str | Path) -> tuple[bool, str]:
    """Full-decode check: ffprobe metadata + ffmpeg null decode with no errors."""
    p = Path(path)
    if not p.exists() or p.stat().st_size == 0:
        return False, "missing or empty file"
    try:
        info = ffprobe_json(p)
    except FFmpegError as e:
        return False, f"ffprobe rejected file: {e}"
    if not info.get("streams"):
        return False, "no streams"
    proc = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(p), "-f", "null", "-"],
        capture_output=True, text=True,
    )
    if proc.returncode != 0 or proc.stderr.strip():
        return False, f"decode errors: {proc.stderr[:500]}"
    return True, "ok"


def extract_wav(src: str | Path, dst: str | Path, rate: int = 16000):
    """Mono 16 kHz wav, the format whisper and RMS analysis both want."""
    run([
        "ffmpeg", "-y", "-i", str(src), "-vn",
        "-ac", "1", "-ar", str(rate), "-c:a", "pcm_s16le", str(dst),
    ], "extract_wav")


def extract_thumbnails(src: str | Path, out_dir: str | Path, count: int = 8) -> list[str]:
    """Evenly spaced jpeg frames for eyeball validation."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    dur = stream_durations(src).get("video") or stream_durations(src)["container"]
    outs = []
    for i in range(count):
        t = dur * (i + 0.5) / count
        dst = out_dir / f"frame-{i+1:02d}-{t:06.1f}s.jpg"
        run(["ffmpeg", "-y", "-ss", f"{t:.3f}", "-i", str(src),
             "-frames:v", "1", "-q:v", "3", str(dst)], "thumbnail")
        outs.append(str(dst))
    return outs
