"""Silence/dead-air detection via ffmpeg silencedetect."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path


def detect_silences(path: str | Path, noise_db: float, min_dur: float) -> list[dict]:
    """Return [{'start': s, 'end': e, 'dur': d}] silence intervals."""
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(path), "-vn", "-af",
         f"silencedetect=noise={noise_db}dB:d={min_dur}", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    starts = [float(m) for m in re.findall(r"silence_start: ([\d.]+)", proc.stderr)]
    ends = [float(m) for m in re.findall(r"silence_end: ([\d.]+)", proc.stderr)]
    # trailing silence may have a start with no end; that's fine, pair what we have
    silences = []
    for s, e in zip(starts, ends):
        if e > s:
            silences.append({"start": round(s, 3), "end": round(e, 3),
                             "dur": round(e - s, 3)})
    if len(starts) > len(ends):  # file ends inside silence
        silences.append({"start": round(starts[-1], 3), "end": None, "dur": None})
    return silences


def validate(silences: list[dict], total_dur: float) -> list[str]:
    problems = []
    for s in silences:
        if s["end"] is not None and not (0 <= s["start"] < s["end"] <= total_dur + 0.5):
            problems.append(f"silence interval out of bounds: {s}")
    covered = sum(s["dur"] or 0 for s in silences)
    if covered > total_dur:
        problems.append(f"silences cover {covered:.1f}s > footage {total_dur:.1f}s")
    return problems
