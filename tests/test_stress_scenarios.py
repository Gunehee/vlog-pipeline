"""Full-suite regression: every stress scenario must pass its metric gates.

Slow (generates clips on first run, transcribes with local whisper, renders
cuts). Run explicitly:

    python3 -m pytest tests/test_stress_scenarios.py -m slow -v
    # or equivalently: vlog-pipeline stress

Marked `slow` so the default `pytest tests/` stays fast (unit tests only).
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vlog_pipeline.config import Config
from vlog_pipeline.stress import CHECKERS, ORDER, ensure_scenario

pytestmark = pytest.mark.slow


@pytest.mark.parametrize("name", ORDER)
def test_scenario(name):
    gt = ensure_scenario(name, regen=False)
    res = CHECKERS[name](gt, Config())
    failures = [f"{m.name}: measured {m.measured}, expected {m.threshold}"
                for m in res.metrics if not m.passed]
    assert not failures, f"{name}: " + "; ".join(failures)
