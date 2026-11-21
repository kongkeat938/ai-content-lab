#!/usr/bin/env python3
"""Prove clip_standard can FAIL: build the bad clips and assert each is rejected.

Owner K's rule: a guard that only ever passes proves nothing. Each case below builds
a real file with ffmpeg and asserts the standard refuses it -- a still that stops
moving, a single unbroken shot, a washed-out colour tag, the wrong shape, wrong
loudness, and a too-short clip. The good case must pass, so the guard is not simply
"always fail".

Run: python3 scripts/test_clip_standard.py
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import clip_standard as C  # noqa: E402

FAILS: list = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"{'PASS' if cond else 'FAIL'} {name}" + (f"  [{detail}]" if detail else ""))
    if not cond:
        FAILS.append(name)


def ff(args: list, timeout: int = 300) -> None:
    r = subprocess.run(["ffmpeg", "-y", "-v", "error", *args],
                       capture_output=True, text=True,
                       stdin=subprocess.DEVNULL, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-800:])


def make_clip(path: str, *, seconds: float = 8.0, shots: int = 2,
              size: str = "1280x720", pix: str = "yuv420p",
              rng: str = "tv", cs: str = "bt709",
              freeze_tail: bool = False, lufs: str = "-14") -> str:
    """Build a clip whose defects are exactly the ones the standard must catch."""
    per = seconds / shots
    srcs = []
    for i in range(shots):
        src = f"{path}.src{i}.mp4"
        # Each shot is a moving pattern, so a shot is not already a still.
        motion = (f"nullsrc=s={size}:d={per},geq="
                  f"lum='mod(40+{i*60}+T*120,255)':cb=128:cr=128,"
                  f"format={pix}") if i % 2 == 0 else \
                 (f"testsrc2=s={size}:d={per},format={pix}")
        ff(["-f", "lavfi", "-i", motion, "-t", str(per),
            "-vf", f"scale={size},setsar=1", "-r", "25",
            "-pix_fmt", pix, "-color_range", rng, "-colorspace", cs,
            src])
        srcs.append(src)
    listing = f"{path}.txt"
    with open(listing, "w") as fh:
        for s in srcs:
            fh.write(f"file '{s}'\n")
    ff(["-f", "concat", "-safe", "0", "-i", listing,
        "-f", "lavfi", "-i", f"sine=frequency=300:duration={seconds}",
        "-vf", "setsar=1", "-r", "25", "-pix_fmt", pix,
        "-color_range", rng, "-colorspace", cs,
        "-af", f"loudnorm=I={lufs}:TP=-2:LRA=11", "-c:v", "libx264",
        "-preset", "ultrafast", "-c:a", "aac", "-shortest", path])
    for s in srcs:
        os.unlink(s)
    os.unlink(listing)
    if freeze_tail:
        frozen = f"{path}.frozen.mp4"
        # Hold the last frame for the final third: motion stops, the clip does not.
        head = seconds * 2 / 3
        ff(["-i", path, "-t", str(head), "-c", "copy", f"{path}.head.mp4"])
        ff(["-i", path, "-vf", f"trim={head},tpad=stop_mode=clone:stop_duration="
            f"{seconds - head}", "-an", "-c:v", "libx264", "-preset", "ultrafast",
            f"{path}.tail.mp4"])
        ff(["-i", f"{path}.head.mp4", "-i", f"{path}.tail.mp4", "-i", path,
            "-map", "0:v", "-map", "1:v", "-map", "2:a",
            "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac",
            "-shortest", frozen])
        os.replace(frozen, path)
        for ext in (".head.mp4", ".tail.mp4"):
            os.unlink(path + ext)
    return path


def make_frozen_clip(path: str, seconds: float = 8.0, freeze: float = 3.0) -> str:
    """A clip that moves, then holds one frame -- motion stops, shots stay 2.

    Built this way on purpose: an earlier version concatenated two shots and froze
    the tail, and it was refused for "1 distinct shot" instead of for freezing, so
    the motion rule was never actually exercised.
    """
    body = os.path.join(os.path.dirname(path), "body.mp4")
    tail = os.path.join(os.path.dirname(path), "tail.mp4")
    head_s = seconds - freeze
    motion = ("nullsrc=s=1280x720:d=%s,geq=lum='mod(40+T*120,255)':cb=128:cr=128,"
              "format=yuv420p" % head_s)
    ff(["-f", "lavfi", "-i", motion, "-t", str(head_s),
        "-vf", "scale=1280x720,setsar=1", "-r", "25", "-pix_fmt", "yuv420p",
        "-color_range", "tv", "-colorspace", "bt709", body])
    ff(["-sseof", "-0.1", "-i", body, "-vf",
        f"tpad=stop_mode=clone:stop_duration={freeze}", "-an", "-t", str(freeze),
        "-c:v", "libx264", "-preset", "ultrafast", tail])
    listing = path + ".txt"
    with open(listing, "w") as fh:
        fh.write(f"file '{body}'\nfile '{tail}'\n")
    ff(["-f", "concat", "-safe", "0", "-i", listing,
        "-f", "lavfi", "-i", f"sine=frequency=300:duration={seconds}",
        "-vf", "setsar=1", "-r", "25", "-pix_fmt", "yuv420p",
        "-color_range", "tv", "-colorspace", "bt709",
        "-af", "loudnorm=I=-14:TP=-2:LRA=11", "-c:v", "libx264",
        "-preset", "ultrafast", "-c:a", "aac", "-shortest", path])
    for p in (body, tail, listing):
        os.unlink(p)
    return path


def main() -> int:
    if not shutil.which("ffmpeg"):
        print("SKIP: ffmpeg not on PATH")
        return 0
    tmp = tempfile.mkdtemp()
    try:
        good = make_clip(os.path.join(tmp, "good.mp4"))
        ok, reasons, m = C.verify_clip(good)
        check("a clip that meets every rule passes", ok, f"{reasons} {m.get('shots')} shots")
        check("the passing clip is really 2 shots", m.get("shots", 0) >= 2,
              str(m.get("shots")))

        still = make_clip(os.path.join(tmp, "still.mp4"), shots=1)
        ok, reasons, m = C.verify_clip(still)
        check("a single unbroken shot is refused", not ok,
              "; ".join(reasons)[:90])
        check("the single-shot clip is refused FOR being one shot",
              any("distinct shot" in r for r in reasons), "; ".join(reasons)[:80])

        frozen = make_frozen_clip(os.path.join(tmp, "frozen.mp4"))
        ok, reasons, m = C.verify_clip(frozen)
        check("a clip whose picture stops moving is refused", not ok,
              f"last_quarter={m.get('last_quarter')}")
        check("the frozen clip is refused FOR stopping, not for another reason",
              any("stops moving" in r for r in reasons), "; ".join(reasons)[:90])

        washed = make_clip(os.path.join(tmp, "washed.mp4"), pix="yuvj420p",
                           rng="pc")
        ok, reasons, m = C.verify_clip(washed)
        check("full-range/washed-out colour is refused", not ok,
              f"{m.get('pix_fmt')}/{m.get('color_range')}")
        check("the washed clip is refused FOR its colour tags",
              any("color_range" in r or "pix_fmt" in r for r in reasons),
              "; ".join(reasons)[:80])

        small = make_clip(os.path.join(tmp, "small.mp4"), size="640x360")
        ok, reasons, m = C.verify_clip(small)
        check("below the 720p floor is refused", not ok, str(m.get("size")))
        check("the small clip is refused FOR its size",
              any("below the" in r for r in reasons), "; ".join(reasons)[:80])

        loud = make_clip(os.path.join(tmp, "loud.mp4"), lufs="-8")
        ok, reasons, m = C.verify_clip(loud)
        check("off-target loudness is refused", not ok, f"{m.get('lufs')} LUFS")
        check("the loud clip is refused FOR its loudness",
              any("LUFS" in r for r in reasons), "; ".join(reasons)[:80])

        short = make_clip(os.path.join(tmp, "short.mp4"), seconds=2.0)
        ok, reasons, m = C.verify_clip(short)
        check("a clip under the length floor is refused", not ok,
              f"{m.get('duration_sec')}s")
        check("the short clip is refused FOR its length",
              any("under the" in r for r in reasons), "; ".join(reasons)[:80])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"\n{len(FAILS)} failure(s)")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
