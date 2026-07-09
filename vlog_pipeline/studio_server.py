"""Local review-studio server: FastAPI + the committed web build. Fully
offline at runtime — no CDN, no external requests, zero LLM calls."""
from __future__ import annotations

import json
import queue
import subprocess
import threading
import time
import uuid
from pathlib import Path

import numpy as np
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import review as rv
from .config import Config, STAGE_ORDER

RUNS_ROOT = Path("runs")
WEBDIST = Path(__file__).parent / "webdist"

# settings the UI may pass to re-analyze (whitelist -> Config fields)
TUNABLE = {"silence_db": float, "min_silence": float, "min_segment": float,
           "keep_pad": float, "whisper_model": str}


class Job:
    def __init__(self, kind: str, run: str):
        self.id = uuid.uuid4().hex[:12]
        self.kind = kind
        self.run = run
        self.status = "running"
        self.lines: list[str] = []
        self.result: dict | None = None
        self.error: str | None = None
        self.q: queue.Queue = queue.Queue()

    def log(self, msg: str):
        self.lines.append(msg)
        self.q.put(("log", msg))

    def finish(self, result: dict):
        self.status = "done"
        self.result = result
        self.q.put(("done", result))

    def fail(self, error: str):
        self.status = "failed"
        self.error = error
        self.q.put(("failed", error))

    def snapshot(self) -> dict:
        return {"id": self.id, "kind": self.kind, "run": self.run,
                "status": self.status, "lines": self.lines,
                "result": self.result, "error": self.error}


JOBS: dict[str, Job] = {}


def _run_dir(name: str) -> Path:
    d = RUNS_ROOT / name
    if not (d / "state.json").exists():
        raise HTTPException(404, f"run '{name}' not found")
    return d


def _load_json(path: Path, what: str) -> dict:
    if not path.exists():
        raise HTTPException(409, f"{what} missing for this run — "
                                 "re-run the pipeline or re-analyze")
    return json.loads(path.read_text())


def _run_payload(name: str) -> dict:
    d = _run_dir(name)
    state = _load_json(d / "state.json", "state.json")
    decisions = _load_json(d / "edit-decisions.json", "edit-decisions.json")
    ingest = _load_json(d / "ingest-report.json", "ingest-report.json")
    review = rv.load_review(d)
    total = ingest["duration_sec"]
    cutlist = decisions["cutlist"]
    lines = review.get("captions") or rv.derive_caption_lines(d, cutlist)
    footage = Path(state["footage"])
    return {
        "name": name,
        "topic": state.get("topic", ""),
        "created": state.get("created", ""),
        "duration": total,
        "video": ingest.get("video", {}),
        "cutlist": cutlist,
        "cuts": rv.decisions_view(cutlist, review),
        "review": review,
        "captions": lines,
        "captions_customized": review.get("captions") is not None,
        "predicted_duration": rv.predicted_duration(cutlist, review, total),
        "engine_duration": cutlist["edited_duration"],
        "highlight": decisions.get("highlight", {}),
        "media": {
            "original": f"/media/{name}/original" if footage.exists() else None,
            "footage_path": str(footage),
        },
        "settings": {k: decisions.get("config", {}).get(k) for k in TUNABLE},
        "fillers": decisions.get("config", {}).get("_filler_note", None),
        "exports": {
            "long": f"runs/{name}/final/long-169.mp4"
            if (d / "final/long-169.mp4").exists() else None,
            "short": f"runs/{name}/final/short-916.mp4"
            if (d / "final/short-916.mp4").exists() else None,
            "report": f"runs/{name}/report.html"
            if (d / "report.html").exists() else None,
        },
    }


