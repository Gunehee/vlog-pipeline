"""Subject-tracking vertical crop: Haar face detection with a
motion-centroid fallback, smoothed, emitted as an ffmpeg sendcmd file.

Fallback ladder per sample: face -> LK optical flow from the last known
position (carries the subject through pans and closed-mouth pauses using its
own texture) -> compact motion centroid -> hold last position.
The smoother is deliberately lazy for small errors (jitter rejection) but
re-acquires fast when the subject genuinely moves:
  - scene-cut snap: a hard cut (large frame diff) plus a face detection
    jumps the track immediately;
  - far-cluster snap: three consecutive detections agreeing on a position
    far from the current track (speaker switch, subject re-entry) snap to
    their median within ~0.5s;
  - error-proportional gain: EMA alpha grows with tracking error, so fast
    pans are followed with bounded lag while small noise stays smoothed.
While the subject is undetectable (out of frame, occluded) the crop holds
its last known position — documented fallback, verified by the
exit_reenter stress scenario.
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

SCENE_CUT_DIFF = 28.0     # mean |frame delta| on the half-res gray to call a hard cut
MAX_MOTION_SPREAD = 300.0  # px (full-res) horizontal std of moving pixels; wider = camera motion
CLUSTER_SPREAD = 110.0    # px: how tightly 3 detections must agree to snap
BASE_ALPHA = 0.2
MAX_ALPHA = 0.7


def _flow_track(prev_small, small, x_est: float, crop_w: int,
                scale: float) -> float | None:
    """LK optical flow on features inside the subject band around x_est.
    Returns the flow-updated center x (full-res) or None if unreliable."""
    h, w = prev_small.shape
    lo = int(max(0, (x_est - 0.5 * crop_w) * scale))
    hi = int(min(w, (x_est + 0.5 * crop_w) * scale))
    if hi - lo < 20:
        return None
    mask = np.zeros_like(prev_small)
    mask[:, lo:hi] = 255
    p0 = cv2.goodFeaturesToTrack(prev_small, maxCorners=60, qualityLevel=0.01,
                                 minDistance=7, mask=mask)
    if p0 is None or len(p0) < 8:
        return None
    p1, st, _err = cv2.calcOpticalFlowPyrLK(prev_small, small, p0, None)
    good = st.reshape(-1) == 1
    if good.sum() < 8:
        return None
    dx = float(np.median((p1[good, 0, 0] - p0[good, 0, 0]))) / scale
    if abs(dx) > crop_w:  # implausible jump — features lost
        return None
    return x_est + dx


def detect_centers(video: str | Path, window: tuple[float, float],
                   samples_per_sec: float = 6.0) -> dict:
    """Sample raw subject detections. Returns dict with 'samples':
    [(t_rel, cx_or_None, method, scene_cut)] plus geometry."""
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise RuntimeError(f"OpenCV could not open {video}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

    crop_w = int(H * 9 / 16) & ~1
    step = max(1, round(fps / samples_per_sec))
    start_f, end_f = int(window[0] * fps), int(window[1] * fps)
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_f)

    samples = []
    prev_small = None
    x_est: float | None = None  # last known subject x (full-res px)
    frame_idx = start_f
    scale = 0.5
    while frame_idx <= end_f:
        ok, frame = cap.read()
        if not ok:
            break
        if (frame_idx - start_f) % step == 0:
            small = cv2.cvtColor(cv2.resize(frame, None, fx=scale, fy=scale),
                                 cv2.COLOR_BGR2GRAY)
            scene_cut = False
            cx, method = None, "hold"
            faces = cascade.detectMultiScale(small, 1.15, 5, minSize=(40, 40))
            if len(faces):
                x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
                cx, method = (x + w / 2) / scale, "face"
            if prev_small is not None:
                diff = cv2.absdiff(small, prev_small)
                scene_cut = float(diff.mean()) > SCENE_CUT_DIFF
                if cx is None and x_est is not None:
                    cx = _flow_track(prev_small, small, x_est, crop_w, scale)
                    if cx is not None:
                        method = "flow"
                if cx is None:
                    _, thresh = cv2.threshold(diff, 18, 255, cv2.THRESH_BINARY)
                    m = cv2.moments(thresh)
                    if m["m00"] > 255 * 150:  # >=150 moving px before we trust it
                        # compactness gate: a subject is a compact blob; camera
                        # motion lights up edges across the whole frame. A
                        # diffuse cloud means "camera moved" — don't chase it.
                        sigma_x = float(np.sqrt(m["mu20"] / m["m00"])) / scale
                        if sigma_x < MAX_MOTION_SPREAD:
                            cx, method = m["m10"] / m["m00"] / scale, "motion"
            if cx is not None:
                x_est = float(cx)
            prev_small = small
            samples.append(((frame_idx - start_f) / fps,
                            float(cx) if cx is not None else None,
                            method, scene_cut))
        frame_idx += 1
    cap.release()
    if not samples:
        samples = [(0.0, None, "hold", False)]
    return {"samples": samples, "width": W, "height": H, "fps": fps}


def smooth_centers(samples: list[tuple], W: int, crop_w: int,
                   samples_per_sec: float = 6.0,
                   max_speed: float = 260.0) -> list[tuple[float, float]]:
    """Pure smoothing pass over raw detection samples (unit-testable).

    samples: [(t, cx_or_None, method, scene_cut)] -> [(t, smoothed_center_x)]
    """
    max_step = max_speed / samples_per_sec
    half = crop_w / 2
    out: list[tuple[float, float]] = []
    x: float | None = None
    recent: list[float] = []  # last raw detections for far-cluster snap

    for t, cx, method, scene_cut in samples:
        if cx is not None:
            recent.append(cx)
            if len(recent) > 3:
                recent.pop(0)
        if x is None:
            x = cx if cx is not None else W / 2
            out.append((t, float(x)))
            continue

        if cx is None:
            out.append((t, float(x)))          # hold last known position
            continue

        if scene_cut and method == "face":
            x = cx                              # hard cut: trust the new face
            recent = [cx]
        elif (len(recent) == 3
              and max(recent) - min(recent) < CLUSTER_SPREAD
              and abs(float(np.median(recent)) - x) > crop_w / 3):
            x = float(np.median(recent))        # consistent far target: snap
        else:
            err = cx - x
            alpha = BASE_ALPHA + (MAX_ALPHA - BASE_ALPHA) * min(
                1.0, abs(err) / half)
            x += float(np.clip(alpha * err, -max_step, max_step))
        out.append((t, float(x)))
    return out


def track_crop(video: str | Path, window: tuple[float, float],
               samples_per_sec: float = 6.0) -> dict:
    """Track subject center-x across a window of the given video.

    Returns {'keyframes': [(t_rel, x_crop)], 'width', 'height', 'fps',
             'crop_w', 'stats': {...}}
    """
    det = detect_centers(video, window, samples_per_sec)
    W, H = det["width"], det["height"]
    crop_w = int(H * 9 / 16) & ~1  # even width for yuv420p
    smoothed = smooth_centers(det["samples"], W, crop_w, samples_per_sec)

    half = crop_w / 2
    keyframes = [(round(t, 3), int(np.clip(cx - half, 0, W - crop_w)))
                 for t, cx in smoothed]

    n = len(det["samples"])
    methods = [s[2] for s in det["samples"]]
    stats = {
        "samples": n,
        "face_pct": round(100 * methods.count("face") / n, 1),
        "flow_pct": round(100 * methods.count("flow") / n, 1),
        "motion_pct": round(100 * methods.count("motion") / n, 1),
        "hold_pct": round(100 * methods.count("hold") / n, 1),
        "scene_cuts": sum(1 for s in det["samples"] if s[3]),
        "x_range": [min(k[1] for k in keyframes), max(k[1] for k in keyframes)],
    }
    return {"keyframes": keyframes, "width": W, "height": H, "fps": det["fps"],
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
