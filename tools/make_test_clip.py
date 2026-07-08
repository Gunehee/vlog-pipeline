"""Synthesize talking-head test clips for the pipeline — baseline + stress scenarios.

Baseline (default, unchanged behavior):
    python3 tools/make_test_clip.py testdata/raw-vlog.mp4

Stress scenarios (each writes <name>.mp4 + <name>.gt.json ground truth):
    python3 tools/make_test_clip.py --scenario handheld --outdir testdata/stress
    python3 tools/make_test_clip.py --scenario all --outdir testdata/stress

Ground truth is generator-known, not estimated: audio is assembled from
individually synthesized chunks (speech / filler / pause), so every planted
filler word and pause has an exact interval; video paths record the subject
center per frame, visibility, speaker-switch times, and camera pan.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import wave
from pathlib import Path

import cv2
import numpy as np

W, H, FPS = 1920, 1080, 30
SR = 48000
VOICE = "Samantha"
VOICE_B = "Daniel"

# ---------------------------------------------------------------- baseline --
# (rate wpm, gain, text) — section 3 is the deliberate high-energy highlight
SECTIONS = [
    (180, 1.00, """Okay, so, um, I just hit thirty days of daily vlogging. [[slnc 900]]
Thirty days, one video every single day, no exceptions. [[slnc 700]]
And, uh, honestly? I almost quit three separate times. [[slnc 1200]]
But I learned three things that completely changed how I make videos,
and, um, I want to walk you through all three of them right now. [[slnc 1500]]"""),

    (172, 1.00, """So lesson number one is that, um, editing is where videos actually get made. [[slnc 800]]
I used to think the shoot was the hard part. [[slnc 600]]
It's not. [[slnc 900]]
Uh, my first vlogs took me forty five minutes to shoot and, like, four hours to edit. [[slnc 700]]
Four hours! [[slnc 1100]]
The thing that saved me was, um, cutting silence automatically instead of
scrubbing the timeline by hand looking for dead air. [[slnc 1400]]
Once I stopped doing that manually, my edit time dropped by more than half. [[slnc 1600]]"""),

    (205, 1.30, """And that brings me to lesson two, and this is the one that blew my mind!
Nobody watches your intro! Nobody! [[slnc 500]]
I looked at my retention graphs and eighty percent of people were gone
before minute one! So I started cutting my videos to open on the single
most interesting sentence I said that day, no hello, no welcome back,
just straight into the point! And my average view duration doubled!
Doubled! In one week! That one change did more than everything else
I tried in the entire month combined! [[slnc 1800]]"""),

    (178, 1.05, """Let me, uh, give you a concrete example of that. [[slnc 700]]
Last Tuesday I filmed a video about my morning routine, and the best
moment was, um, me spilling coffee on my desk at minute six. [[slnc 800]]
The old me would have opened with, like, a whole explanation of what
morning routines are. [[slnc 600]]
Instead I opened on the spill, and, uh, the retention line just stayed
flat the entire video. [[slnc 900]]
Flat retention is basically the holy grail, if you didn't know. [[slnc 1400]]"""),

    (158, 0.90, """Lesson three is, um, quieter, but it might be the most important one. [[slnc 900]]
Consistency beats quality. [[slnc 800]]
Not because quality doesn't matter, but because, uh, you only get good
by shipping. [[slnc 700]]
My day one video is, like, genuinely embarrassing. [[slnc 600]]
My day thirty video is something I'm actually proud of. [[slnc 900]]
And there is no version of this where I skip the embarrassing ones
and jump straight to the good ones. [[slnc 1300]]"""),

    (182, 1.05, """So, um, that's the whole month. Cut the dead air, kill your intro,
and ship every single day. [[slnc 700]]
If you want to see the before and after retention graphs, uh, I put
them in a follow up video, so subscribe so you don't miss it. [[slnc 500]]
And I will see you tomorrow. [[slnc 800]]"""),
]


