"""Run state persisted to runs/<name>/state.json — the stage-gate ledger."""
from __future__ import annotations

import json
import time
from pathlib import Path

from .config import STAGE_ORDER


class RunState:
    def __init__(self, run_dir: Path, footage: str = "", topic: str = ""):
        self.run_dir = Path(run_dir)
        self.path = self.run_dir / "state.json"
        if self.path.exists():
            self.data = json.loads(self.path.read_text())
        else:
            self.data = {
                "footage": footage,
                "topic": topic,
                "created": time.strftime("%Y-%m-%d %H:%M:%S"),
                "stages": {
                    s: {"status": "pending", "outputs": [], "validation": [],
                        "cost_usd": 0.0, "seconds": 0.0}
                    for s in STAGE_ORDER
                },
            }
            self.save()

    def save(self):
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2))

    def stage(self, name: str) -> dict:
        return self.data["stages"][name]

    def start(self, name: str):
        st = self.stage(name)
        st["status"] = "running"
        st["_t0"] = time.time()
        self.save()

    def finish(self, name: str, outputs: list[str], validation: list[str],
               cost_usd: float = 0.0):
        st = self.stage(name)
        st["seconds"] = round(time.time() - st.pop("_t0", time.time()), 1)
        st["outputs"] = outputs
        st["validation"] = validation
        st["cost_usd"] = round(cost_usd, 4)
        st["status"] = "done"
        self.save()

    def fail(self, name: str, error: str):
        st = self.stage(name)
        st["seconds"] = round(time.time() - st.pop("_t0", time.time()), 1)
        st["status"] = "failed"
        st["error"] = error
        self.save()

    def total_cost(self) -> float:
        return sum(s.get("cost_usd", 0.0) for s in self.data["stages"].values())