def _waveform(name: str) -> dict:
    """2400-bin peak envelope of the original footage, cached in work/."""
    d = _run_dir(name)
    state = _load_json(d / "state.json", "state.json")
    footage = Path(state["footage"])
    if not footage.exists():
        raise HTTPException(409, "original footage not on this machine")
    cache = d / "work" / "waveform.json"
    if cache.exists():
        data = json.loads(cache.read_text())
        if data.get("mtime") == footage.stat().st_mtime:
            return data
    proc = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(footage), "-vn", "-ac", "1",
         "-ar", "8000", "-f", "s16le", "-"], capture_output=True)
    x = np.abs(np.frombuffer(proc.stdout, dtype=np.int16).astype(np.float32))
    bins = 2400
    hop = max(1, len(x) // bins)
    peaks = [float(x[i * hop:(i + 1) * hop].max()) if len(x[i * hop:(i + 1) * hop])
             else 0.0 for i in range(bins)]
    top = max(peaks) or 1.0
    data = {"bins": bins, "duration": len(x) / 8000,
            "peaks": [round(p / top, 3) for p in peaks],
            "mtime": footage.stat().st_mtime}
    cache.parent.mkdir(exist_ok=True)
    cache.write_text(json.dumps(data))
    return data


def _reanalyze_job(job: Job, name: str, settings: dict):
    from .stages import StageError, edit, ingest
    d = RUNS_ROOT / name
    try:
        state = json.loads((d / "state.json").read_text())
        old = json.loads((d / "edit-decisions.json").read_text())
        review = rv.load_review(d)
        cfg_kwargs = {}
        for k, caster in TUNABLE.items():
            if k in settings and settings[k] is not None:
                cfg_kwargs[k] = caster(settings[k])
        cfg = Config(**cfg_kwargs)
        if isinstance(settings.get("fillers"), list):
            from .config import ALWAYS_FILLERS
            ALWAYS_FILLERS.clear()
            ALWAYS_FILLERS.update(w.strip().lower()
                                  for w in settings["fillers"] if w.strip())
        ctx = {"run_dir": d, "footage": Path(state["footage"]), "cfg": cfg,
               "topic": state.get("topic", ""), "skip_llm": True}
        job.log(f"re-analyzing with {cfg_kwargs or 'default settings'} ($0, local)...")
        job.log("ingest: probing + silence map...")
        ingest.run(ctx)
        job.log("edit: transcribe -> fillers -> cutlist -> render (takes ~1 min)...")
        edit.run(ctx)
        new = json.loads((d / "edit-decisions.json").read_text())
        new_review, stats = rv.match_decisions(
            old["cutlist"]["removed"], review, new["cutlist"]["removed"])
        rv.save_review(d, new_review)
        job.log(f"decisions carried over: {stats['inherited']} inherited, "
                f"{stats['new_unreviewed']} new suggestions marked unreviewed")
        job.finish({"stats": stats, "run": _run_payload(name)})
    except StageError as e:
        job.fail(f"engine gate: {e}")
    except Exception as e:  # noqa: BLE001 — surfaced to the UI, not swallowed
        job.fail(f"{type(e).__name__}: {e}")


def _export_job(job: Job, name: str):
    from .export import ExportError, export_run
    try:
        result = export_run(RUNS_ROOT / name, on_progress=job.log)
        job.finish(result)
    except ExportError as e:
        job.fail(str(e))
    except Exception as e:  # noqa: BLE001
        job.fail(f"{type(e).__name__}: {e}")


def create_app() -> FastAPI:
    app = FastAPI(title="vlog-pipeline studio", docs_url=None, redoc_url=None)

    @app.get("/api/runs")
    def list_runs():
        out = []
        if RUNS_ROOT.exists():
            for d in sorted(RUNS_ROOT.iterdir()):
                sp = d / "state.json"
                if not sp.exists() or not (d / "edit-decisions.json").exists():
                    continue
                state = json.loads(sp.read_text())
                dec = json.loads((d / "edit-decisions.json").read_text())
                footage = Path(state.get("footage", ""))
                out.append({
                    "name": d.name,
                    "topic": state.get("topic", ""),
                    "created": state.get("created", ""),
                    "original_duration": dec["cutlist"]["original_duration"],
                    "engine_duration": dec["cutlist"]["edited_duration"],
                    "cut_count": len(dec["cutlist"]["removed"]),
                    "reviewed": (d / "review-state.json").exists(),
                    "footage_available": footage.exists(),
                })
        return out

    @app.get("/api/runs/{name}")
    def get_run(name: str):
        return _run_payload(name)

    @app.put("/api/runs/{name}/review")
    async def put_review(name: str, request: Request):
        d = _run_dir(name)
        body = await request.json()
        if body.get("version") != rv.REVIEW_VERSION:
            raise HTTPException(400, "unknown review-state version")
        base = rv.default_review()
        base.update(body)
        rv.save_review(d, base)
        decisions = _load_json(d / "edit-decisions.json", "edit-decisions.json")
        ingest = _load_json(d / "ingest-report.json", "ingest-report.json")
        total = ingest["duration_sec"]
        return {
            "saved": True,
            "predicted_duration": rv.predicted_duration(
                decisions["cutlist"], base, total),
            "cuts": rv.decisions_view(decisions["cutlist"], base),
        }

    @app.post("/api/runs/{name}/review/reset")
    def reset_review(name: str):
        d = _run_dir(name)
        p = d / "review-state.json"
        if p.exists():
            p.unlink()
        return {"reset": True, "run": _run_payload(name)}

    @app.get("/api/runs/{name}/waveform")
    def waveform(name: str):
        return _waveform(name)

    @app.get("/media/{name}/original")
    def media(name: str):
        d = _run_dir(name)
        state = _load_json(d / "state.json", "state.json")
        footage = Path(state["footage"])
        if not footage.exists():
            raise HTTPException(404, "footage not on this machine")
        return FileResponse(footage, media_type="video/mp4")

    @app.post("/api/runs/{name}/reanalyze")
    async def reanalyze(name: str, request: Request):
        _run_dir(name)
        settings = await request.json()
        job = Job("reanalyze", name)
        JOBS[job.id] = job
        threading.Thread(target=_reanalyze_job, args=(job, name, settings),
                         daemon=True).start()
        return {"job": job.id}

    @app.post("/api/runs/{name}/export")
    async def export(name: str, request: Request):
        d = _run_dir(name)
        body = await request.json()
        review = rv.load_review(d)
        review["export"] = {**review.get("export", {}), **body.get("export", {})}
        if body.get("caption_preset"):
            review["caption_preset"] = body["caption_preset"]
        rv.save_review(d, review)
        job = Job("export", name)
        JOBS[job.id] = job
        threading.Thread(target=_export_job, args=(job, name),
                         daemon=True).start()
        return {"job": job.id}

    @app.get("/api/jobs/{jid}")
    def job_snapshot(jid: str):
        if jid not in JOBS:
            raise HTTPException(404, "unknown job")
        return JOBS[jid].snapshot()

    @app.get("/api/jobs/{jid}/events")
    def job_events(jid: str):
        if jid not in JOBS:
            raise HTTPException(404, "unknown job")
        job = JOBS[jid]

        def stream():
            for line in job.lines:  # replay history for late subscribers
                yield f"data: {json.dumps({'type': 'log', 'msg': line})}\n\n"
            if job.status != "running":
                yield ("data: " + json.dumps(
                    {"type": job.status, "result": job.result,
                     "error": job.error}) + "\n\n")
                return
            while True:
                try:
                    kind, payload = job.q.get(timeout=15)
                except queue.Empty:
                    yield ": heartbeat\n\n"
                    continue
                if kind == "log":
                    yield f"data: {json.dumps({'type': 'log', 'msg': payload})}\n\n"
                else:
                    yield ("data: " + json.dumps(
                        {"type": kind,
                         "result": payload if kind == "done" else None,
                         "error": payload if kind == "failed" else None})
                        + "\n\n")
                    return

        return StreamingResponse(stream(), media_type="text/event-stream")

    if RUNS_ROOT.exists():
        # report.html + its relative thumbnails/exports, straight from disk
        app.mount("/runs-static", StaticFiles(directory=RUNS_ROOT), name="runs")
    if WEBDIST.exists():
        app.mount("/", StaticFiles(directory=WEBDIST, html=True), name="web")
    return app


def serve(port: int = 5175, open_browser: bool = True, run: str | None = None):
    import webbrowser

    import uvicorn

    app = create_app()
    url = f"http://127.0.0.1:{port}/" + (f"#/run/{run}" if run else "")
    if open_browser:
        threading.Timer(0.9, webbrowser.open, [url]).start()
    print(f"vlog-pipeline studio: {url}  (Ctrl-C to stop; fully local, $0)")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
