"""Local word-level transcription with faster-whisper (no API calls)."""
from __future__ import annotations

from pathlib import Path


def transcribe_words(wav_path: str | Path, model_name: str) -> list[dict]:
    """Return [{'word', 'start', 'end', 'prob'}] with word-level timestamps."""
    from faster_whisper import WhisperModel

    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    segments, _info = model.transcribe(
        str(wav_path), word_timestamps=True, vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 300},
    )
    words = []
    for seg in segments:
        for w in seg.words or []:
            words.append({
                "word": w.word.strip(),
                "start": round(w.start, 3),
                "end": round(w.end, 3),
                "prob": round(w.probability, 3),
            })
    return words


def validate(words: list[dict], total_dur: float) -> list[str]:
    problems = []
    if not words:
        problems.append("transcription produced zero words")
        return problems
    last = 0.0
    for w in words:
        if w["end"] < w["start"]:
            problems.append(f"word with negative duration: {w}")
        if w["start"] < last - 1.0:  # whisper words should be near-monotonic
            problems.append(f"non-monotonic word timestamp: {w}")
        last = max(last, w["start"])
    if words[-1]["end"] > total_dur + 2.0:
        problems.append(f"last word ends at {words[-1]['end']}s beyond footage {total_dur}s")
    return problems
