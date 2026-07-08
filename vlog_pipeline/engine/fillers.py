"""Filler-word detection on word-level whisper output."""
from __future__ import annotations

import re

from ..config import ALWAYS_FILLERS, CONTEXTUAL_FILLERS


def _norm(word: str) -> str:
    return re.sub(r"[^a-z']", "", word.lower())


def detect_fillers(words: list[dict], pad: float) -> list[dict]:
    """Return [{'start','end','word','why'}] intervals to cut.

    - unconditional fillers ("um", "uh", ...) are always cut
    - contextual fillers ("like", "so", ...) are cut only when whisper is
      unsure of them (low prob) or they are drawn out (slow), both hesitation
      signatures; this avoids butchering legitimate usage.
    """
    cuts = []
    for w in words:
        token = _norm(w["word"])
        if not token:
            continue
        dur = w["end"] - w["start"]
        why = None
        if token in ALWAYS_FILLERS:
            why = f"filler '{token}'"
        elif token in CONTEXTUAL_FILLERS and (w["prob"] < 0.45 or dur > 0.6):
            why = f"hesitation '{token}' (prob={w['prob']}, dur={dur:.2f}s)"
        if why:
            cuts.append({
                "start": round(max(0.0, w["start"] - pad), 3),
                "end": round(w["end"] + pad, 3),
                "word": token,
                "why": why,
            })
    return cuts


def validate(fillers: list[dict], words: list[dict]) -> list[str]:
    problems = []
    for f in fillers:
        if f["end"] <= f["start"]:
            problems.append(f"empty filler interval: {f}")
        if f["end"] - f["start"] > 2.5:
            problems.append(f"suspiciously long filler cut (> 2.5s): {f}")
    if words and len(fillers) > len(words) * 0.5:
        problems.append("more than half of all words flagged as filler — thresholds wrong")
    return problems
