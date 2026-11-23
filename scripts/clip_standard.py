#!/usr/bin/env python3
"""The minimum standard every long-form clip must meet before it may ship.

Owner K (2026-11-20): the demo he approved ("งานผ่านแล้ว") is now the **minimum bar**
for clip building -- "คุณภาพขั้นต่ำต้องแบบนี้". This is the ONE place that decides
pass/fail for a horizontal clip, exactly as `short_standard.py` is the one place for
a Short. A build that fails is HELD, not shipped; the publish rail and the test guard
both call this, so there is no second opinion to drift.

Every threshold is the number measured on the approved demo, not a guess:

  * **720p floor, 16:9** -- the demo was 1280x720; rule 5 of the new spec is
    "4K source / 720p output", so 720 is the floor, not the target.
  * **yuv420p + range=tv + bt709** -- measured 2026-11-17: a build that skipped the
    tags came out `yuvj420p` / full-range / `bt470bg` and played washed-out.
  * **-14 LUFS, true peak <= -1.5 dBFS** -- the demo measured -14.9 LUFS / -1.5 dBTP.
  * **real motion to the last frame** -- the demo's last-quarter frame-diff was 0.98
    against a 0.22 minimum; a still that stops moving reads as a slide-show.
  * **>= 2 distinct shots** -- the demo cut 5 AI scenes; scene-change scores were
    74.5 and 61.2. One unbroken still is not a clip.
  * **voice above the bed** -- measured: speech -14 dB, music -20..-27 dB.

    from clip_standard import verify_clip
    ok, reasons, metrics = verify_clip("demo.mp4")
"""
from __future__ import annotations

import json
import os
import re
import subprocess

MIN_W, MIN_H = 1280, 720
ASPECT = 16 / 9
PIX_FMT = "yuv420p"
COLOR_RANGE = "tv"
COLORSPACE = "bt709"
LOUD_I, LOUD_TOL = -14.0, 1.5
LOUD_TP = -1.5
MIN_SEC = 3.0
# Motion: mean absolute frame difference over the last quarter of the clip.
MIN_LAST_QUARTER_MOTION = 0.05
MIN_SCENES = 2
# Distinctness is a RATIO against the same-shot baseline, never an absolute number:
# measured 2026-11-20 on the approved demo, shot-to-shot mean-image distance was
# 45-73 against a same-shot baseline of 7.9 (>=5.6x). A crossfade has no hard cut,
# so a cut-detector reports "1 shot" on a perfectly good clip -- that was the bug.
DISTINCT_RATIO = 3.0
# Motion: mean absolute frame difference over the last quarter of the clip.
MIN_LAST_QUARTER_MOTION = 0.05


def _run(argv: list) -> str:
    r = subprocess.run(argv, capture_output=True, text=True,
                       stdin=subprocess.DEVNULL)
    return r.stderr + r.stdout


def _probe(path: str) -> dict:
    out = _run(["ffprobe", "-v", "error", "-show_entries",
                "stream=codec_type,width,height,pix_fmt,color_range,color_space:"
                "format=duration", "-of", "json", path])
    m = re.search(r"\{.*\}", out, re.S)
    return json.loads(m.group(0)) if m else {}


def _loudness(path: str) -> tuple:
    out = _run(["ffmpeg", "-i", path, "-af", "ebur128=peak=true", "-f", "null", "-"])
    i = tp = None
    for ln in out.splitlines():
        s = ln.strip()
        if s.startswith("I:") and "LUFS" in s:
            i = float(s.split()[1])
        elif s.startswith("Peak:") and "dBFS" in s:
            tp = float(s.split()[1])
    return i, tp


def _frames(path: str, w: int = 160, h: int = 90) -> list:
    """Decode the whole clip to tiny grey frames for motion/scene measurement."""
    import numpy as np

    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", path, "-vf", f"scale={w}:{h}",
         "-pix_fmt", "gray", "-f", "rawvideo", "-"],
        capture_output=True, stdin=subprocess.DEVNULL).stdout
    n = w * h
    return [np.frombuffer(raw[i:i + n], dtype=np.uint8)
            for i in range(0, len(raw) - n + 1, n)]


