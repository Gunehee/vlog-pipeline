"""Stage 1 — plan (Sonnet, metered): shot list + script + structure."""
from __future__ import annotations

from pathlib import Path

from . import StageError
from ..llm import run_claude, api_key_present

PROMPT = """You are a video producer. A creator is about to edit raw vlog footage on this topic:

TOPIC: {topic}

Write a concise production plan as markdown with exactly these sections:

# Plan: {topic}
## Structure
A hook / body / CTA breakdown with target timings for a 1-4 minute talking-head video.
## Shot list
5-8 shots/beats the edit should look for in the footage.
## Talking points
The key points a good cut on this topic should retain, in order.
## Short-form angle
Which single moment/idea would make the best <60s vertical clip and why.

Keep it under 450 words. Output ONLY the markdown document, no preamble."""


def run(ctx: dict) -> tuple[list[str], list[str], float]:
    run_dir: Path = ctx["run_dir"]
    out = run_dir / "plan.md"
    if not api_key_present() or ctx.get("skip_llm"):
        if out.exists() and "_LLM stage skipped" not in out.read_text():
            return ([str(out)], ["LLM plan skipped — kept existing plan.md"],
                    ctx.get("prev_cost", 0.0))
        out.write_text(f"# Plan: {ctx['topic']}\n\n"
                       "_LLM stage skipped (no ANTHROPIC_API_KEY or --skip-llm); "
                       "edit proceeds without a generated plan._\n")
        return [str(out)], ["skipped (no API key or --skip-llm)"], 0.0

    text, cost = run_claude(PROMPT.format(topic=ctx["topic"]), model="sonnet")
    if len(text.strip()) < 200 or "## Structure" not in text:
        raise StageError(f"plan output failed validation (len={len(text)}, "
                         "missing '## Structure' section)")
    out.write_text(text.strip() + "\n")
    return [str(out)], [f"plan.md written ({len(text)} chars, structure present)"], cost
