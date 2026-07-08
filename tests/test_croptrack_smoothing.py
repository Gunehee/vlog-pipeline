"""Regression tests for croptrack smoothing (Fix C) — pure, no video needed."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vlog_pipeline.engine.croptrack import smooth_centers

W, CROP_W, SPS = 1920, 608, 6.0


def _t(i):
    return i / SPS


def test_speaker_switch_reacquires_within_bound():
    """Target jumps 540px (speaker switch, no scene-cut flag because Haar
    missed the frame): far-cluster snap must re-acquire within 3 samples."""
    samples = [( _t(i), 690.0, "face", False) for i in range(12)]
    samples += [( _t(12 + i), 1230.0, "motion", False) for i in range(12)]
    out = smooth_centers(samples, W, CROP_W, SPS)
    reacq = next(t for t, x in out if t >= _t(12) and abs(x - 1230) < 120)
    assert reacq - _t(12) <= 3 / SPS + 1e-9, f"re-acquired at +{reacq - _t(12):.2f}s"


def test_scene_cut_with_face_snaps_immediately():
    samples = [(_t(i), 690.0, "face", False) for i in range(6)]
    samples += [(_t(6), 1230.0, "face", True)]  # hard cut + face detection
    samples += [(_t(7 + i), 1230.0, "face", False) for i in range(3)]
    out = smooth_centers(samples, W, CROP_W, SPS)
    assert abs(out[6][1] - 1230) < 1, "scene cut + face must snap same sample"


def test_absence_holds_last_position():
    samples = [(_t(i), 800.0, "face", False) for i in range(6)]
    samples += [(_t(6 + i), None, "hold", False) for i in range(20)]
    out = smooth_centers(samples, W, CROP_W, SPS)
    held = [x for t, x in out[6:]]
    assert max(held) - min(held) < 1e-9, "no-detection samples must hold position"


def test_jitter_is_smoothed():
    rng = np.random.default_rng(5)
    noisy = 900 + rng.normal(0, 30, 60)
    samples = [(_t(i), float(noisy[i]), "face", False) for i in range(60)]
    out = smooth_centers(samples, W, CROP_W, SPS)
    xs = np.array([x for _, x in out[10:]])
    assert xs.std() < 15, f"output std {xs.std():.1f} vs input 30"


def test_fast_pan_tracked_with_bounded_lag():
    """200px/s ramp: error-proportional gain must keep lag < crop margin."""
    samples = [(_t(i), 500.0 + 200.0 * _t(i), "face", False) for i in range(60)]
    out = smooth_centers(samples, W, CROP_W, SPS)
    errs = [abs(x - (500.0 + 200.0 * t)) for t, x in out[12:]]
    assert max(errs) < 130, f"steady-state lag {max(errs):.0f}px"


def test_single_outlier_detection_does_not_yank_track():
    samples = [(_t(i), 800.0, "face", False) for i in range(10)]
    samples[5] = (_t(5), 1700.0, "motion", False)  # one bogus centroid
    out = smooth_centers(samples, W, CROP_W, SPS)
    assert all(abs(x - 800) < 90 for _, x in out), "outlier must not snap the track"
