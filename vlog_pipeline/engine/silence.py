"""Silence/dead-air detection via ffmpeg silencedetect.

When footage has a raised noise floor (music bed, room tone, AC hum) the
fixed threshold can sit *below* the floor and never fire. `pick_threshold`
detects that case and rescues it with a floor-relative threshold; footage
whose floor is below the fixed threshold keeps the configured value, so
clean recordings behave exactly as before.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import numpy as np


def measure_levels(path: str | Path) -> tuple[float, float]:
    """(noise_floor_db, speech_db) from 50 ms frame-PEAK levels.

    Peak, not RMS, deliberately: silencedetect declares silence only while
    |sample| stays below the threshold, so a noise bed's crest factor
    (~10-12 dB above its RMS) is what the threshold must clear. floor = 2nd
    percentile of frame peaks (quietest sustained content), speech = 80th.
    """
    proc = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-vn", "-ac", "1",
         "-ar", "16000", "-f", "f32le", "-"],
        capture_output=True, check=True)
    x = np.abs(np.frombuffer(proc.stdout, dtype=np.float32))
    hop = 800  # 50 ms at 16 kHz
    n = max(1, len(x) // hop)
    peaks = np.array([x[i * hop:(i + 1) * hop].max() for i in range(n)])
    db = 20 * np.log10(peaks + 1e-9)
    return float(np.percentile(db, 2)), float(np.percentile(db, 80))


def pick_threshold(path: str | Path, fixed_db: float,
                   adaptive: bool = True) -> tuple[float, str]:
    """Return (threshold_db, mode_note). Rescue mode only: the adaptive
    threshold engages ONLY when the noise floor is at/above the fixed
    threshold (fixed would never fire); otherwise the fixed value is kept."""
    if not adaptive:
        return fixed_db, "fixed (adaptive disabled)"
    floor, speech = measure_levels(path)
    if floor < fixed_db - 1.0:
        return fixed_db, f"fixed (floor {floor:.1f}dB below threshold)"
    if speech - floor < 8.0:
        return fixed_db, (f"fixed (floor {floor:.1f}dB vs speech {speech:.1f}dB "
                          "too close to separate — raised-floor footage, "
                          "silence removal effectively disabled)")
    # midpoint of floor->speech in dB, capped 6dB under speech: measured on
    # fluctuating beds, recall/FP are flat across factors 0.45-0.6, so the
    # midpoint is well inside the safe plateau on both sides
    thr = min(floor + 0.5 * (speech - floor), speech - 6.0)
    thr = max(thr, floor + 3.0)
    return round(thr, 1), (f"adaptive rescue (floor {floor:.1f}dB, "
                           f"speech {speech:.1f}dB)")


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
