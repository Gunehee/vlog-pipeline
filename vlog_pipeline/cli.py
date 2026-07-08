"""vlog-pipeline CLI: run / status."""
from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

from . import __version__
from .config import Config, STAGE_ORDER, STAGE_ROUTING
from .llm import api_key_present
from .state import RunState
from .stages import StageError
from .stages import plan, ingest, edit, caption, package, optimize

STAGE_FUNCS = {
    "plan": plan.run, "ingest": ingest.run, "edit": edit.run,
    "caption": caption.run, "package": package.run, "optimize": optimize.run,
}


def _billing_table(skip_llm: bool):
    key = api_key_present()
    print("\n=== Model routing & billing (read before you pay) " + "=" * 24)
    print(f"{'stage':<10} {'model':<8} {'engine':<52} billing")
    for s in STAGE_ORDER:
        model, engine, billing = STAGE_ROUTING[s]
        if model != "-" and (skip_llm or not key):
            billing = "SKIPPED (" + ("--skip-llm" if skip_llm else "no ANTHROPIC_API_KEY") + ")"
        print(f"{s:<10} {model:<8} {engine:<52} {billing}")
    print()
    if key and not skip_llm:
        print("NOTE: plan/package/optimize spawn headless `claude -p` subprocesses.")
        print("      With ANTHROPIC_API_KEY set these bill the METERED API — they are")
        print("      NOT covered by an interactive session's subscription quota.")
        print("      edit/caption (the expensive engine) are fully local: repeat runs")
        print("      cost $0 in LLM calls.")
    print("=" * 74 + "\n")


def cmd_run(args) -> int:
    footage = Path(args.footage).resolve()
    if not footage.exists():
        print(f"error: footage not found: {footage}", file=sys.stderr)
        return 1
    name = args.name or re.sub(r"[^a-z0-9-]+", "-", footage.stem.lower()).strip("-")
    run_dir = Path("runs") / name
    cfg = Config(whisper_model=args.whisper_model,
                 silence_db=args.silence_db, min_silence=args.min_silence)

    _billing_table(args.skip_llm)
    print(f"run:     {name}")
    print(f"footage: {footage}")
    print(f"topic:   {args.topic}\n")

    state = RunState(run_dir, str(footage), args.topic)
    ctx = {"run_dir": run_dir, "footage": footage, "topic": args.topic,
           "cfg": cfg, "skip_llm": args.skip_llm}

    stages_to_run = STAGE_ORDER
    if args.only:
        if args.only not in STAGE_ORDER:
            print(f"error: unknown stage '{args.only}' (choose from "
                  f"{', '.join(STAGE_ORDER)})", file=sys.stderr)
            return 1
        stages_to_run = [args.only]
        print(f"(--only: running just the '{args.only}' stage against "
              f"existing run artifacts)\n")

    t0 = time.time()
    for stage_name in stages_to_run:
        func = STAGE_FUNCS[stage_name]
        print(f"--- {stage_name} " + "-" * (60 - len(stage_name)))
        ctx["prev_cost"] = state.stage(stage_name).get("cost_usd", 0.0)
        state.start(stage_name)
        try:
            outputs, notes, cost = func(ctx)
        except StageError as e:
            state.fail(stage_name, str(e))
            print(f"    FAILED: {e}", file=sys.stderr)
            print(f"\nrun aborted at stage '{stage_name}' (stage gate). "
                  f"See runs/{name}/state.json", file=sys.stderr)
            return 2
        except Exception as e:  # noqa: BLE001 — record any crash in state
            state.fail(stage_name, f"{type(e).__name__}: {e}")
            print(f"    CRASHED: {type(e).__name__}: {e}", file=sys.stderr)
            return 2
        state.finish(stage_name, outputs, notes, cost)
        for n in notes:
            print(f"    ok: {n}")
        cost_str = f", ${cost:.4f}" if cost else ""
        print(f"    ({state.stage(stage_name)['seconds']}s{cost_str})")

    wall = time.time() - t0
    m, s = divmod(int(wall), 60)
    print("\n=== Done " + "=" * 65)
    print(f"wall-clock: {m}m{s:02d}s   metered LLM cost: ${state.total_cost():.4f}")
    print(f"outputs in: runs/{name}/")
    for label, p in [("long-form 16:9", f"runs/{name}/final/long-169.mp4"),
                     ("shorts 9:16", f"runs/{name}/final/short-916.mp4"),
                     ("captions", f"runs/{name}/captions.srt"),
                     ("edit report", f"runs/{name}/edit-report.md"),
                     ("review", f"runs/{name}/review-report.md"),
                     ("upload kit", f"runs/{name}/optimize.md"),
                     ("report", f"runs/{name}/report.html")]:
        print(f"  {label:<16} {p}")
    return 0


def cmd_stress(args) -> int:
    from .stress import run_stress
    return run_stress(args.scenario, args.regen)


def cmd_status(args) -> int:
    runs_root = Path("runs")
    if not runs_root.exists():
        print("no runs yet")
        return 0
    dirs = sorted([d for d in runs_root.iterdir() if (d / "state.json").exists()],
                  key=lambda d: (d / "state.json").stat().st_mtime, reverse=True)
    if args.name:
        dirs = [d for d in dirs if d.name == args.name]
    if not dirs:
        print("no matching runs")
        return 0
    for d in dirs:
        st = RunState(d)
        print(f"\n{d.name}  (topic: {st.data.get('topic', '?')})")
        for sname in STAGE_ORDER:
            s = st.stage(sname)
            cost = f" ${s['cost_usd']:.4f}" if s.get("cost_usd") else ""
            extra = f" — {s['error'][:80]}" if s.get("error") else ""
            print(f"  {sname:<10} {s['status']:<8} {s.get('seconds', 0):>7}s{cost}{extra}")
        print(f"  {'total':<10} {'':8} metered ${st.total_cost():.4f}")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="vlog-pipeline",
        description="raw footage + topic -> edited, captioned, multi-format video package")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="run the full pipeline")
    r.add_argument("--footage", required=True)
    r.add_argument("--topic", required=True)
    r.add_argument("--name", help="run name (default: derived from footage filename)")
    r.add_argument("--skip-llm", action="store_true",
                   help="skip metered plan/package/optimize stages")
    r.add_argument("--only", metavar="STAGE",
                   help="re-run a single stage against existing run artifacts")
    r.add_argument("--whisper-model", default="small.en")
    r.add_argument("--silence-db", type=float, default=-35.0)
    r.add_argument("--min-silence", type=float, default=0.45)
    r.set_defaults(func=cmd_run)

    s = sub.add_parser("status", help="show state of runs")
    s.add_argument("--name")
    s.set_defaults(func=cmd_status)

    st = sub.add_parser(
        "stress",
        help="run engine stress scenarios vs generator ground truth ($0, local only)")
    st.add_argument("--scenario", action="append",
                    help="run only this scenario (repeatable)")
    st.add_argument("--regen", action="store_true",
                    help="regenerate scenario clips even if cached")
    st.set_defaults(func=cmd_stress)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
