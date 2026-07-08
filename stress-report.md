# Engine stress-test report

Seven synthetic stress scenarios were generated with **generator-known ground
truth** (exact planted pause intervals, exact planted filler-word intervals,
per-frame subject centers, speaker-switch times), the full local engine
(ingest + edit + croptrack) was run against each, and every metric below is a
measured diff against that ground truth — no eyeballing, no fabricated passes.
Total LLM cost of this entire hardening pass: **$0** (engine-only; the
plan/review/optimize stages were never invoked).

- Harness: `vlog-pipeline stress` (or `pytest tests/test_stress_scenarios.py -m slow`)
- Scenario generator: `tools/make_test_clip.py --scenario all --outdir testdata/stress`
- Machine-written matrix: `runs/stress/stress-results.md`
- Pre-fix matrix snapshot: `runs/stress/stress-results-v1-prefix.md`

## Results after hardening (all 28 metrics pass)

| scenario | metric | before fixes | after fixes | expected |
|---|---|---|---|---|
| handheld | subject containment | **97.1%** | 100.0% | ≥ 99% |
| handheld | mean tracking error | 76px | 26px | ≤ 152px (crop_w/4) |
| handheld | tracking loss rate | 0.4px avg | 0.0px avg | ≤ 2px avg overflow |
| music snr18 | silence false-positive rate | 0.00% | 0.00% | ≤ 1% of speech time |
| music snr18 | pause recall | **0% (0/4)** | 100% (4/4) | ≥ 80% |
| music snr08 | silence false-positive rate | 0.00% | 0.00% | ≤ 1% of speech time |
| music snr08 | pause recall | **0% (0/4)** | 100% (4/4) | ≥ 80% |
| alternation | worst re-acquire after switch | **1.80s** | 1.07s | ≤ 1.5s |
| alternation | settled containment | 99.3% | 99.3% | ≥ 95% |
| exit_reenter | hold drift while absent | 0px | 0px | ≤ 150px |
| exit_reenter | re-acquire after re-entry | 1.50s | 1.50s | ≤ 2.0s |
| low_contrast | detection share (non-hold) | 96.4% | 99.1% | ≥ 50% |
| low_contrast | mean tracking error | 34px | 22px | ≤ 150px |
| low_contrast | movement span ratio | 0.99 | 0.99 | ≥ 0.5 |
| dense_filler | filler recall | 91% (10/11) | 91% (10/11) | ≥ 70% |
| dense_filler | filler precision | 100% (0 false cuts) | 100% | ≥ 80% |
| boundary_silence | edited duration vs config-derived | **33.11s** | 29.18s | 29.47s ± 0.7s |
| boundary_silence | leading silence to t=0 rule | 2.85s | 2.85s | 2.85s ± 0.3s |
| boundary_silence | trailing silence to clip end | **44.47s (uncut!)** | 40.53s | 40.62s ± 0.3s |
| boundary_silence | min kept segment | pass | 7.25s | ≥ min_segment 0.6s |

(Stage-gate "no StageError" metrics passed in every scenario before and after.)

## What failed initially and what was fixed

### 1. Trailing/leading dead air survived edits (boundary_silence — genuine bug)

silencedetect's timestamps sit a few ms inside the container duration (codec
padding), so cutting a trailing silence left a sub-perceptual "kept" fragment
(8ms) at the clip edge. The pacing guard saw a segment shorter than
`min_segment` and its only remedy was to *restore the entire trailing-silence
cut* — 4 seconds of dead air survived into the export. The baseline day30 run
had the same signature ("160.46–161.26s restored for pacing"), so this bug was
already shipping.

**Fix** (`engine/cutlist.py`): edge cuts snap to the true clip boundary, and
the pacing guard *absorbs* too-short edge fragments into the adjacent cut
instead of restoring it. Mid-clip restore behavior is unchanged.
Regression tests: `tests/test_cutlist.py` (8 tests, both edges + mid-clip).

### 2. Silence detection blind under music beds (music — genuine bug, two layers)

Layer 1: the fixed −35dB threshold sits below a music bed's level, so
silencedetect never fires (pause recall 0% at both SNRs, though false-positive
rate was also 0%). Layer 2: the natural fix — measure the noise floor and set
a floor-relative threshold — still detected nothing, because the floor was
measured in RMS while **silencedetect is peak-based**: a −28dB-RMS bed has
~−17dB frame peaks.

