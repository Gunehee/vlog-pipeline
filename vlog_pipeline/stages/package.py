"""Stage 5 — package (Sonnet, metered): review final cut against the plan."""
from __future__ import annotations

import json
from pathlib import Path

from . import StageError
from ..llm import run_claude, api_key_present

PROMPT = """You are reviewing an automated vlog edit. Compare the final cut against the original plan and write a quality review.

## Original plan
{plan}

## Edit report (what the engine actually did)
{edit_report}

## Final caption text (the actual content of the cut)
{caption_text}

## Export facts
{facts}

Respond with a markdown review document (text only) with sections:
# Review report
## Verdict  (one line: SHIP / SHIP WITH NOTES / RECUT, plus a sentence)
## Structure match  (does the cut deliver the plan's hook/body/CTA? cite caption text)
## Runtime & pacing  (is the edited runtime and cut density appropriate? use the numbers)
## Caption quality  (readability of the caption lines shown)
## Risks / notes for the human
Keep it under 400 words, concrete, no fluff. Output ONLY the markdown."""


def run(ctx: dict) -> tuple[list[str], list[str], float]:
    run_dir: Path = ctx["run_dir"]
    out = run_dir / "review-report.md"
    if not api_key_present() or ctx.get("skip_llm"):
        out.write_text("# Review report\n\n_LLM stage skipped._\n")
        return [str(out)], ["skipped (no API key or --skip-llm)"], 0.0

    plan = (run_dir / "plan.md").read_text()[:3000]
    edit_report = (run_dir / "edit-report.md").read_text()[:4000]
    srt = (run_dir / "captions.srt").read_text()
    caption_text = " ".join(
        l for l in srt.splitlines()
        if l.strip() and not l.strip().isdigit() and "-->" not in l)[:2500]
    decisions = json.loads((run_dir / "edit-decisions.json").read_text())
    facts = json.dumps({
        "original_duration_sec": decisions["cutlist"]["original_duration"],
        "edited_duration_sec": decisions["cutlist"]["edited_duration"],
        "cuts": len(decisions["cutlist"]["removed"]),
        "short_window_sec": decisions["highlight"]["window_duration"],
    })

    text, cost = run_claude(
        PROMPT.format(plan=plan, edit_report=edit_report,
                      caption_text=caption_text, facts=facts),
        model="sonnet")
    if len(text.strip()) < 150 or "## Verdict" not in text:
        raise StageError("review output failed validation (missing Verdict)")
    out.write_text(text.strip() + "\n")
    verdict = next((l for l in text.splitlines()
                    if l.strip() and not l.startswith("#")), "?")
    return [str(out)], [f"review written; verdict: {verdict.strip()[:80]}"], cost