# ---------------------------------------------------------- audio plumbing --
def read_wav_f32(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as w:
        assert w.getframerate() == SR and w.getnchannels() == 1
        return (np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
                .astype(np.float32) / 32768.0)


def write_wav_f32(path: Path, x: np.ndarray):
    x = np.clip(x, -1.0, 1.0)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((x * 32767).astype(np.int16).tobytes())


def trim_edges(x: np.ndarray, thresh_db: float = -45.0) -> np.ndarray:
    """Strip `say`'s leading/trailing padding so chunk timings are tight."""
    thresh = 10 ** (thresh_db / 20)
    idx = np.where(np.abs(x) > thresh)[0]
    if not len(idx):
        return x
    pad = int(0.02 * SR)
    return x[max(int(idx[0]) - pad, 0): int(idx[-1]) + pad]


def say_chunk(text: str, work: Path, voice: str = VOICE, rate: int = 175,
              gain: float = 1.0) -> np.ndarray:
    aiff, wav = work / "_say.aiff", work / "_say.wav"
    subprocess.run(["say", "-v", voice, "-r", str(rate), "-o", str(aiff),
                    " ".join(text.split())], check=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(aiff),
                    "-ar", str(SR), "-ac", "1", "-c:a", "pcm_s16le", str(wav)],
                   check=True)
    return trim_edges(read_wav_f32(wav)) * gain


GAP = 0.06  # tiny inter-chunk gap; far below Config.min_silence


def assemble(parts: list[dict], work: Path) -> tuple[np.ndarray, list[dict]]:
    """parts: {kind: 'speech'|'filler'|'pause', text?, dur?, voice?, rate?, gain?}
    Returns (audio, events) where events carry exact [start, end] per part."""
    chunks, events, t = [], [], 0.0
    for p in parts:
        if p["kind"] == "pause":
            n = int(p["dur"] * SR)
            chunks.append(np.zeros(n, dtype=np.float32))
            events.append({"kind": "pause", "start": round(t, 3),
                           "end": round(t + p["dur"], 3)})
            t += p["dur"]
        else:
            x = say_chunk(p["text"], work, p.get("voice", VOICE),
                          p.get("rate", 175), p.get("gain", 1.0))
            d = len(x) / SR
            events.append({"kind": p["kind"], "start": round(t, 3),
                           "end": round(t + d, 3), "text": p["text"],
                           "voice": p.get("voice", VOICE)})
            chunks.append(x)
            t += d
            chunks.append(np.zeros(int(GAP * SR), dtype=np.float32))
            t += GAP
    return np.concatenate(chunks), events


def noise_bed(n: int, seed: int = 7) -> np.ndarray:
    """Soft low-passed noise 'music bed' with slow amplitude movement."""
    rng = np.random.default_rng(seed)
    x = rng.standard_normal(n).astype(np.float32)
    kernel = np.ones(64, dtype=np.float32) / 64
    x = np.convolve(x, kernel, mode="same")
    lfo = 0.75 + 0.25 * np.sin(np.arange(n) / SR * 2 * np.pi * 0.13).astype(np.float32)
    x *= lfo
    return x / (np.sqrt(np.mean(x ** 2)) + 1e-9)


def mix_at_snr(voice: np.ndarray, bed: np.ndarray, snr_db: float,
               speech_mask: np.ndarray) -> np.ndarray:
    speech_rms = np.sqrt(np.mean(voice[speech_mask] ** 2) + 1e-12)
    bed_rms = speech_rms / (10 ** (snr_db / 20))
    return np.clip(voice + bed[: len(voice)] * bed_rms, -1, 1)


# ---------------------------------------------------------- video plumbing --
STYLE_A = {"shirt": (90, 60, 40), "shirt_edge": (70, 45, 30),
           "hair": (45, 35, 30), "skin": (150, 175, 210),
           "skin_dk": (120, 145, 185)}
STYLE_B = {"shirt": (40, 40, 140), "shirt_edge": (30, 30, 110),
           "hair": (60, 80, 120), "skin": (130, 160, 200),
           "skin_dk": (100, 130, 175)}


