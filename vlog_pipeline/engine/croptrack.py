"""Subject-tracking vertical crop: Haar face detection with a
motion-centroid fallback, EMA-smoothed, emitted as an ffmpeg sendcmd file."""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


def track_crop(video: str | Path, window: tuple[float, float],
               samples_per_sec: float = 6.0) -> dict:
    """Track subject center-x across the highlight window of the edited cut.

    Returns {'keyframes': [(t_rel, x_center)], 'width', 'height', 'fps',
             'crop_w', 'stats': {...}}
    """
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise RuntimeError(f"OpenCV could not open {video}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    crop_w = int(H * 9 / 16) & ~1  # even width for yuv420p

    cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

    step = max(1, round(fps / samples_per_sec))
    start_f = int(window[0] * fps)
    end_f = int(window[1] * fps)

    cap.set(cv2.CAP_PROP_POS_FRAMES, start_f)
    centers: list[tuple[float, float, str]] = []
    prev_small = None
    frame_idx = start_f
    scale = 0.5

    while frame_idx <= end_f:
        ok, frame = cap.read()
        if not ok:
            break
        if (frame_idx - start_f) % step == 0:
            small = cv2.cvtColor(cv2.resize(frame, None, fx=scale, fy=scale),
                                 cv2.COLOR_BGR2GRAY)
            cx, method = None, "hold"
            faces = cascade.detectMultiScale(small, 1.15, 5, minSize=(40, 40))
            if len(faces):
                x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
                cx, method = (x + w / 2) / scale, "face"
            elif prev_small is not None:
                diff = cv2.absdiff(small, prev_small)
                _, thresh = cv2.threshold(diff, 18, 255, cv2.THRESH_BINARY)
                m = cv2.moments(thresh)
                if m["m00"] > 255 * 150:  # >=150 moving pixels before we trust it
                    cx, method = m["m10"] / m["m00"] / scale, "motion"
            prev_small = small
            t_rel = (frame_idx - start_f) / fps
            if cx is None:
                cx = centers[-1][1] if centers else W / 2
            centers.append((t_rel, float(cx), method))
        frame_idx += 1
    cap.release()

    if not centers:
        centers = [(0.0, W / 2, "hold")]

    # EMA smoothing + speed clamp so the crop glides instead of jittering
    max_step = 260.0 / samples_per_sec  # px per sample at source scale
    smoothed: list[tuple[float, float]] = []
    x = centers[0][1]
    for t_rel, cx, _ in centers:
        target = 0.8 * x + 0.2 * cx
        x += float(np.clip(target - x, -max_step, max_step))
        smoothed.append((t_rel, x))

    half = crop_w / 2
    keyframes = [(round(t, 3), int(np.clip(cx - half, 0, W - crop_w)))
                 for t, cx in smoothed]

    stats = {
        "samples": len(centers),
        "face_pct": round(100 * sum(1 for c in centers if c[2] == "face") / len(centers), 1),
        "motion_pct": round(100 * sum(1 for c in centers if c[2] == "motion") / len(centers), 1),
        "hold_pct": round(100 * sum(1 for c in centers if c[2] == "hold") / len(centers), 1),
        "x_range": [min(k[1] for k in keyframes), max(k[1] for k in keyframes)],
    }
    return {"keyframes": keyframes, "width": W, "height": H, "fps": fps,
            "crop_w": crop_w, "stats": stats}


def write_sendcmd(track: dict, path: str | Path) -> int:
    """Emit `t crop x N;` commands, deduping consecutive identical x values."""
    lines, last_x = [], None
    for t, x in track["keyframes"]:
        if x != last_x:
            lines.append(f"{t:.3f} crop x {x};")
            last_x = x
    Path(path).write_text("\n".join(lines) + "\n")
    return len(lines)


def validate(track: dict, window: tuple[float, float]) -> list[str]:
    problems = []
    kf = track["keyframes"]
    if not kf:
        problems.append("crop tracker produced no keyframes")
        return problems
    dur = window[1] - window[0]
    if len(kf) < max(2, dur * 2):
        problems.append(f"only {len(kf)} crop keyframes for {dur:.0f}s window")
    lo, hi = 0, track["width"] - track["crop_w"]
    for t, x in kf:
        if not (lo <= x <= hi):
            problems.append(f"crop x={x} out of range [{lo},{hi}] at t={t}")
            break
    if track["stats"]["hold_pct"] > 80:
        problems.append(
            f"tracker held static for {track['stats']['hold_pct']}% of samples — "
            "no face or motion signal found")
    return problems
