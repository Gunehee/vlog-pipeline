"""Stage 2 — ingest (local): ffprobe + silence map."""
from __future__ import annotations

import json
from pathlib import Path

from . import StageError
from ..config import Config
from ..engine import silence
from ..ffmpeg import ffprobe_json


def run(ctx: dict) -> tuple[list[str], list[str], float]:
    run_dir: Path = ctx["run_dir"]
    cfg: Config = ctx["cfg"]
    footage = ctx["footage"]

    info = ffprobe_json(footage)
    vstreams = [s for s in info["streams"] if s["codec_type"] == "video"]
    astreams = [s for s in info["streams"] if s["codec_type"] == "audio"]
    if not vstreams:
        raise StageError("footage has no video stream")
    if not astreams:
        raise StageError("footage has no audio stream — nothing to edit against")

    v = vstreams[0]
    duration = float(info["format"]["duration"])
    fps_n, fps_d = v.get("r_frame_rate", "30/1").split("/")
    threshold_db, threshold_mode = silence.pick_threshold(
        footage, cfg.silence_db, cfg.adaptive_silence)
    silences = silence.detect_silences(footage, threshold_db, cfg.min_silence)
    problems = silence.validate(silences, duration)
    if problems:
        raise StageError("silence map failed validation: " + "; ".join(problems))

    report = {
        "footage": str(footage),
        "duration_sec": round(duration, 3),
        "video": {
            "codec": v["codec_name"],
            "width": v["width"], "height": v["height"],
            "fps": round(float(fps_n) / float(fps_d), 3),
            "pix_fmt": v.get("pix_fmt"),
        },
        "audio_tracks": [
            {"codec": a["codec_name"], "channels": a.get("channels"),
             "sample_rate": a.get("sample_rate")} for a in astreams
        ],
        "silence_map": {
            "threshold_db": threshold_db,
            "threshold_mode": threshold_mode,
            "min_duration_sec": cfg.min_silence,
            "count": len(silences),
            "total_silence_sec": round(sum(s["dur"] or 0 for s in silences), 2),
            "silences": silences,
        },
    }
    out = run_dir / "ingest-report.json"
    out.write_text(json.dumps(report, indent=2))
    notes = [
        f"{duration:.1f}s, {v['width']}x{v['height']}@{report['video']['fps']}, "
        f"{len(astreams)} audio track(s)",
        f"{len(silences)} silences totaling {report['silence_map']['total_silence_sec']}s "
        f"at {threshold_db}dB ({threshold_mode})",
    ]
    return [str(out)], notes, 0.0