def _background(img: np.ndarray, pan: int):
    for y in range(0, H, 4):
        c = 38 + int(26 * y / H)
        img[y:y + 4] = (c + 8, c, c - 6)
    cv2.rectangle(img, (60 + pan, 240), (420 + pan, 280), (60, 90, 120), -1)
    cv2.rectangle(img, (100 + pan, 120), (180 + pan, 240), (40, 60, 150), -1)
    cv2.rectangle(img, (200 + pan, 150), (260 + pan, 240), (60, 140, 90), -1)
    cv2.circle(img, (1720 + pan, 380), 90, (50, 130, 60), -1)
    cv2.rectangle(img, (1700 + pan, 470), (1740 + pan, 620), (40, 70, 90), -1)
    cv2.rectangle(img, (1500 + pan, 80), (1880 + pan, 300), (140, 120, 90), 6)


def draw_scene(t: float, cx: float, cy: float, mouth: float, *,
               pan: float = 0.0, brightness: float = 1.0,
               style: dict = STYLE_A, noise_sigma: float = 0.0,
               rng: np.random.Generator | None = None) -> np.ndarray:
    img = np.zeros((H, W, 3), dtype=np.uint8)
    _background(img, int(pan))
    cx, cy = int(cx), int(cy)

    cv2.ellipse(img, (cx, cy + 430), (260, 300), 0, 180, 360, style["shirt"], -1)
    cv2.ellipse(img, (cx, cy + 430), (260, 300), 0, 180, 360, style["shirt_edge"], 12)
    cv2.rectangle(img, (cx - 40, cy + 150), (cx + 40, cy + 220), style["skin_dk"], -1)
    cv2.ellipse(img, (cx, cy), (150, 190), 0, 0, 360, style["skin"], -1)
    cv2.ellipse(img, (cx, cy - 110), (152, 110), 0, 180, 360, style["hair"], -1)
    cv2.ellipse(img, (cx, cy - 60), (150, 90), 0, 200, 340, style["hair"], -1)
    for sx in (-58, 58):
        ex = cx + sx
        cv2.ellipse(img, (ex, cy - 30), (34, 22), 0, 0, 360, style["skin_dk"], -1)
        cv2.ellipse(img, (ex, cy - 30), (26, 15), 0, 0, 360, (245, 245, 245), -1)
        blink = 1.0 if (t % 4.7) > 0.18 else 0.15
        cv2.circle(img, (ex + 4, cy - 30), int(9 * blink) or 1, (40, 30, 25), -1)
        cv2.line(img, (ex - 30, cy - 62), (ex + 30, cy - 68), (50, 40, 35), 10)
    cv2.line(img, (cx, cy - 10), (cx - 12, cy + 42), style["skin_dk"], 8)
    cv2.ellipse(img, (cx, cy + 48), (18, 8), 0, 0, 180, style["skin_dk"], 4)
    mh = max(3, int(44 * mouth))
    cv2.ellipse(img, (cx, cy + 105), (52, mh), 0, 0, 360, (40, 35, 90), -1)
    if mh > 18:
        cv2.rectangle(img, (cx - 30, cy + 105 - mh + 6), (cx + 30, cy + 105 - 2),
                      (235, 235, 235), -1)
    cv2.ellipse(img, (cx, cy), (150, 190), 0, 0, 360, (110, 130, 165), 4)

    if brightness != 1.0:
        img = (img.astype(np.float32) * brightness)
        if noise_sigma > 0 and rng is not None:
            img += rng.normal(0, noise_sigma, img.shape).astype(np.float32)
        img = np.clip(img, 0, 255).astype(np.uint8)
    return img


def rms_per_frame_arr(x: np.ndarray) -> np.ndarray:
    hop = SR // FPS
    n = len(x) // hop
    rms = np.sqrt(np.array([
        np.mean(np.square(x[i * hop:(i + 1) * hop])) for i in range(n)]) + 1e-12)
    active = rms[rms > 0.005]
    p95 = np.percentile(active, 95) if len(active) else 1.0
    return np.clip(rms / p95, 0, 1)


