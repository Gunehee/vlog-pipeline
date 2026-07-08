"""Synthesize a talking-head test clip for the pipeline.

Audio: macOS `say` TTS, sectioned (different speaking rates + gains so the
energy detector has real signal), with embedded [[slnc]] dead air and natural
filler words for the silence/filler cutters to find.

Video: an OpenCV-drawn presenter on a set. Mouth height is driven by the real
audio RMS (per-frame), and the presenter drifts laterally across the frame so
a center crop would lose them — the smart crop has to actually track.

Usage: python3 tools/make_test_clip.py testdata/raw-vlog.mp4
"""
from __future__ import annotations

import subprocess
import sys
import wave
from pathlib import Path

import cv2
import numpy as np

W, H, FPS = 1920, 1080, 30
VOICE = "Samantha"

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


def rms_per_frame(wav_path: Path) -> np.ndarray:
    with wave.open(str(wav_path), "rb") as w:
        rate = w.getframerate()
        data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    data = data.astype(np.float32) / 32768.0
    hop = rate // FPS
    n = len(data) // hop
    rms = np.sqrt(np.array([
        np.mean(np.square(data[i * hop:(i + 1) * hop])) for i in range(n)]) + 1e-12)
    p95 = np.percentile(rms[rms > 0.005], 95) if np.any(rms > 0.005) else 1.0
    return np.clip(rms / p95, 0, 1)


def draw_frame(t: float, mouth: float, energy_smooth: float) -> np.ndarray:
    img = np.zeros((H, W, 3), dtype=np.uint8)
    # wall gradient + set dressing (static, so off-center presenter is obvious)
    for y in range(0, H, 4):
        c = 38 + int(26 * y / H)
        img[y:y + 4] = (c + 8, c, c - 6)
    cv2.rectangle(img, (60, 240), (420, 280), (60, 90, 120), -1)       # shelf
    cv2.rectangle(img, (100, 120), (180, 240), (40, 60, 150), -1)      # books
    cv2.rectangle(img, (200, 150), (260, 240), (60, 140, 90), -1)
    cv2.circle(img, (1720, 380), 90, (50, 130, 60), -1)                # plant
    cv2.rectangle(img, (1700, 470), (1740, 620), (40, 70, 90), -1)
    cv2.rectangle(img, (1500, 80), (1880, 300), (140, 120, 90), 6)     # frame

    # presenter drifts: slow sine with dwells, plus energy bob
    cx = int(W * (0.5 + 0.22 * np.sin(t * 0.14) + 0.06 * np.sin(t * 0.045)))
    cy = int(H * 0.46 + 8 * np.sin(t * 2.2) * energy_smooth)

    skin, skin_dk = (150, 175, 210), (120, 145, 185)
    # body
    cv2.ellipse(img, (cx, cy + 430), (260, 300), 0, 180, 360, (90, 60, 40), -1)
    cv2.ellipse(img, (cx, cy + 430), (260, 300), 0, 180, 360, (70, 45, 30), 12)
    cv2.rectangle(img, (cx - 40, cy + 150), (cx + 40, cy + 220), skin_dk, -1)  # neck
    # head
    cv2.ellipse(img, (cx, cy), (150, 190), 0, 0, 360, skin, -1)
    cv2.ellipse(img, (cx, cy - 110), (152, 110), 0, 180, 360, (45, 35, 30), -1)  # hair
    cv2.ellipse(img, (cx, cy - 60), (150, 90), 0, 200, 340, (45, 35, 30), -1)
    # eye sockets / eyes / brows (dark-light contrast helps Haar)
    for sx in (-58, 58):
        ex = cx + sx
        cv2.ellipse(img, (ex, cy - 30), (34, 22), 0, 0, 360, skin_dk, -1)
        cv2.ellipse(img, (ex, cy - 30), (26, 15), 0, 0, 360, (245, 245, 245), -1)
        blink = 1.0 if (t % 4.7) > 0.18 else 0.15
        cv2.circle(img, (ex + 4, cy - 30), int(9 * blink) or 1, (40, 30, 25), -1)
        cv2.line(img, (ex - 30, cy - 62), (ex + 30, cy - 68), (50, 40, 35), 10)
    # nose + shadow
    cv2.line(img, (cx, cy - 10), (cx - 12, cy + 42), skin_dk, 8)
    cv2.ellipse(img, (cx, cy + 48), (18, 8), 0, 0, 180, skin_dk, 4)
    # mouth driven by real audio amplitude
    mh = max(3, int(44 * mouth))
    cv2.ellipse(img, (cx, cy + 105), (52, mh), 0, 0, 360, (40, 35, 90), -1)
    if mh > 18:
        cv2.rectangle(img, (cx - 30, cy + 105 - mh + 6), (cx + 30, cy + 105 - 2),
                      (235, 235, 235), -1)
    cv2.ellipse(img, (cx, cy), (150, 190), 0, 0, 360, (110, 130, 165), 4)
    return img


def main():
    out_path = Path(sys.argv[1] if len(sys.argv) > 1 else "testdata/raw-vlog.mp4")
    work = out_path.parent / "work-clip"
    work.mkdir(parents=True, exist_ok=True)

    print("synthesizing TTS audio...")
    voice = synth_audio(work)
    rms = rms_per_frame(voice)
    n_frames = len(rms)
    print(f"audio: {n_frames / FPS:.1f}s -> rendering {n_frames} frames...")

    silent = out_path.parent / "video-silent.mp4"
    ff = subprocess.Popen(
        ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgr24",
         "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
         "-c:v", "libx264", "-crf", "18", "-preset", "veryfast",
         "-pix_fmt", "yuv420p", str(silent)], stdin=subprocess.PIPE)
    energy = 0.0
    for i in range(n_frames):
        energy = 0.9 * energy + 0.1 * rms[i]
        mouth = rms[i] ** 0.6
        ff.stdin.write(draw_frame(i / FPS, mouth, energy).tobytes())
        if i % 900 == 0:
            print(f"  frame {i}/{n_frames}")
    ff.stdin.close()
    ff.wait()

    print("muxing...")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(silent), "-i", str(voice),
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest",
                    str(out_path)], check=True)
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
