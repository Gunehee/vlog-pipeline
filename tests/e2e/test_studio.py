"""Studio E2E against the committed day30-vlog run. Zero LLM calls.

Run:  python3 -m pytest tests/e2e -m e2e -v   (needs: playwright install chromium,
      the day30-vlog run present, and the original footage on this machine —
      regenerate with `python3 tools/make_test_clip.py testdata/raw-vlog.mp4`).

Every assertion is a measured number (durations via ffprobe, audio via RMS,
frames via pixel diff), not a vibe. Repo artifacts touched by exports are
snapshotted and restored by the session fixture.
"""
import json
import math
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from vlog_pipeline import review as rv  # noqa: E402

pytestmark = [pytest.mark.e2e, pytest.mark.slow]

RUN = ROOT / "runs/day30-vlog"
PORT = 5601
BASE = f"http://127.0.0.1:{PORT}"
PRESERVE = ["captions.srt", "report.html", "review-state.json"]

playwright = pytest.importorskip("playwright.sync_api")


def _ffprobe_duration(p):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries",
         "stream=duration", "-of", "csv=p=0", str(p)],
        capture_output=True, text=True).stdout.strip()
    return float(out)


def _rms_db_at(video, t, win=0.2):
    """Mean RMS (dBFS) of a small audio window of the file."""
    proc = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", f"{max(0, t - win / 2):.3f}",
         "-t", f"{win:.3f}", "-i", str(video), "-vn", "-ac", "1",
         "-ar", "16000", "-f", "s16le", "-"], capture_output=True)
    x = np.frombuffer(proc.stdout, dtype=np.int16).astype(np.float32) / 32768
    if not len(x):
        return -120.0
    return 20 * math.log10(float(np.sqrt(np.mean(x ** 2))) + 1e-9)


def _grab_gray(video, t):
    with tempfile.NamedTemporaryFile(suffix=".raw") as f:
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.3f}", "-i", str(video),
             "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "gray",
             "-s", "480x270", f.name], check=True)
        return np.fromfile(f.name, dtype=np.uint8).astype(np.float32)


