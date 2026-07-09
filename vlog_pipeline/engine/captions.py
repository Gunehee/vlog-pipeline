"""Caption line building + SRT/ASS emission with platform-aware styling."""
from __future__ import annotations

from pathlib import Path


def build_lines(words: list[dict], max_chars: int = 34, max_words: int = 6,
                max_dur: float = 3.2, gap_break: float = 0.8) -> list[dict]:
    """Group word timestamps into readable caption lines."""
    lines, cur = [], []
    for w in words:
        token = w["word"].strip()
        if not token:
            continue
        if cur:
            text_len = len(" ".join(x["word"] for x in cur)) + 1 + len(token)
            gap = w["start"] - cur[-1]["end"]
            dur = w["end"] - cur[0]["start"]
            if (text_len > max_chars or len(cur) >= max_words
                    or gap > gap_break or dur > max_dur):
                lines.append(_flush(cur))
                cur = []
        cur.append(w)
    if cur:
        lines.append(_flush(cur))
    return lines


def _flush(ws: list[dict]) -> dict:
    return {
        "start": ws[0]["start"],
        "end": max(ws[-1]["end"], ws[0]["start"] + 0.4),
        "text": " ".join(w["word"].strip() for w in ws),
    }


def _srt_ts(t: float) -> str:
    h, rem = divmod(max(0.0, t), 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int(round((s % 1) * 1000)):03d}"


def write_srt(lines: list[dict], path: str | Path):
    out = []
    for i, ln in enumerate(lines, 1):
        out.append(f"{i}\n{_srt_ts(ln['start'])} --> {_srt_ts(ln['end'])}\n{ln['text']}\n")
    Path(path).write_text("\n".join(out), encoding="utf-8")


FONT = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"

# Export style presets. 9:16 margins keep captions above the Shorts UI zone
# (progress bar / title / engagement buttons live in the bottom ~25%).
PRESETS = {
    "clean":  {"size_scale": 1.0,  "box_alpha": 115, "mv_v": 560, "mv_h": 72},
    "boxed":  {"size_scale": 1.0,  "box_alpha": 200, "mv_v": 560, "mv_h": 72},
    "large":  {"size_scale": 1.22, "box_alpha": 115, "mv_v": 560, "mv_h": 80},
    "high":   {"size_scale": 1.0,  "box_alpha": 115, "mv_v": 760, "mv_h": 72},
}


def render_caption_pngs(lines: list[dict], out_dir: str | Path, *, vertical: bool,
                        offset: float = 0.0, preset: str = "clean") -> list[dict]:
    """Render each caption line to a styled transparent PNG for ffmpeg overlay.

    Styling: bold white text, black stroke, semi-transparent rounded box.
    16:9  -> 1920x1080 canvas, bottom-centered.
    9:16  -> 1080x1920 canvas, raised above the Shorts UI zone (progress bar /
             title / engagement buttons live in the bottom ~25%), bigger font.

    Returns [{'file', 'x', 'y', 'start', 'end'}] with times shifted by -offset.
    """
    from PIL import Image, ImageDraw, ImageFont

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    st = PRESETS.get(preset, PRESETS["clean"])
    if vertical:
        canvas_w, canvas_h, size, stroke = 1080, 1920, 76, 5
        margin_bottom = st["mv_v"]
    else:
        canvas_w, canvas_h, size, stroke = 1920, 1080, 56, 4
        margin_bottom = st["mv_h"]
    size = int(size * st["size_scale"])
    box_alpha = st["box_alpha"]
    font = ImageFont.truetype(FONT, size)
    pad_x, pad_y = 26, 14

    overlays = []
    for i, ln in enumerate(lines):
        a, b = ln["start"] - offset, ln["end"] - offset
        if b <= 0.05:
            continue
        probe = ImageDraw.Draw(Image.new("RGBA", (8, 8)))
        bbox = probe.textbbox((0, 0), ln["text"], font=font, stroke_width=stroke)
        w = bbox[2] - bbox[0] + 2 * pad_x
        h = bbox[3] - bbox[1] + 2 * pad_y
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle((0, 0, w - 1, h - 1), radius=16, fill=(0, 0, 0, box_alpha))
        d.text((pad_x - bbox[0], pad_y - bbox[1]), ln["text"], font=font,
               fill=(255, 255, 255, 255), stroke_width=stroke,
               stroke_fill=(10, 10, 10, 255))
        f = out_dir / f"cap-{i:03d}.png"
        img.save(f)
        overlays.append({
            "file": str(f),
            "x": (canvas_w - w) // 2,
            "y": canvas_h - margin_bottom - h,
            "start": round(max(0.0, a), 3),
            "end": round(b, 3),
        })
    return overlays


def validate(lines: list[dict], edited_dur: float) -> list[str]:
    problems = []
    if not lines:
        problems.append("no caption lines produced")
        return problems
    prev_end = 0.0
    for ln in lines:
        if ln["end"] <= ln["start"]:
            problems.append(f"caption with non-positive duration: {ln}")
        if ln["start"] < prev_end - 0.4:
            problems.append(f"overlapping captions near {ln['start']:.1f}s")
        if len(ln["text"]) > 60:
            problems.append(f"caption too long to read: {ln['text'][:60]}...")
        prev_end = ln["end"]
    if lines[-1]["end"] > edited_dur + 1.5:
        problems.append("captions extend beyond edited duration")
    return problems