def render_clip(out_path: Path, voice: np.ndarray, frame_fn):
    """frame_fn(i, mouth) -> BGR frame. Mouth is real per-frame audio RMS."""
    rms = rms_per_frame_arr(voice)
    n = len(rms)
    work = out_path.parent
    work.mkdir(parents=True, exist_ok=True)
    voice_wav = work / f"{out_path.stem}-voice.wav"
    write_wav_f32(voice_wav, voice)
    silent = work / f"{out_path.stem}-silent.mp4"
    ff = subprocess.Popen(
        ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgr24",
         "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
         "-c:v", "libx264", "-crf", "18", "-preset", "veryfast",
         "-pix_fmt", "yuv420p", str(silent)], stdin=subprocess.PIPE)
    for i in range(n):
        ff.stdin.write(frame_fn(i, rms[i] ** 0.6).tobytes())
    ff.stdin.close()
    ff.wait()
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(silent), "-i",
                    str(voice_wav), "-c:v", "copy", "-c:a", "aac", "-b:a",
                    "192k", "-shortest", str(out_path)], check=True)
    silent.unlink()
    voice_wav.unlink()
    return n


def _speech_mask(events: list[dict], n: int) -> np.ndarray:
    mask = np.zeros(n, dtype=bool)
    for e in events:
        if e["kind"] != "pause":
            mask[int(e["start"] * SR): int(e["end"] * SR)] = True
    return mask


def _write_gt(outdir: Path, name: str, gt: dict):
    (outdir / f"{name}.gt.json").write_text(json.dumps(gt, indent=2))


# ------------------------------------------------------------- speech pool --
POOL = [
    "The first thing I check every morning is the retention graph, because it tells me exactly where people got bored.",
    "If you only change one thing about your videos this year, make it the first ten seconds.",
    "I keep a running list of every hook that worked, and I steal from my own list constantly.",
    "Batch recording saved my schedule; I film three videos every Sunday and edit them across the week.",
    "Good audio matters more than good video, and you can quote me on that.",
    "The camera you already own is good enough, I promise.",
    "Thumbnails take me twenty minutes now, and they used to take two hours.",
    "Publishing on a schedule trains your audience to come back without being asked.",
]


def _pool_parts(idx: list[int], pause: list[float]) -> list[dict]:
    parts = []
    for i, p in zip(idx, pause + [None]):
        parts.append({"kind": "speech", "text": POOL[i % len(POOL)]})
        if p is not None:
            parts.append({"kind": "pause", "dur": p})
    return parts


# --------------------------------------------------------------- scenarios --
def scen_handheld(outdir: Path) -> dict:
    """Camera pan/drift + presenter movement. GT: subject center per frame."""
    work = outdir
    voice, events = assemble(_pool_parts([0, 1, 2, 3, 4], [0.9, 0.8, 1.1, 0.7]), work)
    dur = len(voice) / SR
    n = int(dur * FPS)
    rng = np.random.default_rng(11)
    jitter = np.cumsum(rng.normal(0, 1.6, n))
    jitter -= np.linspace(jitter[0], jitter[-1], n)  # keep bounded
    ts = np.arange(n) / FPS
    pan = W * 0.030 * np.sin(0.9 * ts) + jitter
    cx_world = W * (0.5 + 0.18 * np.sin(0.21 * ts) + 0.08 * np.sin(0.53 * ts))
    cx = np.clip(cx_world + pan, 0.18 * W, 0.82 * W)
    cy = H * 0.46 + 6 * np.sin(2.1 * ts)

    def frame(i, mouth):
        return draw_scene(ts[i], cx[i], cy[i], mouth, pan=pan[i])

    render_clip(outdir / "handheld.mp4", voice, frame)
    gt = {"scenario": "handheld", "fps": FPS, "duration": dur,
          "cx": cx.round(1).tolist(), "events": events}
    _write_gt(outdir, "handheld", gt)
    return gt


