"""Engine stress-test harness: scenario x metric matrix vs generator ground truth.

Runs at $0 — only local ffmpeg/whisper/OpenCV; the LLM stages are never touched.
Every pass/fail below is a measured diff against the scenario generator's
known ground truth (planted pause intervals, planted filler intervals,
per-frame subject centers, speaker-switch times) — see tools/make_test_clip.py.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .config import Config
from .engine import croptrack
from .stages import StageError, edit, ingest

STRESS_DIR = Path("testdata/stress")
RUNS_DIR = Path("runs/stress")

# clips each scenario produces (music renders one clip per SNR)
CLIPS = {
    "handheld": ["handheld.mp4"],
    "music": ["music_snr18.mp4", "music_snr08.mp4"],
    "alternation": ["alternation.mp4"],
    "exit_reenter": ["exit_reenter.mp4"],
    "low_contrast": ["low_contrast.mp4"],
    "dense_filler": ["dense_filler.mp4"],
    "boundary_silence": ["boundary_silence.mp4"],
}
ORDER = list(CLIPS)


@dataclass
class Metric:
    scenario: str
    name: str
    measured: str
    threshold: str
    passed: bool
    note: str = ""


@dataclass
class ScenarioResult:
    name: str
    metrics: list[Metric] = field(default_factory=list)

    def add(self, name, measured, threshold, passed, note=""):
        self.metrics.append(Metric(self.name, name, str(measured),
                                   str(threshold), bool(passed), note))


# ------------------------------------------------------------ infrastructure
def ensure_scenario(name: str, regen: bool) -> dict:
    gt_path = STRESS_DIR / f"{name}.gt.json"
    missing = regen or not gt_path.exists() or any(
        not (STRESS_DIR / c).exists() for c in CLIPS[name])
    if missing:
        print(f"    generating {name} clip(s)...")
        subprocess.run([sys.executable, "tools/make_test_clip.py",
                        "--scenario", name, "--outdir", str(STRESS_DIR)],
                       check=True, capture_output=True, text=True)
    return json.loads(gt_path.read_text())


def run_engine(clip: Path, cfg: Config) -> dict:
    """ingest + edit stages (the local engine path), stage-gated."""
    run_dir = RUNS_DIR / clip.stem
    if run_dir.exists():
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True)
    ctx = {"run_dir": run_dir, "footage": clip.resolve(), "topic": "stress",
           "cfg": cfg, "skip_llm": True}
    out = {"run_dir": run_dir, "error": None}
    try:
        ingest.run(ctx)
        edit.run(ctx)
    except (StageError, Exception) as e:  # noqa: BLE001 — recorded, not hidden
        out["error"] = f"{type(e).__name__}: {e}"
        return out
    out["ingest"] = json.loads((run_dir / "ingest-report.json").read_text())
    out["decisions"] = json.loads((run_dir / "edit-decisions.json").read_text())
    return out


def track_arrays(clip: Path, gt: dict) -> dict:
    """Run croptrack over the whole raw clip; align with GT per-frame centers."""
    track = croptrack.track_crop(clip, (0.0, gt["duration"] - 0.2))
    fps = gt["fps"]
    gt_cx = np.array(gt["cx"], dtype=float)
    ts, centers, gts = [], [], []
    for t, x in track["keyframes"]:
        fi = min(int(round(t * fps)), len(gt_cx) - 1)
        ts.append(t)
        centers.append(x + track["crop_w"] / 2)
        gts.append(gt_cx[fi])
    return {"t": np.array(ts), "center": np.array(centers),
            "gt": np.array(gts), "track": track}


def _overlap(a0, a1, b0, b1) -> float:
    return max(0.0, min(a1, b1) - max(a0, b0))


# ----------------------------------------------------------------- checkers
def check_handheld(gt: dict, cfg: Config) -> ScenarioResult:
    r = ScenarioResult("handheld")
    clip = STRESS_DIR / "handheld.mp4"
    eng = run_engine(clip, cfg)
    r.add("stage gates (ingest+edit)", eng["error"] or "pass", "no StageError",
          eng["error"] is None, note=str(eng["error"] or ""))

    ta = track_arrays(clip, gt)
    half = ta["track"]["crop_w"] / 2
    err = np.abs(ta["center"] - ta["gt"])
    contained = float(np.mean(err <= half - 40))
    r.add("subject containment", f"{contained * 100:.1f}%", ">= 99% of samples",
          contained >= 0.99,
          note=f"|center err| <= crop_w/2-40px; crop_w={ta['track']['crop_w']}")
    mean_err = float(np.mean(err))
    r.add("mean tracking error", f"{mean_err:.0f}px",
          f"<= crop_w/4 = {half / 2:.0f}px", mean_err <= half / 2)
    # tracking loss rate: average out-of-crop pixels per sample
    loss = float(np.mean(np.maximum(0, err - (half - 40))))
    r.add("tracking loss rate", f"{loss:.1f}px avg", "<= 2px avg overflow",
          loss <= 2.0)
    return r


def check_music(gt: dict, cfg: Config) -> ScenarioResult:
    r = ScenarioResult("music")
    pauses = [e for e in gt["events"] if e["kind"] == "pause"]
    speech = [e for e in gt["events"] if e["kind"] != "pause"]
    for snr in gt["snrs"]:
        clip = STRESS_DIR / f"music_snr{snr:02d}.mp4"
        eng = run_engine(clip, cfg)
        r.add(f"snr{snr:02d}: stage gates", eng["error"] or "pass",
              "no StageError", eng["error"] is None)
        if eng["error"]:
            continue
        sil = eng["ingest"]["silence_map"]["silences"]
        sil = [s for s in sil if s["end"] is not None]
        # false positives: detected silence overlapping known speech
        # (0.25s edge tolerance for silencedetect boundary timing)
        fp_time = sum(_overlap(s["start"], s["end"], e["start"] + 0.25,
                               e["end"] - 0.25)
                      for s in sil for e in speech)
        speech_time = sum(e["end"] - e["start"] for e in speech)
        fp_rate = fp_time / speech_time
        r.add(f"snr{snr:02d}: silence false-positive rate",
              f"{fp_rate * 100:.2f}% of speech time", "<= 1%", fp_rate <= 0.01)
        # recall: planted pauses (all > cfg.min_silence) actually detected
        hit = sum(1 for p in pauses if any(
            _overlap(s["start"], s["end"], p["start"], p["end"])
            >= 0.6 * (p["end"] - p["start"]) for s in sil))
        recall = hit / len(pauses)
        r.add(f"snr{snr:02d}: pause recall", f"{recall * 100:.0f}% ({hit}/{len(pauses)})",
              ">= 80%", recall >= 0.8,
              note=f"threshold used: {eng['ingest']['silence_map']['threshold_db']}dB")
    return r


def check_alternation(gt: dict, cfg: Config) -> ScenarioResult:
    r = ScenarioResult("alternation")
    clip = STRESS_DIR / "alternation.mp4"
    eng = run_engine(clip, cfg)
    r.add("stage gates (ingest+edit)", eng["error"] or "pass", "no StageError",
          eng["error"] is None)

    ta = track_arrays(clip, gt)
    half = ta["track"]["crop_w"] / 2
    # re-acquire time after each hard speaker switch
    worst = 0.0
    for sw in gt["switches"]:
        target = ta["gt"][ta["t"] >= sw + 0.3]
        after = (ta["t"] >= sw)
        idx = np.where(after & (np.abs(ta["center"] - ta["gt"]) < 120))[0]
        dt = (ta["t"][idx[0]] - sw) if len(idx) else float("inf")
        worst = max(worst, dt)
    r.add("worst re-acquire after switch",
          f"{worst:.2f}s" if np.isfinite(worst) else "never",
          "<= 1.5s", worst <= 1.5)
    # settled tracking share outside the 1.5s re-acquire grace windows
    grace = np.zeros(len(ta["t"]), dtype=bool)
    for sw in gt["switches"]:
        grace |= (ta["t"] >= sw) & (ta["t"] < sw + 1.5)
    err = np.abs(ta["center"] - ta["gt"])[~grace]
    settled = float(np.mean(err <= half - 40))
    r.add("settled containment (excl. grace)", f"{settled * 100:.1f}%",
          ">= 95%", settled >= 0.95)
    return r


def check_exit_reenter(gt: dict, cfg: Config) -> ScenarioResult:
    r = ScenarioResult("exit_reenter")
    clip = STRESS_DIR / "exit_reenter.mp4"
    eng = run_engine(clip, cfg)
    r.add("stage gates (ingest+edit)", eng["error"] or "pass", "no StageError",
          eng["error"] is None)

    ta = track_arrays(clip, gt)
    visible = np.array(gt["visible"], dtype=bool)
    fps = gt["fps"]
    vis_at = lambda t: visible[min(int(round(t * fps)), len(visible) - 1)]
    sample_vis = np.array([vis_at(t) for t in ta["t"]])

    # documented fallback: hold last known position while subject is gone
    gone = ~sample_vis
    if gone.any():
        last_vis_center = ta["center"][sample_vis][
            np.searchsorted(ta["t"][sample_vis], ta["t"][gone][0]) - 1]
        drift = float(np.max(np.abs(ta["center"][gone] - last_vis_center)))
        r.add("hold drift while subject absent", f"{drift:.0f}px",
              "<= 150px (hold-last-position fallback)", drift <= 150)
    # re-acquire after re-entry
    t_back = gt["marks"]["back"]
    idx = np.where((ta["t"] >= t_back) & sample_vis
                   & (np.abs(ta["center"] - ta["gt"]) < 140))[0]
    dt = (ta["t"][idx[0]] - t_back) if len(idx) else float("inf")
    r.add("re-acquire after re-entry",
          f"{dt:.2f}s" if np.isfinite(dt) else "never", "<= 2.0s", dt <= 2.0)
    return r


def check_low_contrast(gt: dict, cfg: Config) -> ScenarioResult:
    r = ScenarioResult("low_contrast")
    clip = STRESS_DIR / "low_contrast.mp4"
    eng = run_engine(clip, cfg)
    r.add("stage gates (ingest+edit)", eng["error"] or "pass", "no StageError",
          eng["error"] is None)

    ta = track_arrays(clip, gt)
    st = ta["track"]["stats"]
    active = 100 - st["hold_pct"]
    r.add("detection share (face+motion)", f"{active:.1f}%",
          ">= 50% (motion fallback must carry)", active >= 50,
          note=f"face {st['face_pct']}% / motion {st['motion_pct']}% / hold {st['hold_pct']}%")
    err = np.abs(ta["center"] - ta["gt"])
    mean_err = float(np.mean(err))
    r.add("mean tracking error", f"{mean_err:.0f}px", "<= 150px",
          mean_err <= 150)
    span_ratio = ((ta["center"].max() - ta["center"].min())
                  / max(1.0, ta["gt"].max() - ta["gt"].min()))
    r.add("movement span ratio", f"{span_ratio:.2f}",
          ">= 0.5 (not a silent static/center crop)", span_ratio >= 0.5)
    return r


def check_dense_filler(gt: dict, cfg: Config) -> ScenarioResult:
    r = ScenarioResult("dense_filler")
    clip = STRESS_DIR / "dense_filler.mp4"
    eng = run_engine(clip, cfg)
    r.add("stage gates (ingest+edit)", eng["error"] or "pass", "no StageError",
          eng["error"] is None)
    if eng["error"]:
        return r

    gt_fillers = [e for e in gt["events"] if e["kind"] == "filler"]
    detected = eng["decisions"]["filler_cuts"]
    tol = 0.3
    def matches(d, g):
        mid = (d["start"] + d["end"]) / 2
        return g["start"] - tol <= mid <= g["end"] + tol
    hit = sum(1 for g in gt_fillers if any(matches(d, g) for d in detected))
    recall = hit / len(gt_fillers)
    fp = sum(1 for d in detected if not any(matches(d, g) for g in gt_fillers))
    precision = (len(detected) - fp) / max(1, len(detected))
    r.add("filler recall", f"{recall * 100:.0f}% ({hit}/{len(gt_fillers)})",
          ">= 70%", recall >= 0.7,
          note=f"{len(detected)} detected cuts vs {len(gt_fillers)} planted")
    r.add("filler precision", f"{precision * 100:.0f}% ({fp} false cuts)",
          ">= 80%", precision >= 0.8,
          note="false cut = detection not overlapping any planted filler "
               "(includes legit 'like'/umbrella/summer traps)")
    return r


def check_boundary_silence(gt: dict, cfg: Config) -> ScenarioResult:
    r = ScenarioResult("boundary_silence")
    clip = STRESS_DIR / "boundary_silence.mp4"
    eng = run_engine(clip, cfg)
    r.add("stage gates (ingest+edit)", eng["error"] or "pass", "no StageError",
          eng["error"] is None)
    if eng["error"]:
        return r

    cut = eng["decisions"]["cutlist"]
    pauses = [e for e in gt["events"] if e["kind"] == "pause"]
    total = gt["duration"]
    # expected removal per pause, computed from the engine's actual Config
    expected_removed = 0.0
    for p in pauses:
        d = p["end"] - p["start"]
        at_start = p["start"] < 0.05
        at_end = p["end"] > total - 1.0  # trailing pause runs to clip end
        pad = cfg.keep_pad * ((0 if at_start else 1) + (0 if at_end else 1))
        cut_len = d - pad
        if cut_len >= cfg.min_cut:
            expected_removed += cut_len
    expected_edited = total - expected_removed
    got = cut["edited_duration"]
    r.add("edited duration vs config-derived expectation",
          f"{got:.2f}s", f"{expected_edited:.2f}s ± 0.7s",
          abs(got - expected_edited) <= 0.7,
          note=f"keep_pad={cfg.keep_pad}, min_cut={cfg.min_cut} read from Config")
    lead = pauses[0]
    first_kept = cut["kept"][0]["start"]
    exp_first = lead["end"] - cfg.keep_pad
    r.add("leading silence trimmed to t=0 edge rule",
          f"first kept at {first_kept:.2f}s", f"{exp_first:.2f}s ± 0.3s",
          abs(first_kept - exp_first) <= 0.3)
    tail = pauses[-1]
    last_kept = cut["kept"][-1]["end"]
    exp_last = tail["start"] + cfg.keep_pad
    r.add("trailing silence trimmed to clip end",
          f"last kept ends {last_kept:.2f}s", f"{exp_last:.2f}s ± 0.3s",
          abs(last_kept - exp_last) <= 0.3)
    min_kept = min(s["end"] - s["start"] for s in cut["kept"])
    r.add("pacing guard: min kept segment", f"{min_kept:.2f}s",
          f">= min_segment {cfg.min_segment}s", min_kept >= cfg.min_segment - 0.05)
    return r


CHECKERS = {
    "handheld": check_handheld,
    "music": check_music,
    "alternation": check_alternation,
    "exit_reenter": check_exit_reenter,
    "low_contrast": check_low_contrast,
    "dense_filler": check_dense_filler,
    "boundary_silence": check_boundary_silence,
}


# ----------------------------------------------------------------- reporting
def write_matrix(results: list[ScenarioResult], path: Path):
    lines = ["# Stress-test results matrix", "",
             "Every measured value is diffed against generator ground truth "
             "(see tools/make_test_clip.py). $0 run — no LLM calls.", "",
             "| scenario | metric | measured | expected | result | note |",
             "|---|---|---|---|---|---|"]
    for res in results:
        for m in res.metrics:
            lines.append(
                f"| {m.scenario} | {m.name} | {m.measured} | {m.threshold} | "
                f"{'PASS' if m.passed else '**FAIL**'} | {m.note} |")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")


def run_stress(scenarios: list[str] | None = None, regen: bool = False) -> int:
    cfg = Config()
    names = scenarios or ORDER
    results: list[ScenarioResult] = []
    for name in names:
        print(f"--- scenario: {name} " + "-" * (48 - len(name)))
        gt = ensure_scenario(name, regen)
        res = CHECKERS[name](gt, cfg)
        results.append(res)
        for m in res.metrics:
            flag = "ok " if m.passed else "FAIL"
            print(f"    {flag} {m.name}: {m.measured} (expected {m.threshold})")
    out = RUNS_DIR / "stress-results.md"
    write_matrix(results, out)
    failed = sum(1 for r in results for m in r.metrics if not m.passed)
    total = sum(len(r.metrics) for r in results)
    print(f"\n{total - failed}/{total} metrics pass -> {out}")
    return 1 if failed else 0
