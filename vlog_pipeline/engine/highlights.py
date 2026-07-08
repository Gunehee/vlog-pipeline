"""Highlight scoring: audio energy + speech rate on the edited timeline."""
from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

from ..config import Config

HOP = 0.5  # seconds per score sample


def _rms_curve(wav_path: str | Path) -> tuple[np.ndarray, float]:
    with wave.open(str(wav_path), "rb") as w:
        rate = w.getframerate()
        data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    data = data.astype(np.float32) / 32768.0
    hop = int(rate * HOP)
    n = max(1, len(data) // hop)
    rms = np.array([
        np.sqrt(np.mean(np.square(data[i * hop:(i + 1) * hop])) + 1e-12)
        for i in range(n)
    ])
    return rms, len(data) / rate


def _norm(x: np.ndarray) -> np.ndarray:
    lo, hi = np.percentile(x, 10), np.percentile(x, 90)
    if hi - lo < 1e-9:
        return np.zeros_like(x)
    return np.clip((x - lo) / (hi - lo), 0.0, 1.0)


def score_highlights(edited_wav: str | Path, words_edited: list[dict],
                     cfg: Config) -> dict:
    """Score the edited cut and choose the best short-form window."""
    rms, dur = _rms_curve(edited_wav)
    t = np.arange(len(rms)) * HOP

    # speech rate: words per second in a 4 s window centered on each hop
    rate = np.zeros(len(rms))
    starts = np.array([w["start"] for w in words_edited]) if words_edited else np.array([])
    for i, ti in enumerate(t):
        if len(starts):
            rate[i] = np.sum((starts >= ti - 2.0) & (starts < ti + 2.0)) / 4.0

    score = 0.6 * _norm(rms) + 0.4 * _norm(rate)

    win = min(max(cfg.short_target, cfg.short_min), cfg.short_max, dur)
    win_hops = max(1, int(win / HOP))
    if win_hops >= len(score):
        best_start = 0.0
    else:
        sums = np.convolve(score, np.ones(win_hops), mode="valid")
        best_start = float(np.argmax(sums)) * HOP

    start, end = best_start, min(best_start + win, dur)

    # snap to word boundaries so the short never opens/closes mid-word
    if words_edited:
        w_starts = [w["start"] for w in words_edited]
        w_ends = [w["end"] for w in words_edited]
        snap_s = min(w_starts, key=lambda x: abs(x - start))
        if abs(snap_s - start) < 1.5:
            start = max(0.0, snap_s - 0.15)
        snap_e = min(w_ends, key=lambda x: abs(x - end))
        if abs(snap_e - end) < 1.5 and snap_e - start >= cfg.short_min * 0.8:
            end = min(dur, snap_e + 0.25)

    end = min(end, start + cfg.short_max, dur)

    return {
        "window": [round(start, 3), round(end, 3)],
        "window_duration": round(end - start, 3),
        "edited_duration": round(dur, 3),
        "curve": [
            {"t": round(float(ti), 1), "energy": round(float(e), 3),
             "speech_rate": round(float(r), 2), "score": round(float(s), 3)}
            for ti, e, r, s in zip(t, _norm(rms), rate, score)
        ],
    }


def validate(hl: dict, cfg: Config) -> list[str]:
    problems = []
    s, e = hl["window"]
    if not (0 <= s < e <= hl["edited_duration"] + 0.05):
        problems.append(f"highlight window {s}-{e}s out of bounds")
    dur = e - s
    if hl["edited_duration"] >= cfg.short_min and dur < cfg.short_min * 0.7:
        problems.append(f"highlight window {dur:.1f}s too short")
    if dur > cfg.short_max + 0.5:
        problems.append(f"highlight window {dur:.1f}s exceeds shorts max")
    return problems