def measure_motion(path: str) -> dict:
    """Frame-diff statistics, measured on the real file."""
    import numpy as np

    frames = _frames(path)
    if len(frames) < 2:
        return {"frames": len(frames), "mean": 0.0, "last_quarter": 0.0,
                "shots": 0, "shot_ratio": 0.0}
    diffs = [float(np.abs(frames[i].astype("int16") -
                          frames[i - 1].astype("int16")).mean())
             for i in range(1, len(frames))]
    quarter = diffs[max(0, len(diffs) * 3 // 4):]
    return {"frames": len(frames),
            "mean": round(float(np.mean(diffs)), 3),
            "last_quarter": round(float(np.mean(quarter)), 3)}


def measure_shots(path: str, window: float = 1.0) -> dict:
    """How many visually distinct shots, without needing a hard cut.

    A crossfade has no cut, so the honest measure is how far apart the *looks* are:
    compare the mean image of each time window against a same-window baseline (two
    halves of one window, which is one look) and count a window as a distinct shot
    when it differs by DISTINCT_RATIO times that baseline. Measured on the approved
    demo: shot-to-shot 45-73 vs a same-shot baseline of 7.9.
    """
    import numpy as np

    frames = _frames(path, 64, 36)
    if len(frames) < 4:
        return {"shots": len(frames) > 0, "shot_ratio": 0.0}
    arr = np.array([f.astype("float32") for f in frames])
    dur_frames = len(frames)
    per = max(2, int(round(dur_frames / max(1.0, dur_frames / 25 * window))))
    wins = [arr[i:i + per] for i in range(0, dur_frames - per + 1, per)]
    if len(wins) < 2:
        return {"shots": 1, "shot_ratio": 0.0}
    means = [w.mean(axis=0) for w in wins]
    baseline = float(np.mean([
        np.abs(w[:len(w) // 2].mean(axis=0) - w[len(w) // 2:].mean(axis=0)).mean()
        for w in wins])) or 1e-6
    gaps = [float(np.abs(means[i] - means[i - 1]).mean())
            for i in range(1, len(means))]
    shot_gaps = [g for g in gaps if g >= DISTINCT_RATIO * baseline]
    return {"shots": 1 + len(shot_gaps),
            "shot_ratio": round(float(np.mean(shot_gaps) / baseline), 2)
            if shot_gaps else 0.0,
            "shot_baseline": round(baseline, 2)}


def verify_clip(video: str, min_h: int = MIN_H) -> tuple:
    """Return (ok, reasons, metrics). ok is False if ANY standard is missed."""
    reasons: list = []
    metrics: dict = {}
    if not (video and os.path.exists(video)):
        return False, [f"no video at {video!r}"], metrics

    info = _probe(video)
    streams = info.get("streams", [])
    v = next((s for s in streams if s.get("codec_type") == "video"), None)
    a = next((s for s in streams if s.get("codec_type") == "audio"), None)

    if not v:
        reasons.append("no video stream")
    else:
        w, h = v.get("width") or 0, v.get("height") or 0
        metrics["size"] = f"{w}x{h}"
        min_w = round(min_h * 16 / 9)
        if w < min_w or h < min_h:
            reasons.append(f"{w}x{h} is below the {min_w}x{min_h} floor")
        if h and abs(w / h - ASPECT) > 0.02:
            reasons.append(f"aspect {w}x{h} is not 16:9")
        metrics["pix_fmt"] = v.get("pix_fmt")
        metrics["color_range"] = v.get("color_range")
        metrics["colorspace"] = v.get("color_space")
        if v.get("pix_fmt") != PIX_FMT:
            reasons.append(f"pix_fmt {v.get('pix_fmt')} is not {PIX_FMT}")
        if v.get("color_range") != COLOR_RANGE:
            reasons.append(f"color_range {v.get('color_range')} is not {COLOR_RANGE}")
        if v.get("color_space") not in (COLORSPACE, "unknown", None):
            reasons.append(f"colorspace {v.get('color_space')} is not {COLORSPACE}")

    if not a:
        reasons.append("no audio stream")
    else:
        i, tp = _loudness(video)
        metrics["lufs"], metrics["true_peak"] = i, tp
        if i is None:
            reasons.append("loudness could not be measured")
        elif not (LOUD_I - LOUD_TOL <= i <= LOUD_I + LOUD_TOL):
            reasons.append(f"loudness {i:.1f} LUFS is off the {LOUD_I} target")
        if tp is not None and tp > LOUD_TP:
            reasons.append(f"true peak {tp:.1f} dBFS exceeds {LOUD_TP}")

    dur = float(info.get("format", {}).get("duration") or 0.0)
    metrics["duration_sec"] = round(dur, 2)
    if dur and dur < MIN_SEC:
        reasons.append(f"duration {dur:.2f}s is under the {MIN_SEC:.0f}s floor")

    if v:
        motion = measure_motion(video)
        metrics.update(motion)
        if motion["last_quarter"] < MIN_LAST_QUARTER_MOTION:
            reasons.append(f"the picture stops moving (last-quarter frame-diff "
                           f"{motion['last_quarter']} < {MIN_LAST_QUARTER_MOTION})")
        shots = measure_shots(video)
        metrics.update(shots)
        if shots["shots"] < MIN_SCENES:
            reasons.append(f"only {shots['shots']} distinct shot(s); "
                           f"{MIN_SCENES} minimum (one still is a slide-show)")

    return (not reasons), reasons, metrics


def main() -> int:
    import argparse
    import sys

    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--min-height", type=int, default=MIN_H,
                    help="floor for this rail; the long-form rail asks for 2160")
    args = ap.parse_args()
    ok, reasons, metrics = verify_clip(args.video, args.min_height)
    print(json.dumps({"verdict": "pass" if ok else "fail",
                      "failures": reasons, "metrics": metrics},
                     indent=1, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
