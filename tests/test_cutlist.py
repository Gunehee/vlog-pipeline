"""Unit regression tests for cutlist assembly + pacing guard (no media needed)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vlog_pipeline.config import Config
from vlog_pipeline.engine import cutlist as cl


CFG = Config()


def test_basic_silence_cut_with_padding():
    cut = cl.build_cutlist(
        60.0, [{"start": 10.0, "end": 12.0, "dur": 2.0}], [], CFG)
    assert len(cut["removed"]) == 1
    r = cut["removed"][0]
    assert abs(r["start"] - (10.0 + CFG.keep_pad)) < 1e-6
    assert abs(r["end"] - (12.0 - CFG.keep_pad)) < 1e-6
    assert abs(cut["edited_duration"] - (60.0 - r["dur"])) < 1e-6


def test_leading_silence_cut_from_zero():
    cut = cl.build_cutlist(30.0, [{"start": 0.0, "end": 3.0, "dur": 3.0}], [], CFG)
    r = cut["removed"][0]
    assert r["start"] == 0.0, "leading silence must be cut from t=0, no pad"
    assert abs(r["end"] - (3.0 - CFG.keep_pad)) < 1e-6
    assert cut["kept"][0]["start"] == r["end"]


def test_trailing_silence_cut_to_clip_end_despite_container_padding():
    """Regression: silencedetect's end sits a few ms short of the container
    duration (codec padding). The phantom sub-perceptual kept fragment at the
    edge must not trick the pacing guard into restoring the whole trailing cut."""
    total = 44.467
    silences = [{"start": 40.383, "end": 44.459, "dur": 4.076}]  # real-run values
    cut = cl.build_cutlist(total, silences, [], CFG)
    assert cut["removed"], "trailing silence must stay cut"
    assert cut["kept"][-1]["end"] <= 40.383 + CFG.keep_pad + 0.01, (
        f"trailing dead air survived: kept runs to {cut['kept'][-1]['end']}")
    assert not cut["restored"], "pacing guard must not restore a trailing-silence cut"


def test_leading_silence_with_container_padding_at_start():
    """Mirror case: silence starts a few ms after 0 (decoder priming)."""
    cut = cl.build_cutlist(
        30.0, [{"start": 0.02, "end": 3.0, "dur": 2.98}], [], CFG)
    assert cut["kept"][0]["start"] >= 3.0 - CFG.keep_pad - 0.01
    assert not cut["restored"]


def test_pacing_guard_restores_midclip_cut_for_short_segment():
    """Two silences separated by a 0.25s sound burst: the kept island is
    0.25 + 2*keep_pad = 0.55s < min_segment, so the guard should cancel one
    cut (mid-clip restore is the right remedy there)."""
    silences = [{"start": 5.0, "end": 7.0, "dur": 2.0},
                {"start": 7.25, "end": 9.5, "dur": 2.25}]
    cut = cl.build_cutlist(30.0, silences, [], CFG)
    kept_durs = [s["end"] - s["start"] for s in cut["kept"]]
    assert min(kept_durs) >= CFG.min_segment - 0.05
    assert len(cut["restored"]) == 1


def test_open_ended_trailing_silence():
    """silencedetect start without end (file ends inside silence)."""
    cut = cl.build_cutlist(
        20.0, [{"start": 16.0, "end": None, "dur": None}], [], CFG)
    assert cut["kept"][-1]["end"] <= 16.0 + CFG.keep_pad + 0.01


def test_filler_cut_and_remap():
    fillers = [{"start": 5.0, "end": 5.4, "word": "um", "why": "filler 'um'"}]
    cut = cl.build_cutlist(20.0, [], fillers, CFG)
    assert len(cut["removed"]) == 1
    words = [{"word": "a", "start": 1.0, "end": 1.4, "prob": 0.9},
             {"word": "um", "start": 5.05, "end": 5.35, "prob": 0.9},
             {"word": "b", "start": 8.0, "end": 8.4, "prob": 0.9}]
    remapped = cl.remap_words(words, cut["kept"])
    assert [w["word"] for w in remapped] == ["a", "b"]
    b = remapped[1]
    assert abs(b["start"] - (8.0 - 0.4)) < 1e-6  # shifted left by the cut


def test_overlapping_removals_merge():
    silences = [{"start": 10.0, "end": 12.0, "dur": 2.0}]
    fillers = [{"start": 11.5, "end": 12.5, "word": "um", "why": "filler 'um'"}]
    cut = cl.build_cutlist(30.0, silences, fillers, CFG)
    assert len(cut["removed"]) == 1
    assert cut["removed"][0]["kind"] == "mixed"
