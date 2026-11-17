#!/usr/bin/env python3
"""Guard the long-form minimum standard in verify_night.py.

Owner K (2026-11-17): the approved look is now the minimum bar for EVERY channel,
so verify_night.py -- the check every long-form rail runs -- must hard-fail a file
that is not sharp 1080p with the long-form colour standard. This test builds REAL
files with ffmpeg and asserts the right reason fires, so the guard can FAIL:

  * a 1920x1080 yuv420p tv/bt709 file must NOT raise a format failure;
  * a 1280x720 file must raise "expected 1920x1080";
  * a full-range yuvj420p/pc file must raise "expected yuv420p" and "expected tv".

The bed-headroom check is a night-compilation concern and is not what this test
covers, so the assertions look only at the format reason strings.

    python3 scripts/test_verify_night.py    # exit 0 = the standard is enforced
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def build(path: str, *, w: int, h: int, pix_fmt: str, color_range: str) -> None:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error",
                    "-f", "lavfi", "-i", f"testsrc2=size={w}x{h}:rate=30:duration=2",
                    "-f", "lavfi", "-i", "sine=frequency=300:duration=2",
                    "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", pix_fmt,
                    "-color_range", color_range, "-colorspace", "bt709",
                    "-color_primaries", "bt709", "-color_trc", "bt709",
                    "-c:a", "aac", "-shortest", path], check=True)


def verify(path: str) -> str:
    r = subprocess.run([sys.executable, os.path.join(HERE, "verify_night.py"), path],
                       capture_output=True, text=True)
    return r.stdout + r.stderr


def main() -> int:
    d = tempfile.mkdtemp(prefix="vnight_")
    good = os.path.join(d, "good.mp4")
    small = os.path.join(d, "small.mp4")
    full = os.path.join(d, "full.mp4")
    build(good, w=1920, h=1080, pix_fmt="yuv420p", color_range="tv")
    build(small, w=1280, h=720, pix_fmt="yuv420p", color_range="tv")
    build(full, w=1920, h=1080, pix_fmt="yuvj420p", color_range="pc")

    fails = 0

    def want(label: str, text: str, needle: str, present: bool) -> None:
        nonlocal fails
        has = needle in text
        if has != present:
            fails += 1
            print(f"  FAIL: {label}: {'expected' if present else 'unexpected'} "
                  f"{needle!r} in verify_night output")
        else:
            print(f"  ok: {label}")

    out_good = verify(good)
    want("good 1080p does not fail on size", out_good, "expected 1920x1080", False)
    want("good 1080p does not fail on pix_fmt", out_good, "expected yuv420p", False)

    out_small = verify(small)
    want("720p fails on size", out_small, "expected 1920x1080", True)

    out_full = verify(full)
    want("full-range fails on pix_fmt", out_full, "expected yuv420p", True)
    want("full-range fails on range", out_full, "expected tv", True)

    print(f"\n{'PASS' if not fails else f'FAIL ({fails})'} -- long-form standard enforced")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
