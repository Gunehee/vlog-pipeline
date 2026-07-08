"""Stage 6 — optimize (Haiku, metered): titles, thumbnail text, description, tags."""
from __future__ import annotations

from pathlib import Path

from . import StageError
from ..llm import run_claude, api_key_present

PROMPT = """A creator just finished editing a video. Generate upload metadata.

TOPIC: {topic}

TRANSCRIPT (from the final cut):
{transcript}

Write markdown with exactly these sections:
# Upload kit
## Titles
5 title variants (mix curiosity/benefit/direct styles), <=70 chars each.
## Thumbnail
One thumbnail concept: 2-4 word overlay text + one-line visual direction.
## Description
A YouTube description (~120 words) with a hook first line.
## Tags
12-15 comma-separated tags.

Output ONLY the markdown."""


def run(ctx: dict) -> tuple[list[str], list[str], float]:
    run_dir: Path = ctx["run_dir"]
    out = run_dir / "optimize.md"
    if not api_key_present() or ctx.get("skip_llm"):
        if out.exists() and "_LLM stage skipped._" not in out.read_text():
            return ([str(out)],
                    ["LLM optimize skipped — kept existing optimize.md"],
                    ctx.get("prev_cost", 0.0))
        out.write_text("# Upload kit\n\n_LLM stage skipped._\n")
        return [str(out)], ["skipped (no API key or --skip-llm)"], 0.0

    srt = (run_dir / "captions.srt").read_text()
    transcript = " ".join(
        l for l in srt.splitlines()
        if l.strip() and not l.strip().isdigit() and "-->" not in l)[:2500]

    text, cost = run_claude(
        PROMPT.format(topic=ctx["topic"], transcript=transcript), model="haiku")
    if "## Titles" not in text or "## Tags" not in text:
        raise StageError("optimize output failed validation (missing sections)")
    out.write_text(text.strip() + "\n")
    return [str(out)], [f"optimize.md written ({len(text)} chars)"], cost