def scen_music(outdir: Path) -> dict:
    """Speech over a noise/music bed at two SNRs. GT: exact pause intervals."""
    voice, events = assemble(_pool_parts([0, 1, 5, 2, 4], [1.0, 0.8, 1.4, 0.7]), outdir)
    mask = _speech_mask(events, len(voice))
    bed = noise_bed(len(voice))
    dur = len(voice) / SR
    n = int(dur * FPS)
    ts = np.arange(n) / FPS
    cx = W * 0.5 + 18 * np.sin(0.4 * ts)
    cy = H * 0.46 + 6 * np.sin(2.1 * ts)

    for snr in (18, 8):
        mixed = mix_at_snr(voice, bed, snr, mask)

        def frame(i, mouth):
            return draw_scene(ts[i], cx[i], cy[i], mouth)

        render_clip(outdir / f"music_snr{snr:02d}.mp4", mixed, frame)
    gt = {"scenario": "music", "fps": FPS, "duration": dur, "snrs": [18, 8],
          "events": events}
    _write_gt(outdir, "music", gt)
    return gt


def scen_alternation(outdir: Path) -> dict:
    """Two presenters (voice+position+style) alternating with hard cuts.
    GT: switch times + active-speaker center per frame."""
    turns = [(VOICE, 0.36, 0), (VOICE_B, 0.64, 3), (VOICE, 0.36, 1),
             (VOICE_B, 0.64, 4), (VOICE, 0.36, 2), (VOICE_B, 0.64, 5)]
    parts = []
    for voice_name, _, pool_i in turns:
        parts.append({"kind": "speech", "text": POOL[pool_i], "voice": voice_name})
        parts.append({"kind": "pause", "dur": 0.7})
    parts.pop()  # no trailing pause
    voice, events = assemble(parts, outdir)
    dur = len(voice) / SR
    n = int(dur * FPS)
    ts = np.arange(n) / FPS

    speech_events = [e for e in events if e["kind"] == "speech"]
    switches = [e["start"] for e in speech_events[1:]]
    cx = np.zeros(n)
    style_id = np.zeros(n, dtype=int)
    for k, e in enumerate(speech_events):
        end = speech_events[k + 1]["start"] if k + 1 < len(speech_events) else dur
        seg = (ts >= e["start"]) & (ts < end)
        _, posx, _ = turns[k]
        cx[seg] = W * posx + 12 * np.sin(2.2 * ts[seg])
        style_id[seg] = 0 if turns[k][0] == VOICE else 1
    cy = H * 0.46 + 5 * np.sin(2.0 * ts)

    def frame(i, mouth):
        style = STYLE_A if style_id[i] == 0 else STYLE_B
        return draw_scene(ts[i], cx[i], cy[i], mouth, style=style)

    render_clip(outdir / "alternation.mp4", voice, frame)
    gt = {"scenario": "alternation", "fps": FPS, "duration": dur,
          "switches": switches, "cx": cx.round(1).tolist(), "events": events}
    _write_gt(outdir, "alternation", gt)
    return gt


def scen_exit_reenter(outdir: Path) -> dict:
    """Presenter leaves frame completely, then returns. GT: cx + visibility."""
    voice, events = assemble(
        _pool_parts([0, 3, 1, 4, 7], [0.8, 0.9, 0.8, 0.7]), outdir)
    dur = len(voice) / SR
    n = int(dur * FPS)
    ts = np.arange(n) / FPS
    t_exit, t_gone, t_back, t_home = 12.0, 16.0, 24.0, 27.0
    cx = np.empty(n)
    for i, t in enumerate(ts):
        if t < t_exit:
            cx[i] = W * (0.5 + 0.02 * np.sin(0.5 * t))
        elif t < t_gone:
            f = (t - t_exit) / (t_gone - t_exit)
            cx[i] = W * (0.5 + f * 0.85)          # walks off right (to 1.35 W)
        elif t < t_back:
            cx[i] = W * 1.35                       # fully out of frame
        elif t < t_home:
            f = (t - t_back) / (t_home - t_back)
            cx[i] = W * (1.35 - f * 0.87)          # re-enters from the right
        else:
            cx[i] = W * (0.48 + 0.02 * np.sin(0.5 * t))
    # visible = any part of the presenter (body half-width ~270) on screen
    visible = (cx > -270) & (cx < W + 270)
    cy = H * 0.46 + 6 * np.sin(2.1 * ts)

    def frame(i, mouth):
        return draw_scene(ts[i], cx[i], cy[i], mouth)

    render_clip(outdir / "exit_reenter.mp4", voice, frame)
    gt = {"scenario": "exit_reenter", "fps": FPS, "duration": dur,
          "cx": cx.round(1).tolist(), "visible": visible.astype(int).tolist(),
          "marks": {"exit": t_exit, "gone": t_gone, "back": t_back,
                    "home": t_home}, "events": events}
    _write_gt(outdir, "exit_reenter", gt)
    return gt


