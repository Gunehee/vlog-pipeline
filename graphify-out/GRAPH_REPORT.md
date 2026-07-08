# Graph Report - vlog-pipeline  (2026-07-08)

## Corpus Check
- 33 files · ~29,538 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 188 nodes · 324 edges · 19 communities (18 shown, 1 thin omitted)
- Extraction: 99% EXTRACTED · 1% INFERRED · 0% AMBIGUOUS · INFERRED: 2 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `6b14fbb4`
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

## God Nodes (most connected - your core abstractions)
1. `StageError` - 19 edges
2. `Config` - 18 edges
3. `run()` - 12 edges
4. `RunState` - 11 edges
5. `stream_durations()` - 9 edges
6. `is_valid_media()` - 9 edges
7. `api_key_present()` - 9 edges
8. `run_claude()` - 9 edges
9. `render_cut()` - 8 edges
10. `burn_captions()` - 8 edges

## Surprising Connections (you probably didn't know these)
- `validate()` --references--> `Config`  [EXTRACTED]
  vlog_pipeline/engine/highlights.py → vlog_pipeline/config.py
- `cmd_run()` --calls--> `Config`  [EXTRACTED]
  vlog_pipeline/cli.py → vlog_pipeline/config.py
- `cmd_run()` --calls--> `RunState`  [EXTRACTED]
  vlog_pipeline/cli.py → vlog_pipeline/state.py
- `cmd_status()` --calls--> `RunState`  [EXTRACTED]
  vlog_pipeline/cli.py → vlog_pipeline/state.py
- `validate()` --references--> `Config`  [EXTRACTED]
  vlog_pipeline/engine/cutlist.py → vlog_pipeline/config.py

## Import Cycles
- None detected.

## Communities (19 total, 1 thin omitted)

### Community 0 - "Config"
Cohesion: 0.12
Nodes (25): CompletedProcess, Config, Pipeline configuration with editing thresholds and model routing., build_cutlist(), _complement(), map_time(), Cutlist assembly: merge silence + filler removals into a paced jump-cut EDL., Project word timestamps onto the edited timeline; drop cut words. (+17 more)

### Community 1 - "cli.py"
Cohesion: 0.15
Nodes (21): RuntimeError, _billing_table(), cmd_run(), cmd_status(), main(), vlog-pipeline CLI: run / status., api_key_present(), LLMError (+13 more)

### Community 2 - "edit.py"
Cohesion: 0.17
Nodes (21): extract_thumbnails(), extract_wav(), ffprobe_json(), is_valid_media(), Path, Thin ffmpeg/ffprobe wrappers used across stages., Return {'video': secs, 'audio': secs} decoded stream durations., Full-decode check: ffprobe metadata + ffmpeg null decode with no errors. (+13 more)

### Community 3 - "captions.py"
Cohesion: 0.24
Nodes (9): build_lines(), _flush(), Path, Caption line building + SRT/ASS emission with platform-aware styling., Render each caption line to a styled transparent PNG for ffmpeg overlay.      St, Group word timestamps into readable caption lines., render_caption_pngs(), _srt_ts() (+1 more)

### Community 4 - "RunState"
Cohesion: 0.31
Nodes (3): Path, Run state persisted to runs/<name>/state.json — the stage-gate ledger., RunState

### Community 5 - "highlights.py"
Cohesion: 0.33
Nodes (8): _norm(), ndarray, Path, Highlight scoring: audio energy + speech rate on the edited timeline., Score the edited cut and choose the best short-form window., _rms_curve(), score_highlights(), validate()

### Community 6 - "vlog-pipeline"
Cohesion: 0.25
Nodes (7): Current limitations, Install, Model routing, Proof: real end-to-end run, The edit engine (stage 3–4, all local signal analysis), vlog-pipeline, What it produces

### Community 7 - "make_test_clip.py"
Cohesion: 0.46
Nodes (7): draw_frame(), main(), ndarray, Path, Synthesize a talking-head test clip for the pipeline.  Audio: macOS `say` TTS, s, rms_per_frame(), synth_audio()

### Community 8 - "croptrack.py"
Cohesion: 0.29
Nodes (6): Path, Subject-tracking vertical crop: Haar face detection with a motion-centroid fallb, Track subject center-x across the highlight window of the edited cut.      Retur, Emit `t crop x N;` commands, deduping consecutive identical x values., track_crop(), write_sendcmd()

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
Cohesion: 0.33
Nodes (4): detect_silences(), Path, Silence/dead-air detection via ffmpeg silencedetect., Return [{'start': s, 'end': e, 'dur': d}] silence intervals.

### Community 15 - "transcribe.py"
Cohesion: 0.33
Nodes (4): Path, Local word-level transcription with faster-whisper (no API calls)., Return [{'word', 'start', 'end', 'prob'}] with word-level timestamps., transcribe_words()

### Community 16 - "Edit report"
Cohesion: 0.40
Nodes (4): Cuts cancelled to protect pacing, Edit report, Kept segments, What was cut and why

## Knowledge Gaps
- **28 isolated node(s):** `vlog-pipeline`, `What it produces`, `Model routing`, `The edit engine (stage 3–4, all local signal analysis)`, `Install` (+23 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Config` connect `Config` to `cli.py`, `edit.py`, `highlights.py`?**
  _High betweenness centrality (0.107) - this node is a cross-community bridge._
- **Why does `StageError` connect `cli.py` to `edit.py`?**
  _High betweenness centrality (0.072) - this node is a cross-community bridge._
- **Why does `RunState` connect `RunState` to `cli.py`?**
  _High betweenness centrality (0.061) - this node is a cross-community bridge._
- **What connects `vlog-pipeline`, `Synthesize a talking-head test clip for the pipeline.  Audio: macOS `say` TTS, s`, `vlog-pipeline CLI: run / status.` to the rest of the system?**
  _69 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Config` be split into smaller, more focused modules?**
  _Cohesion score 0.11822660098522167 - nodes in this community are weakly interconnected._