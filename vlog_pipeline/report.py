"""Self-contained run report: runs/<name>/report.html.

Single offline HTML file (inline CSS, no JS deps, no CDN). Videos are
referenced by relative path so the report works wherever the runs/<name>/
folder travels; everything else is inlined or read from run artifacts.
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

from .config import STAGE_ROUTING

# Categorical slots (validated with the dataviz palette checker, light+dark):
# silence=blue, filler=aqua, mixed=yellow, restored(pacing-guard)=green.
CSS = """
:root {
  --surface: #fcfcfb; --panel: #f3f2ef; --border: #e0dfda;
  --ink: #0b0b0b; --ink-2: #52514e; --ink-3: #8a887f;
  --c-silence: #2a78d6; --c-filler: #1baf7a; --c-mixed: #eda100;
  --c-restored: #008300; --c-kept: #d4d2cb;
  --s-good: #0ca30c; --s-warn: #fab219; --s-crit: #d03b3b;
}
@media (prefers-color-scheme: dark) {
  :root {
    --surface: #1a1a19; --panel: #232322; --border: #3a3936;
    --ink: #ffffff; --ink-2: #c3c2b7; --ink-3: #8a887f;
    --c-silence: #3987e5; --c-filler: #199e70; --c-mixed: #c98500;
    --c-restored: #008300; --c-kept: #45443f;
  }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--surface); color: var(--ink);
       font: 15px/1.55 -apple-system, "Segoe UI", Helvetica, Arial, sans-serif; }
.wrap { max-width: 1060px; margin: 0 auto; padding: 32px 24px 64px; }
h1 { font-size: 26px; margin: 0 0 4px; }
h2 { font-size: 17px; margin: 40px 0 12px; }
.sub { color: var(--ink-2); margin: 0 0 10px; }
.meta { display: flex; gap: 28px; flex-wrap: wrap; margin: 18px 0 6px;
        padding: 14px 18px; background: var(--panel);
        border: 1px solid var(--border); border-radius: 10px; }
.meta div { min-width: 110px; }
.meta .k { font-size: 12px; color: var(--ink-3); text-transform: uppercase;
           letter-spacing: .04em; }
.meta .v { font-size: 18px; font-weight: 600; }
.videos { display: flex; gap: 16px; align-items: flex-start; flex-wrap: wrap; }
.vcard { background: var(--panel); border: 1px solid var(--border);
         border-radius: 10px; padding: 12px; }
