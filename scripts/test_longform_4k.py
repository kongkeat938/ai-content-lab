#!/usr/bin/env python3
"""The long-form master is 4K, and the gate must say so.

Measured 2026-11-23, twice: the first story build came out 1280x720 and the gate
said "pass", because 720 is the floor the approved demo set. A 1080p render then
passed the same way. K: "ทำไมคุณภาพคลิปไม่ใช่ 4k" -- the floor and the target had
drifted apart, so a build could be below the bar and still look approved.

This guard reads the workflow, the rail and the gate, and it feeds the gate a
1080p file that must be REJECTED -- a floor nobody can fail is decoration.

    python3 scripts/test_longform_4k.py
"""
from __future__ import annotations

import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WORKFLOW = os.path.join(ROOT, ".github", "workflows", "longform-standard.yml")

failures: list[str] = []


def check(ok: bool, what: str) -> None:
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        failures.append(what)


def run(code: str, env: dict | None = None) -> str:
    out = subprocess.run([sys.executable, "-c", code], cwd=HERE, capture_output=True,
                         text=True, env={**os.environ, **(env or {})},
                         stdin=subprocess.DEVNULL)
    return out.stdout.strip() if out.returncode == 0 else ""


def main() -> int:
    text = open(WORKFLOW, encoding="utf-8").read()
    check(re.search(r"CLIP_W:\s*3840", text) is not None, "workflow asks for width 3840")
    check(re.search(r"CLIP_H:\s*2160", text) is not None, "workflow asks for height 2160")
    check(re.search(r"CLIP_SCENE_PX:\s*960", text) is not None,
          "workflow generates 960 px scenes (x4 = 3840, no upscale)")

    rail = open(os.path.join(HERE, "longform_clip.py"), encoding="utf-8").read()
    check("MIN_OUT_H = 2160" in rail, "the rail demands 2160 from the gate")
    check('"--min-height", str(MIN_OUT_H)' in rail, "the rail passes that demand to the gate")

    gate = open(os.path.join(HERE, "clip_standard.py"), encoding="utf-8").read()
    check("min_h: int = MIN_H" in gate, "the gate takes an explicit floor")

    for env, want in (({"CLIP_W": "3840", "CLIP_H": "2160"}, "3840 2160 640"),
                      ({"CLIP_SCENE_PX": "960"}, "1280 720 960"),
                      ({}, "1280 720 640")):
        code = ("import standard_clip as s; print(s.W, s.H, s.SCENE_PX)")
        got = run(code, env)
        check(got == want, f"standard_clip honours {env or 'its defaults'} -> {want} (got {got})")

    # The floor must be able to FAIL: a real 1080p file is below 2160.
    ff = os.environ.get("FFMPEG", "ffmpeg")
    sample = "/tmp/_4k_guard_1080.mp4"
    made = subprocess.run(
        [ff, "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
         "-i", "testsrc=size=1920x1080:rate=25:duration=1", "-c:v", "libx264",
         "-pix_fmt", "yuv420p", sample], stdin=subprocess.DEVNULL)
    if made.returncode == 0:
        out = subprocess.run([sys.executable, "clip_standard.py", sample, "--min-height", "2160"],
                             cwd=HERE, capture_output=True, text=True, stdin=subprocess.DEVNULL)
        check(out.returncode != 0 and "below the" in out.stdout,
              "a 1080p file FAILS the 4K floor")
    else:
        print("skip  the 1080p fixture (no ffmpeg on PATH)")

    print(f"\n{'FAILED' if failures else 'PASS'} ({len(failures)} failures)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
