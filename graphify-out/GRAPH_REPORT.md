# Graph Report - vlog-pipeline  (2026-07-08)

## Corpus Check
- 73 files · ~55,449 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 350 nodes · 632 edges · 31 communities (28 shown, 3 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 20 edges (avg confidence: 0.52)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `67e86673`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_Config|Config]]
- [[_COMMUNITY_cli.py|cli.py]]
- [[_COMMUNITY_edit.py|edit.py]]
- [[_COMMUNITY_captions.py|captions.py]]
- [[_COMMUNITY_RunState|RunState]]
- [[_COMMUNITY_highlights.py|highlights.py]]
- [[_COMMUNITY_vlog-pipeline|vlog-pipeline]]
- [[_COMMUNITY_make_test_clip.py|make_test_clip.py]]
- [[_COMMUNITY_croptrack.py|croptrack.py]]
- [[_COMMUNITY_Review report|Review report]]
- [[_COMMUNITY_Review report|Review report]]
- [[_COMMUNITY_Upload kit|Upload kit]]
- [[_COMMUNITY_Plan Three lessons from my first 30 days of daily vlogging|Plan: Three lessons from my first 30 days of daily vlogging]]
- [[_COMMUNITY_fillers.py|fillers.py]]
- [[_COMMUNITY_silence.py|silence.py]]
- [[_COMMUNITY_transcribe.py|transcribe.py]]
- [[_COMMUNITY_Edit report|Edit report]]
- [[_COMMUNITY_vlog-pipeline|vlog-pipeline]]
- [[_COMMUNITY_report.py|report.py]]
- [[_COMMUNITY_Engine stress-test report|Engine stress-test report]]
- [[_COMMUNITY_Edit report|Edit report]]
- [[_COMMUNITY_Edit report|Edit report]]
- [[_COMMUNITY_Edit report|Edit report]]
- [[_COMMUNITY_Edit report|Edit report]]
- [[_COMMUNITY_Edit report|Edit report]]
- [[_COMMUNITY_Edit report|Edit report]]
- [[_COMMUNITY_Edit report|Edit report]]
- [[_COMMUNITY_Edit report|Edit report]]
- [[_COMMUNITY_stress-results|stress-results.md]]
- [[_COMMUNITY_stress-results-v1-prefix|stress-results-v1-prefix.md]]

## God Nodes (most connected - your core abstractions)
1. `Config` - 33 edges
2. `StageError` - 21 edges
3. `render_clip()` - 14 edges
4. `assemble()` - 12 edges
5. `run()` - 12 edges
6. `run_engine()` - 12 edges
7. `RunState` - 11 edges
8. `ScenarioResult` - 11 edges
9. `scen_music()` - 10 edges
10. `smooth_centers()` - 10 edges

## Surprising Connections (you probably didn't know these)
- `test_speaker_switch_reacquires_within_bound()` --calls--> `smooth_centers()`  [EXTRACTED]
  tests/test_croptrack_smoothing.py → vlog_pipeline/engine/croptrack.py
- `test_scene_cut_with_face_snaps_immediately()` --calls--> `smooth_centers()`  [EXTRACTED]
  tests/test_croptrack_smoothing.py → vlog_pipeline/engine/croptrack.py
- `test_absence_holds_last_position()` --calls--> `smooth_centers()`  [EXTRACTED]
  tests/test_croptrack_smoothing.py → vlog_pipeline/engine/croptrack.py
- `test_jitter_is_smoothed()` --calls--> `smooth_centers()`  [EXTRACTED]
  tests/test_croptrack_smoothing.py → vlog_pipeline/engine/croptrack.py
- `test_fast_pan_tracked_with_bounded_lag()` --calls--> `smooth_centers()`  [EXTRACTED]
  tests/test_croptrack_smoothing.py → vlog_pipeline/engine/croptrack.py

## Import Cycles
- None detected.

## Communities (31 total, 3 thin omitted)

### Community 0 - "Config"
Cohesion: 0.33
Nodes (8): _norm(), ndarray, Path, Highlight scoring: audio energy + speech rate on the edited timeline., Score the edited cut and choose the best short-form window., _rms_curve(), score_highlights(), validate()