.vcard p { margin: 8px 2px 0; font-size: 13px; color: var(--ink-2); }
video { display: block; border-radius: 6px; background: #000; }
.v169 { flex: 1 1 560px; } .v169 video { width: 100%; }
.v916 { flex: 0 0 240px; } .v916 video { width: 216px; }
.bar-label { font-size: 13px; color: var(--ink-2); margin: 14px 0 4px; }
.bar { position: relative; height: 34px; border-radius: 6px; overflow: hidden;
       background: var(--c-kept); }
.bar .cut { position: absolute; top: 0; height: 100%; min-width: 3px; }
.bar .cut.silence { background: var(--c-silence); }
.bar .cut.filler  { background: var(--c-filler); }
.bar .cut.mixed   { background: var(--c-mixed); }
.bar .cut.restored { background:
  repeating-linear-gradient(135deg, var(--c-restored) 0 4px, transparent 4px 8px); }
.bar .cut:hover { outline: 2px solid var(--ink); outline-offset: -2px; }
.bar2 { height: 34px; border-radius: 6px; background: var(--c-kept); }
.legend { display: flex; gap: 18px; flex-wrap: wrap; margin: 12px 0 4px;
          font-size: 13px; color: var(--ink-2); }
.legend span { display: inline-flex; align-items: center; gap: 6px; }
.chip { width: 12px; height: 12px; border-radius: 3px; display: inline-block; }
.chip.restored { background:
  repeating-linear-gradient(135deg, var(--c-restored) 0 3px, transparent 3px 6px);
  border: 1px solid var(--c-restored); }
details { margin-top: 10px; }
summary { cursor: pointer; color: var(--ink-2); font-size: 14px; }
table { border-collapse: collapse; width: 100%; margin-top: 10px; font-size: 14px; }
th, td { text-align: left; padding: 7px 10px; border-bottom: 1px solid var(--border); }
th { font-size: 12px; color: var(--ink-3); text-transform: uppercase;
     letter-spacing: .04em; }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
.cap-line { display: flex; gap: 12px; padding: 7px 10px; border-radius: 6px;
            align-items: baseline; }
.cap-line:nth-child(odd) { background: var(--panel); }
.cap-t { flex: 0 0 150px; font: 12px/1.6 ui-monospace, Menlo, monospace;
         color: var(--ink-3); }
.cap-x { font-weight: 600; }
.thumbs { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; }
.thumbs figure { margin: 0; }
.thumbs img { width: 100%; border-radius: 6px; border: 1px solid var(--border);
              display: block; }
.thumbs figcaption { font-size: 12px; color: var(--ink-3); margin-top: 3px; }
.banner { border-radius: 10px; padding: 16px 18px; margin: 12px 0;
          border: 1px solid var(--border); border-left: 6px solid var(--ink-3);
          background: var(--panel); }
.banner.good { border-left-color: var(--s-good); }
.banner.warn { border-left-color: var(--s-warn); }
.banner.crit { border-left-color: var(--s-crit); }
.banner .verdict { font-size: 16px; font-weight: 700; }
.banner .verdict .icon { margin-right: 8px; }
.review h3 { font-size: 14px; margin: 16px 0 4px; }
.review p, .review li { font-size: 14px; color: var(--ink-2); }
.footer { margin-top: 48px; font-size: 12px; color: var(--ink-3); }
"""

VERDICTS = [  # order matters: longest match first
    ("SHIP WITH NOTES", "warn", "&#9888;"),
    ("RECUT", "crit", "&#10007;"),
    ("BLOCK", "crit", "&#10007;"),
    ("SHIP", "good", "&#10003;"),
]


def _esc(s: str) -> str:
    return html.escape(str(s), quote=True)


def _fmt_t(t: float) -> str:
    m, s = divmod(t, 60)
    return f"{int(m)}:{s:04.1f}"


def _parse_srt(text: str, limit: int = 10) -> list[tuple[str, str]]:
    cues = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = [l for l in block.splitlines() if l.strip()]
        if len(lines) >= 3 and "-->" in lines[1]:
            cues.append((lines[1].split(",")[0].strip() + " → "
                         + lines[1].split("-->")[1].split(",")[0].strip(),
                         " ".join(lines[2:])))
        if len(cues) >= limit:
            break
    return cues


def _md_to_html(md: str) -> str:
    out = []
    for para in re.split(r"\n\s*\n", md.strip()):
        lines = para.strip().splitlines()
        if lines[0].startswith("#"):
            level = min(len(lines[0]) - len(lines[0].lstrip("#")) + 1, 4)
            out.append(f"<h{level}>{_inline(lines[0].lstrip('# '))}</h{level}>")
            lines = lines[1:]
            if not lines:
                continue
            para = "\n".join(lines)
        if all(re.match(r"\s*(?:[-*]|\d+\.)\s+", l)
               for l in para.splitlines() if l.strip()):
            items = "".join(f"<li>{_inline(re.sub(r'^\s*(?:[-*]|\d+\.)\s+', '', l))}</li>"
                            for l in para.splitlines() if l.strip())
            out.append(f"<ul>{items}</ul>")
        else:
            out.append(f"<p>{_inline(para)}</p>")
    return "\n".join(out)


def _inline(text: str) -> str:
    text = _esc(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
    return text


def _timeline(cut: dict) -> str:
    orig = cut["original_duration"]
    edited = cut["edited_duration"]
    kinds = {"silence": 0, "filler": 0, "mixed": 0}
    cuts_html = []
    for r in cut["removed"]:
        kind = r["kind"] if r["kind"] in kinds else "mixed"
        kinds[kind] += 1
        left = 100 * r["start"] / orig
        width = 100 * r["dur"] / orig
        tip = (f"{_fmt_t(r['start'])}–{_fmt_t(r['end'])} · {r['dur']:.2f}s · "
               f"cut: {r['reason']}")
        cuts_html.append(
            f'<div class="cut {kind}" style="left:{left:.3f}%;width:{width:.3f}%" '
            f'title="{_esc(tip)}"></div>')
    for r in cut.get("restored", []):
        left = 100 * r["start"] / orig
        width = 100 * (r["end"] - r["start"]) / orig
        tip = (f"{_fmt_t(r['start'])}–{_fmt_t(r['end'])} · KEPT — pacing guard "
               f"cancelled this cut ({r['reason']}): {r.get('restored_because', '')}")
        cuts_html.append(
            f'<div class="cut restored" style="left:{left:.3f}%;width:{width:.3f}%" '
            f'title="{_esc(tip)}"></div>')

    removed_total = sum(r["dur"] for r in cut["removed"])
    pct = 100 * removed_total / orig
    rows = "".join(
        f'<tr><td class="num">{i}</td><td class="num">{_fmt_t(r["start"])}</td>'
        f'<td class="num">{_fmt_t(r["end"])}</td><td class="num">{r["dur"]:.2f}s</td>'
        f'<td>{_esc(r["reason"])}</td></tr>'
        for i, r in enumerate(cut["removed"], 1))

    return f"""
<div class="bar-label">Original — {orig:.1f}s ({_fmt_t(orig)}). Hover any cut for
timestamp + reason; cut widths have a 3px minimum for visibility.</div>
<div class="bar">{''.join(cuts_html)}</div>
<div class="bar-label">Final — {edited:.1f}s ({_fmt_t(edited)}) ·
&minus;{removed_total:.1f}s removed ({pct:.1f}%)</div>
<div class="bar2" style="width:{100 * edited / orig:.2f}%"></div>
<div class="legend">
  <span><span class="chip" style="background:var(--c-silence)"></span>silence cut ({kinds['silence']})</span>
  <span><span class="chip" style="background:var(--c-filler)"></span>filler-word cut ({kinds['filler']})</span>
  <span><span class="chip" style="background:var(--c-mixed)"></span>mixed cut ({kinds['mixed']})</span>
  <span><span class="chip restored"></span>pacing-guard kept ({len(cut.get('restored', []))})</span>
  <span><span class="chip" style="background:var(--c-kept)"></span>kept footage</span>
</div>
<details><summary>All {len(cut['removed'])} cuts (table view)</summary>
<table><tr><th class="num">#</th><th class="num">start</th><th class="num">end</th>
<th class="num">dur</th><th>reason</th></tr>{rows}</table></details>
"""


def generate(run_dir: Path) -> Path:
    run_dir = Path(run_dir)
    state = json.loads((run_dir / "state.json").read_text())
    decisions = json.loads((run_dir / "edit-decisions.json").read_text())
    cut = decisions["cutlist"]

    # header numbers
    total_cost = sum(s.get("cost_usd", 0.0) for s in state["stages"].values())
    total_secs = sum(s.get("seconds", 0.0) for s in state["stages"].values())
    m, s = divmod(int(total_secs), 60)

    # videos (relative to this file's location inside runs/<name>/)
    vids = []
    for rel, label, cls in [("final/long-169.mp4", "16:9 long-form", "v169"),
                            ("final/short-916.mp4", "9:16 short", "v916")]:
        exists = (run_dir / rel).exists()
        note = "" if exists else "<br><strong>file missing on this machine</strong> (media is gitignored — re-run the pipeline to regenerate)"
        vids.append(
            f'<div class="vcard {cls}"><video controls preload="metadata" '
            f'src="{rel}"></video><p>{label} — <code>{rel}</code>{note}</p></div>')

    # captions preview
    srt_path = run_dir / "captions.srt"
    cues = _parse_srt(srt_path.read_text()) if srt_path.exists() else []
    caps = "".join(
        f'<div class="cap-line"><span class="cap-t">{_esc(t)}</span>'
        f'<span class="cap-x">{_esc(x)}</span></div>' for t, x in cues)

    # cost table
    rows = []
    for stage in ("plan", "package", "optimize"):
        st = state["stages"][stage]
        model, _, _ = STAGE_ROUTING[stage]
        status = st["status"]
        if stage == "package" and status == "running":
            status = "done"  # this report is written inside the package stage
        rows.append(f'<tr><td>{stage}</td><td>{model}</td><td>{status}</td>'
                    f'<td class="num">${st.get("cost_usd", 0.0):.4f}</td></tr>')
    rows.append('<tr><td>ingest + edit + caption</td><td>— (local ffmpeg / '
                'whisper / OpenCV engine)</td><td>done</td>'
                '<td class="num">$0.0000</td></tr>')
    rows.append(f'<tr><th colspan="3">total metered</th>'
                f'<th class="num">${total_cost:.4f}</th></tr>')

    # thumbnails
    thumbs = sorted((run_dir / "thumbnails").glob("*.jpg"))
    thumbs += sorted((run_dir / "thumbnails" / "short").glob("*.jpg"))
    thumb_html = "".join(
        f'<figure><img src="{p.relative_to(run_dir)}" alt="{_esc(p.stem)}" '
        f'loading="lazy"><figcaption>{_esc(p.parent.name + "/" + p.name)}'
        f'</figcaption></figure>' for p in thumbs)

    # review verdict banner
    review_path = run_dir / "review-report.md"
    review_md = review_path.read_text() if review_path.exists() else ""
    verdict, cls, icon = "NO REVIEW", "", "&#8212;"
    for v, c, i in VERDICTS:
        if v in review_md:
            verdict, cls, icon = v, c, i
            break
    review_html = _md_to_html(review_md) if review_md.strip() else "<p>No review yet.</p>"

    doc = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>vlog-pipeline report — {_esc(run_dir.name)}</title>
<style>{CSS}</style></head><body><div class="wrap">

<h1>{_esc(run_dir.name)}</h1>
<p class="sub">{_esc(state.get('topic', ''))}</p>
<div class="meta">
  <div><div class="k">run date</div><div class="v">{_esc(state.get('created', '?'))}</div></div>
  <div><div class="k">metered LLM cost</div><div class="v">${total_cost:.4f}</div></div>
  <div><div class="k">pipeline time (sum of stages)</div><div class="v">{m}m{s:02d}s</div></div>
</div>

<h2>Exports</h2>
<div class="videos">{''.join(vids)}</div>

<h2>Before / after cut timeline</h2>
{_timeline(cut)}

<h2>Caption preview <span style="font-weight:400;color:var(--ink-3)">(first {len(cues)} of the .srt)</span></h2>
<div>{caps or '<p class="sub">no captions.srt found</p>'}</div>

<h2>Cost breakdown</h2>
<table><tr><th>stage</th><th>model</th><th>status</th><th class="num">cost</th></tr>
{''.join(rows)}</table>

<h2>Thumbnail frames</h2>
<div class="thumbs">{thumb_html or '<p class="sub">no thumbnails found</p>'}</div>

<h2>Review verdict</h2>
<div class="banner {cls}">
  <div class="verdict"><span class="icon">{icon}</span>{_esc(verdict)}</div>
  <div class="review">{review_html}</div>
</div>

<div class="footer">Generated by vlog-pipeline · self-contained file — videos are
referenced relative to this folder, everything else is inline.</div>
</div></body></html>
"""
    out = run_dir / "report.html"
    out.write_text(doc, encoding="utf-8")
    return out
