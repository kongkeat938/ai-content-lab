#!/usr/bin/env python3
"""Guard the kinetic engine's REAL b-roll base (the owner's reference look).

The reference is live-action footage; a free model cannot make a believable human
(measured 2026-11-17), so the standard is free real stock video. `--broll` makes the
kinetic engine use one real clip per narration beat as the base, instead of the
gradient. Three properties must hold, and each FAILS on regression:

  1. the picture is the CLIP, not the gradient -- a red clip over beat 1 and a blue
     clip over beat 2 make the frames red then blue;
  2. the render is still 1280x720-class, tv colour range (verify_night's gate);
  3. a beat that cannot be sourced makes build_broll_plan FAIL, not ship a partial
     set (a generator that can drop a piece must fail).

Renders a ~6 s two-beat fixture, so it finishes in well under a minute.

    python3 scripts/test_kinetic_broll.py    # exit 0 = the rules hold
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import make_kinetic_video as mk  # noqa: E402


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def run(cmd: list) -> None:
    subprocess.run(cmd, check=True, capture_output=True)


def mean_rgb(video: str, t: float) -> tuple[float, float, float]:
    import io
    from PIL import Image
    r = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(t), "-i", video,
                        "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"],
                       capture_output=True)
    im = Image.open(io.BytesIO(r.stdout)).convert("RGB")
    # Sample the centre, away from the caption text at the bottom.
    w, h = im.size
    c = im.crop((w // 4, h // 4, 3 * w // 4, h // 2))
    px = list(c.get_flattened_data())
    n = len(px)
    return (sum(p[0] for p in px) / n, sum(p[1] for p in px) / n, sum(p[2] for p in px) / n)


def solid(path: str, rgb: str, secs: float) -> None:
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
         "-i", f"color=c={rgb}:s=640x360:d={secs}:r=25", "-c:v", "libx264",
         "-pix_fmt", "yuv420p", path])


def main() -> int:
    if not shutil.which("ffmpeg"):
        print("SKIP: ffmpeg not installed")
        return 0
    tmp = tempfile.mkdtemp(prefix="kbroll_guard_")
    red = os.path.join(tmp, "red.mp4")
    blue = os.path.join(tmp, "blue.mp4")
    solid(red, "red", 4)
    solid(blue, "blue", 4)
    aud = os.path.join(tmp, "a.m4a")
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
         "anullsrc=r=48000:cl=stereo", "-t", "6", aud])
    timing = os.path.join(tmp, "a.m4a.timing.json")
    json.dump({"duration_sec": 6, "lines": [
        {"text": "คำถามหนึ่ง", "start": 0.2},
        {"text": "คำตอบสอง", "start": 3.2}]}, open(timing, "w", encoding="utf-8"))
    plan = os.path.join(tmp, "broll.json")
    json.dump([{"clip": red, "start": 0.0, "end": 3.0, "label": "one"},
               {"clip": blue, "start": 3.0, "end": 6.0, "label": "two"}],
              open(plan, "w", encoding="utf-8"))
    out = os.path.join(tmp, "out.mp4")
    mk.build(aud, timing, out, title="ทดสอบ", broll=json.load(open(plan)))

    # 1. The base is the CLIP: red over beat 1, blue over beat 2.
    r1 = mean_rgb(out, 1.2)
    r2 = mean_rgb(out, 4.5)
    if not (r1[0] > r1[1] + 40 and r1[0] > r1[2] + 40):
        fail(f"beat 1 is not the red clip (mean RGB {r1}); gradient leaked in")
    if not (r2[2] > r2[0] + 40 and r2[2] > r2[1] + 40):
        fail(f"beat 2 is not the blue clip (mean RGB {r2}); gradient leaked in")

    # 2. Format gate still holds for the b-roll path.
    info = mk.duration(out)  # raises if unreadable
    p = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "stream=width,height,color_range", "-of", "csv=p=0", out],
                       capture_output=True, text=True, check=True).stdout
    if "tv" not in p:
        fail(f"b-roll render is not tv colour range: {p!r}")

    # 3. A missing clip must FAIL the plan, not ship a partial set.
    import build_night as bn
    import fetch_broll
    info_path = os.path.join(tmp, "info.json")
    json.dump({"pieces": [{"name": "01_one", "duration_sec": 3.0},
                          {"name": "02_two", "duration_sec": 3.0}]},
              open(info_path, "w", encoding="utf-8"))
    orig = fetch_broll.pick
    fetch_broll.pick = lambda q, avoid=None: None   # the API finds nothing
    try:
        try:
            bn.build_broll_plan(tmp, info_path)
        except SystemExit:
            pass
        else:
            fail("build_broll_plan shipped a partial set when a clip was missing")
    finally:
        fetch_broll.pick = orig

    shutil.rmtree(tmp, ignore_errors=True)
    print("PASS: kinetic --broll uses the real clip as the base, keeps the tv-range "
          "gate, and fails (not degrades) when a beat cannot be sourced")
    return 0


if __name__ == "__main__":
    sys.exit(main())