def scen_low_contrast(outdir: Path) -> dict:
    """Dark, noisy footage so Haar hit rate drops. GT: cx per frame."""
    voice, events = assemble(_pool_parts([2, 5, 6, 7], [0.9, 0.8, 1.0]), outdir)
    dur = len(voice) / SR
    n = int(dur * FPS)
    ts = np.arange(n) / FPS
    cx = W * (0.5 + 0.15 * np.sin(0.3 * ts))
    cy = H * 0.46 + 6 * np.sin(2.1 * ts)
    rng = np.random.default_rng(23)

    def frame(i, mouth):
        return draw_scene(ts[i], cx[i], cy[i], mouth, brightness=0.22,
                          noise_sigma=4.0, rng=rng)

    render_clip(outdir / "low_contrast.mp4", voice, frame)
    gt = {"scenario": "low_contrast", "fps": FPS, "duration": dur,
          "cx": cx.round(1).tolist(), "events": events}
    _write_gt(outdir, "low_contrast", gt)
    return gt


def scen_dense_filler(outdir: Path) -> dict:
    """Densely packed fillers with acoustic traps (umbrella/summer/likely) and
    legitimate 'like' usage. GT: exact planted filler intervals."""
    F = lambda w, rate=170: {"kind": "filler", "text": w, "rate": rate}
    parts = [
        {"kind": "speech", "text": "So here is my honest take on gear."},
        F("um"),
        {"kind": "speech", "text": "My umbrella is under the summer sun and the drum kit hums."},
        F("uh"),
        {"kind": "speech", "text": "I like this camera a lot, and it looks like rain outside."},
        F("um"),
        {"kind": "speech", "text": POOL[4]},
        F("erm"),
        {"kind": "speech", "text": "The drummer was unlikely to hum along, unlike last summer."},
        F("uh"),
        {"kind": "speech", "text": POOL[6]},
        F("like", 120),  # drawn-out hesitation 'like'
        {"kind": "speech", "text": POOL[7]},
        F("um"), F("uh"),  # back-to-back pair
        {"kind": "speech", "text": POOL[1]},
        F("hmm"),
        F("ah"),
        {"kind": "speech", "text": POOL[3]},
        F("um"),
        {"kind": "speech", "text": "And that is genuinely everything I know."},
    ]
    voice, events = assemble(parts, outdir)
    dur = len(voice) / SR
    n = int(dur * FPS)
    ts = np.arange(n) / FPS
    cx = W * 0.5 + 20 * np.sin(0.35 * ts)
    cy = H * 0.46 + 6 * np.sin(2.1 * ts)

    def frame(i, mouth):
        return draw_scene(ts[i], cx[i], cy[i], mouth)

    render_clip(outdir / "dense_filler.mp4", voice, frame)
    gt = {"scenario": "dense_filler", "fps": FPS, "duration": dur,
          "events": events}
    _write_gt(outdir, "dense_filler", gt)
    return gt


