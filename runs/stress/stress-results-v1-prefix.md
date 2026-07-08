# Stress-test results matrix

Every measured value is diffed against generator ground truth (see tools/make_test_clip.py). $0 run — no LLM calls.

| scenario | metric | measured | expected | result | note |
|---|---|---|---|---|---|
| handheld | stage gates (ingest+edit) | pass | no StageError | PASS |  |
| handheld | subject containment | 97.1% | >= 99% of samples | **FAIL** | |center err| <= crop_w/2-40px; crop_w=606 |
| handheld | mean tracking error | 76px | <= crop_w/4 = 152px | PASS |  |
| handheld | tracking loss rate | 0.4px avg | <= 2px avg overflow | PASS |  |
| music | snr18: stage gates | pass | no StageError | PASS |  |
| music | snr18: silence false-positive rate | 0.00% of speech time | <= 1% | PASS |  |
| music | snr18: pause recall | 0% (0/4) | >= 80% | **FAIL** | threshold used: -35.0dB |
| music | snr08: stage gates | pass | no StageError | PASS |  |
| music | snr08: silence false-positive rate | 0.00% of speech time | <= 1% | PASS |  |
| music | snr08: pause recall | 0% (0/4) | >= 80% | **FAIL** | threshold used: -35.0dB |
| alternation | stage gates (ingest+edit) | pass | no StageError | PASS |  |
| alternation | worst re-acquire after switch | 1.80s | <= 1.5s | **FAIL** |  |
| alternation | settled containment (excl. grace) | 99.3% | >= 95% | PASS |  |
| exit_reenter | stage gates (ingest+edit) | pass | no StageError | PASS |  |
| exit_reenter | hold drift while subject absent | 0px | <= 150px (hold-last-position fallback) | PASS |  |
| exit_reenter | re-acquire after re-entry | 1.50s | <= 2.0s | PASS |  |
| low_contrast | stage gates (ingest+edit) | pass | no StageError | PASS |  |
| low_contrast | detection share (face+motion) | 96.4% | >= 50% (motion fallback must carry) | PASS | face 35.7% / motion 60.7% / hold 3.6% |
| low_contrast | mean tracking error | 34px | <= 150px | PASS |  |
| low_contrast | movement span ratio | 0.99 | >= 0.5 (not a silent static/center crop) | PASS |  |
| dense_filler | stage gates (ingest+edit) | pass | no StageError | PASS |  |
| dense_filler | filler recall | 91% (10/11) | >= 70% | PASS | 9 detected cuts vs 11 planted |
| dense_filler | filler precision | 100% (0 false cuts) | >= 80% | PASS | false cut = detection not overlapping any planted filler (includes legit 'like'/umbrella/summer traps) |
| boundary_silence | stage gates (ingest+edit) | pass | no StageError | PASS |  |
| boundary_silence | edited duration vs config-derived expectation | 33.11s | 29.47s ± 0.7s | **FAIL** | keep_pad=0.15, min_cut=0.12 read from Config |
| boundary_silence | leading silence trimmed to t=0 edge rule | first kept at 2.85s | 2.85s ± 0.3s | PASS |  |
| boundary_silence | trailing silence trimmed to clip end | last kept ends 44.47s | 40.62s ± 0.3s | **FAIL** |  |
| boundary_silence | pacing guard: min kept segment | 10.60s | >= min_segment 0.6s | PASS |  |
