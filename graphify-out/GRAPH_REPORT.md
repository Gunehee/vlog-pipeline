# Graph Report - vlog-pipeline  (2026-07-10)

## Corpus Check
- 105 files · ~146,773 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 810 nodes · 1772 edges · 56 communities (49 shown, 7 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 110 edges (avg confidence: 0.51)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `9297161c`
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
- [[_COMMUNITY_r|r]]
- [[_COMMUNITY_index-C5MCGBv5.js|index-C5MCGBv5.js]]
- [[_COMMUNITY_hf|hf]]
- [[_COMMUNITY_gs|gs]]
- [[_COMMUNITY_lr|lr]]
- [[_COMMUNITY_zo|zo]]
- [[_COMMUNITY_Jl|Jl]]
- [[_COMMUNITY_studio_server.py|studio_server.py]]
- [[_COMMUNITY_t|t]]
- [[_COMMUNITY_ve|ve]]
- [[_COMMUNITY_package.json|package.json]]
- [[_COMMUNITY_test_studio.py|test_studio.py]]
- [[_COMMUNITY_Tokens|Tokens]]
- [[_COMMUNITY_$e|$e]]
- [[_COMMUNITY_Na|Na]]
- [[_COMMUNITY_Nl|Nl]]
- [[_COMMUNITY_be|be]]
- [[_COMMUNITY_op|op]]
- [[_COMMUNITY_ll|ll]]
- [[_COMMUNITY_Xt|Xt]]
- [[_COMMUNITY_Qo|Qo]]
- [[_COMMUNITY_Bl|Bl]]
- [[_COMMUNITY_Dp|Dp]]
- [[_COMMUNITY_pp|pp]]

## God Nodes (most connected - your core abstractions)
1. `Config` - 39 edges
2. `hf()` - 30 edges
3. `t()` - 25 edges
4. `r()` - 23 edges
5. `StageError` - 22 edges
6. `Jl()` - 22 edges
7. `mc()` - 22 edges
8. `n()` - 21 edges
9. `l()` - 17 edges
10. `b()` - 17 edges

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

## Communities (56 total, 7 thin omitted)

### Community 0 - "Config"
Cohesion: 0.07
Nodes (53): At(), b(), bf(), Bn(), Cc(), Cn(), ct(), dc() (+45 more)

### Community 1 - "cli.py"
Cohesion: 0.11
Nodes (22): _billing_table(), cmd_run(), cmd_status(), cmd_stress(), cmd_ui(), main(), vlog-pipeline CLI: run / status., api_key_present() (+14 more)

### Community 2 - "edit.py"
Cohesion: 0.05
Nodes (87): CompletedProcess, RuntimeError, Full-suite regression: every stress scenario must pass its metric gates.  Slow (, test_scenario(), Config, Pipeline configuration with editing thresholds and model routing., build_cutlist(), _complement() (+79 more)

### Community 3 - "captions.py"
Cohesion: 0.06
Nodes (32): Unit tests for the studio review-decision overlay (pure logic, no media)., build_lines(), _flush(), Path, Caption line building + SRT/ASS emission with platform-aware styling., Render each caption line to a styled transparent PNG for ffmpeg overlay.      St, Group word timestamps into readable caption lines., render_caption_pngs() (+24 more)

### Community 4 - "RunState"
Cohesion: 0.09
Nodes (31): api, watchJob(), App(), parseHash(), CaptionEditor(), CutList(), ExportModal(), Library() (+23 more)

### Community 5 - "highlights.py"
Cohesion: 0.14
Nodes (9): Unit regression tests for cutlist assembly + pacing guard (no media needed)., Regression: silencedetect's end sits a few ms short of the container     duratio, Mirror case: silence starts a few ms after 0 (decoder priming)., Two silences separated by a 0.25s sound burst: the kept island is     0.25 + 2*k, silencedetect start without end (file ends inside silence)., test_leading_silence_with_container_padding_at_start(), test_open_ended_trailing_silence(), test_pacing_guard_restores_midclip_cut_for_short_segment() (+1 more)

### Community 6 - "vlog-pipeline"
Cohesion: 0.20
Nodes (9): Current limitations (post-hardening, measured), Engine hardening (stress suite), Install, Model routing, Proof: real end-to-end run, The edit engine (stage 3–4, all local signal analysis), The review studio, vlog-pipeline (+1 more)

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

### Community 31 - "r"
Cohesion: 0.12
Nodes (33): ad(), Au(), Bu(), C(), cs(), er(), Eu(), f() (+25 more)

### Community 32 - "index-C5MCGBv5.js"
Cohesion: 0.06
Nodes (3): bc, mp, Un

### Community 33 - "hf"
Cohesion: 0.12
Nodes (24): ao(), Dn(), fl(), fp(), Fu(), hf(), ic(), ii() (+16 more)

### Community 34 - "gs"
Cohesion: 0.11
Nodes (22): Ar(), cd(), dd(), ec(), fo(), gs(), Gu(), ho() (+14 more)

### Community 35 - "lr"
Cohesion: 0.14
Nodes (21): _a(), Bt(), Et(), Fi(), Go(), Gr(), I(), Ie() (+13 more)

### Community 36 - "zo"
Cohesion: 0.15
Nodes (21): Ba(), Bi(), dl(), Fe(), ha(), He(), La(), Ne() (+13 more)

### Community 37 - "Jl"
Cohesion: 0.15
Nodes (20): aa(), af(), ca(), cf(), da(), Eo(), ff(), Fs() (+12 more)

### Community 38 - "studio_server.py"
Cohesion: 0.22
Nodes (12): FastAPI, create_app(), _export_job(), Job, _load_json(), Path, Local review-studio server: FastAPI + the committed web build. Fully offline at, 2400-bin peak envelope of the original footage, cached in work/. (+4 more)

### Community 39 - "t"
Cohesion: 0.15
Nodes (16): Cl(), co(), hc(), Hu(), Jc(), ku(), lu(), nu() (+8 more)

### Community 40 - "ve"
Cohesion: 0.17
Nodes (15): Do(), Dt(), ea(), Es(), hi(), Is(), ja(), lc() (+7 more)

### Community 41 - "package.json"
Cohesion: 0.14
Nodes (13): dependencies, react, react-dom, devDependencies, vite, @vitejs/plugin-react, name, private (+5 more)

### Community 42 - "test_studio.py"
Cohesion: 0.20
Nodes (12): _export_via_ui(), _ffprobe_duration(), _grab_gray(), Studio E2E against the committed day30-vlog run. Zero LLM calls.  Run:  python3, Segment-skip preview: entry overshoot and landing within 50ms., Toggle cuts off + nudge + manual cut -> export == prediction ±0.1s,     and a re, Edit one caption line -> new .srt contains it AND the burned pixels at     that, Mean RMS (dBFS) of a small audio window of the file. (+4 more)

### Community 43 - "Tokens"
Cohesion: 0.15
Nodes (12): Color — accent & status, Color — cut-reason categorical (reused from report.html, CVD-validated dark set), Color — surfaces & ink, Component conventions, Direction, Interaction states (uniform everywhere), Layout architecture, Quality bar checklist (applied before every phase gate) (+4 more)

### Community 44 - "$e"
Cohesion: 0.33
Nodes (7): Ds(), $e(), Ga(), Ka(), ni(), ri(), Xa()

### Community 45 - "Na"
Cohesion: 0.29
Nodes (7): K(), Na(), or(), Po(), sa(), wd(), Zl()

### Community 46 - "Nl"
Cohesion: 0.33
Nodes (6): Du(), md(), Nl(), Nr(), Ou(), yf()

### Community 47 - "be"
Cohesion: 0.50
Nodes (4): be(), Bo(), Qr(), vo()

### Community 48 - "op"
Cohesion: 0.50
Nodes (4): gp(), jp(), op(), zp()

### Community 49 - "ll"
Cohesion: 0.50
Nodes (4): ll(), Qa(), vs(), Wr()

### Community 50 - "Xt"
Cohesion: 0.67
Nodes (3): gn(), Lt(), Xt()

## Knowledge Gaps
- **82 isolated node(s):** `vlog-pipeline`, `name`, `private`, `version`, `type` (+77 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **7 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Config` connect `edit.py` to `cli.py`, `highlights.py`, `studio_server.py`?**
  _High betweenness centrality (0.030) - this node is a cross-community bridge._
- **Why does `StageError` connect `edit.py` to `cli.py`, `studio_server.py`?**
  _High betweenness centrality (0.011) - this node is a cross-community bridge._
- **Are the 4 inferred relationships involving `Config` (e.g. with `ExportError` and `Metric`) actually correct?**
  _`Config` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Are the 13 inferred relationships involving `t()` (e.g. with `co()` and `cs()`) actually correct?**
  _`t()` has 13 INFERRED edges - model-reasoned connections that need verification._
- **Are the 15 inferred relationships involving `r()` (e.g. with `Bu()` and `Cn()`) actually correct?**
  _`r()` has 15 INFERRED edges - model-reasoned connections that need verification._
- **What connects `vlog-pipeline`, `name`, `private` to the rest of the system?**
  _172 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Config` be split into smaller, more focused modules?**
  _Cohesion score 0.06734006734006734 - nodes in this community are weakly interconnected._