def scen_boundary_silence(outdir: Path) -> dict:
    """Silence at clip start and end + one very long mid silence.
    GT: exact pause intervals; expectations derive from engine Config."""
    parts = [
        {"kind": "pause", "dur": 3.0},
        {"kind": "speech", "text": POOL[0] + " " + POOL[1]},
        {"kind": "pause", "dur": 0.9},
        {"kind": "speech", "text": POOL[2] + " " + POOL[3]},
        {"kind": "pause", "dur": 8.0},
        {"kind": "speech", "text": POOL[4] + " " + POOL[5]},
        {"kind": "pause", "dur": 4.0},
    ]
    voice, events = assemble(parts, outdir)
    dur = len(voice) / SR
    n = int(dur * FPS)
    ts = np.arange(n) / FPS
    cx = W * 0.5 + 15 * np.sin(0.4 * ts)
    cy = H * 0.46 + 6 * np.sin(2.1 * ts)

    def frame(i, mouth):
        return draw_scene(ts[i], cx[i], cy[i], mouth)

    render_clip(outdir / "boundary_silence.mp4", voice, frame)
    gt = {"scenario": "boundary_silence", "fps": FPS, "duration": dur,
          "events": events}
    _write_gt(outdir, "boundary_silence", gt)
    return gt


SCENARIOS = {
    "handheld": scen_handheld,
    "music": scen_music,
    "alternation": scen_alternation,
    "exit_reenter": scen_exit_reenter,
    "low_contrast": scen_low_contrast,
    "dense_filler": scen_dense_filler,
    "boundary_silence": scen_boundary_silence,
}


# ---------------------------------------------------------------- baseline --
def synth_audio(work: Path) -> Path:
    parts = []
    for i, (rate, gain, text) in enumerate(SECTIONS):
        aiff = work / f"sec{i}.aiff"
        subprocess.run(["say", "-v", VOICE, "-r", str(rate), "-o", str(aiff),
                        " ".join(text.split())], check=True)
        wav = work / f"sec{i}.wav"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(aiff),
                        "-af", f"volume={gain}", "-ar", "48000", "-ac", "1",
                        str(wav)], check=True)
        parts.append(wav)
    concat = work / "concat.txt"
    concat.write_text("".join(f"file '{p.resolve()}'\n" for p in parts))
    full = work / "voice.wav"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
                    "-i", str(concat), "-c:a", "pcm_s16le", str(full)], check=True)
    return full


def baseline(out_path: Path):
    work = out_path.parent / "work-clip"
    work.mkdir(parents=True, exist_ok=True)
    print("synthesizing TTS audio...")
    voice = read_wav_f32(synth_audio(work))
    n = len(rms_per_frame_arr(voice))
    print(f"audio: {n / FPS:.1f}s -> rendering {n} frames...")
    ts = np.arange(n) / FPS
    energy = 0.0
    rms = rms_per_frame_arr(voice)

    def frame(i, mouth):
        nonlocal energy
        energy = 0.9 * energy + 0.1 * rms[i]
        t = ts[i]
        cx = W * (0.5 + 0.22 * np.sin(t * 0.14) + 0.06 * np.sin(t * 0.045))
        cy = H * 0.46 + 8 * np.sin(t * 2.2) * energy
        return draw_scene(t, cx, cy, mouth)

    render_clip(out_path, voice, frame)
    print(f"wrote {out_path}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("output", nargs="?", default="testdata/raw-vlog.mp4",
                    help="baseline output path (ignored with --scenario)")
    ap.add_argument("--scenario", choices=[*SCENARIOS, "all"],
                    help="generate a stress scenario instead of the baseline")
    ap.add_argument("--outdir", default="testdata/stress")
    args = ap.parse_args()

    if args.scenario:
        outdir = Path(args.outdir)
        outdir.mkdir(parents=True, exist_ok=True)
        names = list(SCENARIOS) if args.scenario == "all" else [args.scenario]
        for name in names:
            print(f"=== generating scenario: {name}")
            SCENARIOS[name](outdir)
        return
    baseline(Path(args.output))


if __name__ == "__main__":
    main()
