"""Regression tests for the adaptive silence-threshold rescue (Fix B)."""
import sys
import wave
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vlog_pipeline.engine import silence

SR = 16000


def _write(path: Path, x: np.ndarray):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())


def _speech_like(n_sec: float, level_db: float, rng) -> np.ndarray:
    x = rng.standard_normal(int(n_sec * SR)).astype(np.float32)
    return x / np.sqrt(np.mean(x ** 2)) * 10 ** (level_db / 20)


def test_clean_floor_keeps_fixed_threshold(tmp_path):
    rng = np.random.default_rng(1)
    x = np.concatenate([
        _speech_like(3, -14, rng), np.zeros(SR * 2, np.float32),
        _speech_like(3, -14, rng)])
    wav = tmp_path / "clean.wav"
    _write(wav, x)
    thr, mode = silence.pick_threshold(wav, -35.0)
    assert thr == -35.0
    assert mode.startswith("fixed")


def test_raised_floor_engages_rescue(tmp_path):
    """Bed at -28dB, speech at -14dB: fixed -35 can never fire; the rescue
    threshold must land strictly between floor and speech level."""
    rng = np.random.default_rng(2)
    bed = _speech_like(10, -28, rng)
    speech = _speech_like(10, -14, rng)
    x = bed.copy()
    x[: 4 * SR] += speech[: 4 * SR]
    x[6 * SR:] += speech[: 4 * SR]  # 2s bed-only 'pause' in the middle
    wav = tmp_path / "bed.wav"
    _write(wav, x)
    thr, mode = silence.pick_threshold(wav, -35.0)
    assert "adaptive rescue" in mode
    # frame-peak floor of a -28dB-RMS bed is ~-17dB; threshold sits above it
    assert -17 < thr < -8, thr
    sils = silence.detect_silences(wav, thr, 0.45)
    assert any(4.0 - 0.4 <= s["start"] <= 4.4 and s["dur"] > 1.2 for s in sils), (
        f"planted bed-only pause not detected: {sils}")


def test_hopeless_snr_disables_rather_than_misfires(tmp_path):
    """Floor within 8dB of speech: rescue must decline (returns fixed) so
    silence removal is effectively off instead of cutting into speech."""
    rng = np.random.default_rng(3)
    x = _speech_like(6, -16, rng) + _speech_like(6, -20, rng)
    wav = tmp_path / "hopeless.wav"
    _write(wav, x)
    thr, mode = silence.pick_threshold(wav, -35.0)
    assert thr == -35.0
    assert "too close" in mode


def test_adaptive_disabled_flag(tmp_path):
    rng = np.random.default_rng(4)
    wav = tmp_path / "x.wav"
    _write(wav, _speech_like(3, -20, rng))
    thr, mode = silence.pick_threshold(wav, -35.0, adaptive=False)
    assert thr == -35.0 and "disabled" in mode
