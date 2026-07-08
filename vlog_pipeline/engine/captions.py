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


def _ass_ts(t: float) -> str:
    h, rem = divmod(max(0.0, t), 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def _esc(text: str) -> str:
    return text.replace("{", "(").replace("}", ")").replace("\n", " ")


ASS_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{font},{size},&H00FFFFFF,&H00FFFFFF,&H00141414,&H7A000000,-1,0,0,0,100,100,0,0,1,{outline},1,2,{ml},{mr},{mv},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def write_ass(lines: list[dict], path: str | Path, *, vertical: bool,
              offset: float = 0.0):
    """Styled burned-in captions.

    16:9  -> 1920x1080 canvas, bottom-centered, size 56.
    9:16  -> 1080x1920 canvas, raised well above the Shorts UI zone
             (progress bar / title / engagement buttons live in the bottom
             ~25%), bigger font for phone readability.
    """
    if vertical:
        header = ASS_HEADER.format(w=1080, h=1920, font="Arial", size=78,
                                   outline=4, ml=60, mr=60, mv=560)
    else:
        header = ASS_HEADER.format(w=1920, h=1080, font="Arial", size=56,
                                   outline=3, ml=120, mr=120, mv=72)
    events = []
    for ln in lines:
        a, b = ln["start"] - offset, ln["end"] - offset
        if b <= 0:
            continue
        events.append(
            f"Dialogue: 0,{_ass_ts(max(0, a))},{_ass_ts(b)},Cap,,0,0,0,,{_esc(ln['text'])}")
    Path(path).write_text(header + "\n".join(events) + "\n", encoding="utf-8")


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
