"""Headless `claude -p` subprocess calls for the Sonnet/Haiku text stages.

IMPORTANT billing note: these subprocesses bill against ANTHROPIC_API_KEY
(metered API) whenever that variable is set in the environment. They are NOT
covered by an interactive session's subscription quota. The CLI prints this
before running so it is never silent.
"""
from __future__ import annotations

import json
import os
import subprocess


class LLMError(RuntimeError):
    pass


def api_key_present() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def run_claude(prompt: str, model: str, timeout: int = 300) -> tuple[str, float]:
    """Run one headless prompt. Returns (text, cost_usd)."""
    cmd = [
        "claude", "-p",
        "--model", model,
        "--output-format", "json",
        "--max-turns", "1",
        "--tools", "",  # pure text generation: no tools, single turn
    ]
    # prompt goes via stdin: long prompts as argv make the CLI fail
    proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True,
                          timeout=timeout)
    if proc.returncode != 0:
        raise LLMError(f"claude -p ({model}) rc={proc.returncode}: {proc.stderr[-1500:]}")
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        raise LLMError(f"claude -p returned non-JSON: {proc.stdout[:500]}")
    if payload.get("is_error"):
        raise LLMError(f"claude -p error result: {payload.get('result', '')[:500]}")
    return payload.get("result", ""), float(payload.get("total_cost_usd") or 0.0)