### Community 1 - "cli.py"
Cohesion: 0.12
Nodes (19): _billing_table(), cmd_run(), cmd_status(), cmd_stress(), main(), vlog-pipeline CLI: run / status., api_key_present(), Headless `claude -p` subprocess calls for the Sonnet/Haiku text stages.  IMPORTA (+11 more)

### Community 2 - "edit.py"
Cohesion: 0.10
Nodes (41): CompletedProcess, RuntimeError, burn_captions(), _overlay_chain(), Path, ffmpeg rendering: jump-cut assembly with click-free audio joins., Re-assemble kept segments. Frame-accurate trim + 10 ms audio fades at     every, Chain of timed caption overlays. Returns (filter_lines, out_label). (+33 more)

### Community 3 - "captions.py"
Cohesion: 0.24
Nodes (9): build_lines(), _flush(), Path, Caption line building + SRT/ASS emission with platform-aware styling., Render each caption line to a styled transparent PNG for ffmpeg overlay.      St, Group word timestamps into readable caption lines., render_caption_pngs(), _srt_ts() (+1 more)

### Community 4 - "RunState"
Cohesion: 0.20
Nodes (23): Full-suite regression: every stress scenario must pass its metric gates.  Slow (, test_scenario(), Config, Pipeline configuration with editing thresholds and model routing., check_alternation(), check_boundary_silence(), check_dense_filler(), check_exit_reenter() (+15 more)

### Community 5 - "highlights.py"
Cohesion: 0.09
Nodes (18): Unit regression tests for cutlist assembly + pacing guard (no media needed)., Regression: silencedetect's end sits a few ms short of the container     duratio, Mirror case: silence starts a few ms after 0 (decoder priming)., Two silences separated by a 0.25s sound burst: the kept island is     0.25 + 2*k, silencedetect start without end (file ends inside silence)., test_leading_silence_with_container_padding_at_start(), test_open_ended_trailing_silence(), test_pacing_guard_restores_midclip_cut_for_short_segment() (+10 more)

### Community 6 - "vlog-pipeline"
Cohesion: 0.22
Nodes (8): Current limitations (post-hardening, measured), Engine hardening (stress suite), Install, Model routing, Proof: real end-to-end run, The edit engine (stage 3–4, all local signal analysis), vlog-pipeline, What it produces

### Community 7 - "make_test_clip.py"
Cohesion: 0.14
Nodes (38): assemble(), _background(), baseline(), draw_scene(), main(), mix_at_snr(), noise_bed(), _pool_parts() (+30 more)

### Community 8 - "croptrack.py"
Cohesion: 0.14
Nodes (22): Regression tests for croptrack smoothing (Fix C) — pure, no video needed., Target jumps 540px (speaker switch, no scene-cut flag because Haar     missed th, 200px/s ramp: error-proportional gain must keep lag < crop margin., _t(), test_absence_holds_last_position(), test_fast_pan_tracked_with_bounded_lag(), test_jitter_is_smoothed(), test_scene_cut_with_face_snaps_immediately() (+14 more)

### Community 9 - "Review report"
Cohesion: 0.29
Nodes (6): Caption quality, Review report, Risks / notes for the human, Runtime & pacing, Structure match, Verdict

### Community 10 - "Review report"
Cohesion: 0.29
Nodes (6): Caption quality, Review report, Risks / notes for the human, Runtime & pacing, Structure match, Verdict

### Community 11 - "Upload kit"
Cohesion: 0.33
Nodes (5): Description, Tags, Thumbnail, Titles, Upload kit

### Community 12 - "Plan: Three lessons from my first 30 days of daily vlogging"
Cohesion: 0.33
Nodes (5): Plan: Three lessons from my first 30 days of daily vlogging, Short-form angle, Shot list, Structure, Talking points

### Community 13 - "fillers.py"
Cohesion: 0.40
Nodes (4): detect_fillers(), _norm(), Filler-word detection on word-level whisper output., Return [{'start','end','word','why'}] intervals to cut.      - unconditional fil

### Community 14 - "silence.py"
Cohesion: 0.14
Nodes (19): ndarray, Path, Regression tests for the adaptive silence-threshold rescue (Fix B)., Bed at -28dB, speech at -14dB: fixed -35 can never fire; the rescue     threshol, Floor within 8dB of speech: rescue must decline (returns fixed) so     silence r, _speech_like(), test_adaptive_disabled_flag(), test_clean_floor_keeps_fixed_threshold() (+11 more)

### Community 15 - "transcribe.py"
Cohesion: 0.33
Nodes (4): Path, Local word-level transcription with faster-whisper (no API calls)., Return [{'word', 'start', 'end', 'prob'}] with word-level timestamps., transcribe_words()

### Community 16 - "Edit report"
Cohesion: 0.40
Nodes (4): Cuts cancelled to protect pacing, Edit report, Kept segments, What was cut and why

### Community 19 - "report.py"
Cohesion: 0.38
Nodes (9): _esc(), _fmt_t(), generate(), _inline(), _md_to_html(), _parse_srt(), Path, Self-contained run report: runs/<name>/report.html.  Single offline HTML file (i (+1 more)

### Community 20 - "Engine stress-test report"
Cohesion: 0.18
Nodes (10): 1. Trailing/leading dead air survived edits (boundary_silence — genuine bug), 2. Silence detection blind under music beds (music — genuine bug, two layers), 3. Slow re-acquire after hard cuts (alternation — genuine bug), 4. Motion centroid chased camera motion (handheld — genuine bug, one dead end), Documented fallback behaviors (now tested, not just intended), Engine stress-test report, Remaining known limitations, Results after hardening (all 28 metrics pass) (+2 more)

### Community 21 - "Edit report"
Cohesion: 0.40
Nodes (4): Cuts cancelled to protect pacing, Edit report, Kept segments, What was cut and why

### Community 22 - "Edit report"
Cohesion: 0.50
Nodes (3): Edit report, Kept segments, What was cut and why

### Community 23 - "Edit report"
Cohesion: 0.50
Nodes (3): Edit report, Kept segments, What was cut and why

### Community 24 - "Edit report"
Cohesion: 0.50
Nodes (3): Edit report, Kept segments, What was cut and why

### Community 25 - "Edit report"
Cohesion: 0.50
Nodes (3): Edit report, Kept segments, What was cut and why

### Community 26 - "Edit report"
Cohesion: 0.50
Nodes (3): Edit report, Kept segments, What was cut and why

### Community 27 - "Edit report"
Cohesion: 0.50
Nodes (3): Edit report, Kept segments, What was cut and why

### Community 28 - "Edit report"
Cohesion: 0.50
Nodes (3): Edit report, Kept segments, What was cut and why

## Knowledge Gaps
- **56 isolated node(s):** `vlog-pipeline`, `What it produces`, `Model routing`, `The edit engine (stage 3–4, all local signal analysis)`, `Install` (+51 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Config` connect `RunState` to `Config`, `cli.py`, `edit.py`, `highlights.py`?**
  _High betweenness centrality (0.100) - this node is a cross-community bridge._
- **Why does `StageError` connect `edit.py` to `cli.py`, `RunState`?**
  _High betweenness centrality (0.039) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `Config` (e.g. with `Metric` and `ScenarioResult`) actually correct?**
  _`Config` has 2 INFERRED edges - model-reasoned connections that need verification._
- **What connects `vlog-pipeline`, `Regression tests for croptrack smoothing (Fix C) — pure, no video needed.`, `Target jumps 540px (speaker switch, no scene-cut flag because Haar     missed th` to the rest of the system?**
  _129 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `cli.py` be split into smaller, more focused modules?**
  _Cohesion score 0.12121212121212122 - nodes in this community are weakly interconnected._
- **Should `edit.py` be split into smaller, more focused modules?**
  _Cohesion score 0.09898242368177614 - nodes in this community are weakly interconnected._
- **Should `highlights.py` be split into smaller, more focused modules?**
  _Cohesion score 0.09057971014492754 - nodes in this community are weakly interconnected._