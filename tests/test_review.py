"""Unit tests for the studio review-decision overlay (pure logic, no media)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vlog_pipeline import review as rv

CUTLIST = {
    "removed": [
        {"start": 2.0, "end": 3.0, "kind": "silence", "reason": "silence", "dur": 1.0},
        {"start": 5.0, "end": 5.4, "kind": "filler", "reason": "filler 'um'", "dur": 0.4},
        {"start": 8.0, "end": 9.5, "kind": "silence", "reason": "silence", "dur": 1.5},
    ],
    "kept": [{"start": 0.0, "end": 2.0}, {"start": 3.0, "end": 5.0},
             {"start": 5.4, "end": 8.0}, {"start": 9.5, "end": 12.0}],
}
TOTAL = 12.0


def test_default_overlay_matches_engine():
    r = rv.default_review()
    assert rv.predicted_duration(CUTLIST, r, TOTAL) == TOTAL - 2.9
    kept = rv.effective_kept(CUTLIST, r, TOTAL)
    assert kept == CUTLIST["kept"]


def test_reject_cut_restores_content():
    r = rv.default_review()
    r["cuts"]["e1"] = {"status": "rejected"}
    assert rv.predicted_duration(CUTLIST, r, TOTAL) == TOTAL - 2.5
    kept = rv.effective_kept(CUTLIST, r, TOTAL)
    assert {"start": 3.0, "end": 8.0} in kept  # filler cut healed over


def test_nudge_boundaries():
    r = rv.default_review()
    r["cuts"]["e0"] = {"status": "accepted", "start": 1.8, "end": 3.2}
    assert abs(rv.predicted_duration(CUTLIST, r, TOTAL) - (TOTAL - 3.3)) < 1e-9
    view = rv.decisions_view(CUTLIST, r)
    e0 = next(c for c in view if c["id"] == "e0")
    assert e0["start"] == 1.8 and e0["engine_start"] == 2.0  # engine EDL untouched


def test_manual_cut_and_overlap_merge():
    r = rv.default_review()
    r["manual_cuts"] = [{"id": "m1", "start": 2.5, "end": 4.0}]
    merged = rv.effective_removals(CUTLIST, r, TOTAL)
    assert merged[0] == {"start": 2.0, "end": 4.0}  # merged with e0 for math
    view = rv.decisions_view(CUTLIST, r)
    assert sum(1 for c in view if c["kind"] == "manual") == 1  # identity kept


def test_time_mapping_roundtrip():
    r = rv.default_review()
    kept = rv.effective_kept(CUTLIST, r, TOTAL)
    for t in (0.5, 3.5, 6.0, 10.0):
        e = rv.map_orig_to_edit(t, kept)
        assert e is not None
        back = rv.map_edit_to_orig(e, kept)
        assert abs(back - t) < 0.002
    assert rv.map_orig_to_edit(2.5, kept) is None  # inside a cut


def test_captions_track_cut_changes():
    lines = [{"id": "l0", "start": 4.5, "end": 6.0, "text": "hello world"}]
    r = rv.default_review()
    kept = rv.effective_kept(CUTLIST, r, TOTAL)
    exp = rv.captions_for_export(lines, kept)
    assert len(exp) == 1
    dur_with_cut = exp[0]["end"] - exp[0]["start"]
    # reject the filler cut inside the line -> line grows by the cut length
    r["cuts"]["e1"] = {"status": "rejected"}
    kept2 = rv.effective_kept(CUTLIST, r, TOTAL)
    exp2 = rv.captions_for_export(lines, kept2)
    assert abs((exp2[0]["end"] - exp2[0]["start"]) - (dur_with_cut + 0.4)) < 0.002


def test_caption_fully_inside_cut_dropped():
    lines = [{"id": "l0", "start": 8.2, "end": 9.3, "text": "gone"}]
    kept = rv.effective_kept(CUTLIST, rv.default_review(), TOTAL)
    assert rv.captions_for_export(lines, kept) == []


def test_reanalyze_matching_inherits_and_flags():
    r = rv.default_review()
    r["cuts"]["e0"] = {"status": "rejected"}
    r["cuts"]["e2"] = {"status": "accepted", "start": 7.9}
    new_removed = [
        {"start": 2.05, "end": 3.1, "kind": "silence"},   # ~e0 -> inherit rejected
        {"start": 8.1, "end": 9.4, "kind": "silence"},    # ~e2 -> inherit nudge
        {"start": 10.5, "end": 11.0, "kind": "silence"},  # brand new
    ]
    nr, stats = rv.match_decisions(CUTLIST["removed"], r, new_removed)
    assert nr["cuts"]["e0"] == {"status": "rejected"}
    assert nr["cuts"]["e1"]["start"] == 7.9
    assert nr["unreviewed"] == ["e2"]
    assert stats["inherited"] == 2 and stats["new_unreviewed"] == 1


def test_reanalyze_preserves_manual_and_captions():
    r = rv.default_review()
    r["manual_cuts"] = [{"id": "m1", "start": 1.0, "end": 1.5}]
    r["captions"] = [{"id": "l0", "start": 0.5, "end": 1.0, "text": "edited"}]
    nr, _ = rv.match_decisions(CUTLIST["removed"], r, [])
    assert nr["manual_cuts"] == r["manual_cuts"]
    assert nr["captions"] == r["captions"]


def test_srt_inverse_map_fallback(tmp_path):
    (tmp_path / "captions.srt").write_text(
        "1\n00:00:01,000 --> 00:00:02,000\nfirst line\n\n"
        "2\n00:00:03,500 --> 00:00:04,500\nsecond line\n")
    lines = rv.derive_caption_lines(tmp_path, CUTLIST)
    # edited 1.0s is inside kept[0] (0-2) -> original 1.0
    assert abs(lines[0]["start"] - 1.0) < 0.002
    # edited 3.5s: past kept[0] (2s) -> 1.5 into kept[1] (3.0-5.0) -> 4.5 orig
    assert abs(lines[1]["start"] - 4.5) < 0.002
    assert lines[1]["text"] == "second line"