**Fix** (`engine/silence.py`): `measure_levels()` measures 50ms frame-*peak*
levels; `pick_threshold()` engages a floor-relative rescue threshold **only**
when the peak floor reaches the fixed threshold (clean footage keeps the
configured value — the baseline clip's floor is −75dB and stays at −35dB
fixed), and declines entirely when floor is within 8dB of speech rather than
risk cutting into words. The 0.5 floor→speech factor was chosen from a
measured recall/FP sweep (recall 4/4 and FP 0.00s were flat across factors
0.45–0.6 at both SNRs — the midpoint sits inside a wide safe plateau).
Regression tests: `tests/test_silence_threshold.py`.

### 3. Slow re-acquire after hard cuts (alternation — genuine bug)

The smoother's 260px/s speed clamp made the crop *glide* 538px to a new
speaker after a hard cut (1.80s > 1.5s bound). **Fix** (`engine/croptrack.py`):
scene-cut snap (large frame delta + a face detection → jump immediately) and
far-cluster snap (three consecutive detections agreeing on a position far from
the current track → snap to their median, ~0.5s) — the latter also covers
switches where Haar misses the new face. Measured after: worst re-acquire 1.07s.

### 4. Motion centroid chased camera motion (handheld — genuine bug, one dead end)

During a speech pause coinciding with a camera pan, Haar missed, the mouth was
closed, and the motion centroid averaged the *entire moving background*,
dragging the crop ~270px off the subject (containment 97.1%).

A first fix attempt — phase-correlation camera-motion compensation — made
everything much worse (handheld 75%, alternation 5.6s) because on
flat-background talking-head footage the *dominant* translation is the subject
itself, so the compensation subtracted the subject's motion and handed the
centroid the background. **Reverted.**

Fixes that stuck: a **compactness gate** (a diffuse moving-pixel cloud means
"camera moved" — don't chase it) plus **LK optical-flow tracking** from the
last known position, which follows the subject's own texture through pans and
closed-mouth pauses. Detection ladder is now: Haar face → optical flow →
compact motion centroid → hold. Measured after: 100% containment, mean error
26px (from 76px); low_contrast also improved (hold share 3.6% → 0.9%).
Regression tests: `tests/test_croptrack_smoothing.py` (pure smoothing:
switch snap, scene-cut snap, absence hold, jitter, ramp lag, outlier).

## What was NOT chased (generator artifacts / non-bugs)

- **dense_filler recall 91% (10/11)**: the one miss is the planted
  hesitation-"like" — whisper transcribed it confidently (prob 0.99) and the
  TTS rendered it short (0.43s), so the contextual-filler rule (cut "like"
  only when ASR confidence is low or the word is drawn out ≥ 0.6s) correctly
  declined. Partly a generator artifact (TTS at rate 120 still produces a
  crisp "like", not a natural hesitation), partly the documented
  precision-over-recall design for contextual fillers: the same rule is why
  precision is 100% — none of the acoustic traps (umbrella / summer / unlike /
  legit "like this camera") were falsely cut, which is the error that costs
  content. All unconditional fillers (um/uh/erm/hmm/ah), including the
  back-to-back "um uh" pair, were caught.
- **exit_reenter re-acquire 1.50s**: within the 2.0s bound both before and
  after; the subject re-enters at the frame edge where only a sliver is
  visible for the first ~1s. Left as-is.

## Documented fallback behaviors (now tested, not just intended)

- Subject fully out of frame → **hold last known position** (measured drift
  while absent: 0px), re-acquire on return (1.50s ≤ 2.0s bound).
- Raised noise floor with speech within 8dB of the floor → silence removal is
  **effectively disabled with an explicit note** in ingest-report.json
  (threshold_mode), rather than misfiring into speech.
- No max-gap cap exists on silence removal by design: the 8s mid-clip silence
  is removed in full (minus `keep_pad` on both sides).

## Remaining known limitations

- Haar frontal-face + flow + motion heuristics track **one** subject; two
  simultaneously visible active speakers, faces in profile, or subject swaps
  without a hard cut are out of scope (alternation covers hard-cut swaps only).
- The whisper layer, not the filler detector, bounds filler recall (~91% on
  dense TTS filler speech; real conversational fillers with co-articulation
  may be lower).
- Silence rescue thresholds are derived from whole-file statistics; footage
  whose noise floor changes mid-file (music starts halfway) gets one global
  threshold.
- All scenarios are synthetic (TTS + drawn presenter). Haar face hit rates on
  real faces should be higher than on the cartoon presenter; the flow/motion
  fallback shares measured here are conservative in that respect.