@pytest.fixture(scope="session")
def studio():
    if not RUN.exists():
        pytest.skip("day30-vlog run not present")
    footage = json.loads((RUN / "state.json").read_text())["footage"]
    if not Path(footage).exists():
        pytest.skip("original footage missing — regenerate with tools/make_test_clip.py")

    # snapshot repo artifacts that exports overwrite
    snap = Path(tempfile.mkdtemp(prefix="e2e-snap-"))
    for name in PRESERVE:
        if (RUN / name).exists():
            shutil.copy(RUN / name, snap / name)
    shutil.copytree(RUN / "thumbnails", snap / "thumbnails")
    (RUN / "review-state.json").unlink(missing_ok=True)

    proc = subprocess.Popen(
        [sys.executable, "-m", "vlog_pipeline.cli", "ui", "--no-browser",
         "--port", str(PORT)],
        cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(60):
        try:
            socket.create_connection(("127.0.0.1", PORT), 0.3).close()
            break
        except OSError:
            time.sleep(0.25)
    else:
        proc.kill()
        pytest.fail("studio server did not start")

    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(f"{BASE}/#/run/day30-vlog")
        page.wait_for_selector('[data-testid="timeline"]')
        page.wait_for_function(
            "document.querySelector('video') && document.querySelector('video').readyState >= 2")
        yield page
        browser.close()

    proc.terminate()
    proc.wait(timeout=10)
    # restore repo artifacts
    for name in PRESERVE:
        (RUN / name).unlink(missing_ok=True)
        if (snap / name).exists():
            shutil.copy(snap / name, RUN / name)
    shutil.rmtree(RUN / "thumbnails")
    shutil.copytree(snap / "thumbnails", RUN / "thumbnails")
    shutil.rmtree(snap)


def _export_via_ui(page, timeout=600_000):
    page.click('[data-testid="open-export"]')
    page.wait_for_selector('[data-testid="start-export"]')
    page.click('[data-testid="start-export"]')
    page.wait_for_function(
        "['Export complete','Export failed'].some(s => "
        "document.querySelector('[data-testid=export-status]')?.textContent.includes(s))",
        timeout=timeout)
    status = page.locator('[data-testid="export-status"]').inner_text()
    log = page.locator('[data-testid="export-log"]').inner_text()
    assert "complete" in status, f"export failed:\n{log}"
    page.keyboard.press("Escape")


def test_preview_skip_accuracy(studio):
    """Segment-skip preview: entry overshoot and landing within 50ms."""
    page = studio
    dec = json.loads((RUN / "edit-decisions.json").read_text())
    cut = dec["cutlist"]["removed"][1]
    a, e = cut["start"], cut["end"]
    res = page.evaluate("""async ([a, e]) => {
      const v = document.querySelector('video');
      v.__skipLog = [];
      v.currentTime = a - 0.8;
      await new Promise(r => { v.onseeked = r; });
      await v.play();
      const t0 = performance.now();
      const samples = [];
      await new Promise(res => {
        const iv = setInterval(() => {
          samples.push(v.currentTime);
          if (v.currentTime > e + 0.5 || performance.now() - t0 > 5000) {
            clearInterval(iv); v.pause(); res();
          }
        }, 8);
      });
      return {samples, skips: v.__skipLog};
    }""", [a, e])
    assert res["skips"], "no skip event fired"
    overshoot = max(s["from"] - a for s in res["skips"])
    landing = min(abs(s["to"] - e) for s in res["skips"])
    dwell = [t for t in res["samples"] if a + 0.05 < t < e - 0.05]
    print(f"overshoot {overshoot*1000:.0f}ms landing {landing*1000:.0f}ms dwell {len(dwell)}")
    assert overshoot <= 0.05 and landing <= 0.05 and not dwell


def test_decisions_export_duration_and_rejected_audio(studio):
    """Toggle cuts off + nudge + manual cut -> export == prediction ±0.1s,
    and a rejected filler's audio is verifiably present in the export."""
    page = studio

    # reject two filler cuts (e0 'um' @1.56, e3 'uh' @10.40), nudge e1, manual cut
    for cid in ("e0", "e3"):
        page.click(f'[data-cut="{cid}"]')
        page.click('[data-testid="inspector-toggle"]')
    page.click('[data-cut="e1"]')
    page.click('[data-testid="nudge-start-left"]')  # -50ms
    page.click('[data-testid="add-cut-mode"]')
    tl = page.locator('[data-testid="timeline"]').bounding_box()
    y = tl["y"] + 60
    page.mouse.move(tl["x"] + tl["width"] * 0.62, y)
    page.mouse.down()
    page.mouse.move(tl["x"] + tl["width"] * 0.64, y, steps=5)
    page.mouse.up()
    page.wait_for_timeout(1100)  # autosave

    _export_via_ui(page)

    dec = json.loads((RUN / "edit-decisions.json").read_text())
    ing = json.loads((RUN / "ingest-report.json").read_text())
    review = rv.load_review(RUN)
    assert review["cuts"]["e0"]["status"] == "rejected"
    assert len(review["manual_cuts"]) == 1
    predicted = rv.predicted_duration(dec["cutlist"], review,
                                      ing["duration_sec"], ing["video"]["fps"])
    exported = _ffprobe_duration(RUN / "final/long-169.mp4")
    print(f"exported {exported:.3f}s predicted {predicted:.3f}s "
          f"delta {(exported-predicted)*1000:+.0f}ms")
    assert abs(exported - predicted) <= 0.1

    # rejected 'um' (originally cut at 1.56-1.66) must be audible at its
    # mapped position in the export
    kept = rv.effective_kept(dec["cutlist"], review, ing["duration_sec"])
    t_um = rv.map_orig_to_edit(1.61, kept)
    assert t_um is not None, "rejected cut region not mapped into the export"
    db = _rms_db_at(RUN / "final/long-169.mp4", t_um)
    print(f"audio at mapped 'um' position ({t_um:.2f}s): {db:.1f} dBFS")
    assert db > -35, "rejected filler region is silent — content not restored"


def test_caption_edit_changes_srt_and_burned_frame(studio):
    """Edit one caption line -> new .srt contains it AND the burned pixels at
    that caption's midpoint change vs the previous export."""
    page = studio
    marker = "E2E VERIFIED CAPTION"

    # target: caption line index 6 (well inside kept content)
    page.click('[data-testid="tab-captions"]')
    page.wait_for_selector('[data-testid="cap-6"]')
    page.dblclick('[data-testid="cap-6"] .cap-text')
    page.fill('[data-testid="cap-input-6"]', marker)
    page.keyboard.press("Enter")
    # wait for the autosave to actually land on disk (debounce + write)
    for _ in range(40):
        review = rv.load_review(RUN)
        if review["captions"] and any(l["text"] == marker for l in review["captions"]):
            break
        time.sleep(0.25)
    else:
        pytest.fail("caption edit never persisted to review-state.json")
    line = next(l for l in review["captions"] if l["text"] == marker)
    dec = json.loads((RUN / "edit-decisions.json").read_text())
    ing = json.loads((RUN / "ingest-report.json").read_text())
    kept = rv.effective_kept(dec["cutlist"], review, ing["duration_sec"])
    mid = rv.map_orig_to_edit((line["start"] + line["end"]) / 2, kept)
    assert mid is not None

    pre = _grab_gray(RUN / "final/long-169.mp4", mid)  # export from previous test
    _export_via_ui(page)

    srt = (RUN / "captions.srt").read_text()
    assert marker in srt, "edited text missing from exported .srt"
    post = _grab_gray(RUN / "final/long-169.mp4", mid)
    diff = float(np.mean(np.abs(pre - post)))
    print(f"burned frame diff at caption midpoint ({mid:.2f}s): {diff:.2f}")
    assert diff > 1.0, "burned-in caption pixels did not change after the edit"
