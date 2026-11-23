#!/usr/bin/env python3
"""The ambient-video rail must stitch real clips into ONE long, in-spec file.

K (2026-11-18) asked for what a free GUI editor does -- join short calm clips,
loop them to a target length, lay a music bed. This guard proves the rail really
does that, and that it can FAIL:

  1. four short clips come out as one file at the requested length (not the sum of
     the inputs, not a single clip);
  2. the picture meets the house frame (2160x3840 4K, yuv420p, tv/bt709);
  3. the bed is at the house loudness (-14 LUFS), measured live with ebur128;
  4. a build with no usable clip FAILS instead of writing a partial file.

    python3 scripts/test_ambient_video.py
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import make_ambient_video as A  # noqa: E402

fails = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global fails
    print(f"  {'ok  ' if ok else 'FAIL'} {name}{(' -- ' + detail) if detail else ''}")
    if not ok:
        fails += 1


def make_clip(path: str, colour: str, seconds: float) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
         "-i", f"color=c={colour}:s=1920x1080:r=30", "-t", str(seconds),
         "-c:v", "libx264", "-crf", "23", "-pix_fmt", "yuv420p", path], check=True)


def lufs(path: str) -> float:
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", path, "-af",
                        "ebur128=framelog=quiet", "-f", "null", "-"],
                       capture_output=True, text=True)
    m = re.findall(r"I:\s*(-?\d+\.\d+)\s*LUFS", r.stderr)
    return float(m[-1]) if m else 999.0


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        clips = []
        for i, c in enumerate(["navy", "darkgreen", "maroon", "darkslateblue"]):
            p = os.path.join(td, f"c{i}.mp4")
            make_clip(p, c, 2.0)
            clips.append(p)
        music = os.path.join(ROOT, "assets", "music", "bed-calm-soft-piano-wav.mp3")
        out = os.path.join(td, "ambient.mp4")

        print("four 2s clips become one 6s file (stitched + looped to length)")
        A.assemble(clips, music, 6.0, os.path.join(td, "work"), out)
        p = A.probe(out)
        check("output is the requested length, not the input sum",
              abs(p["dur"] - 6.0) < 1.0, f"{p['dur']:.2f}s")

        st = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
             "stream=width,height,pix_fmt,color_primaries,color_transfer,color_space,color_range",
             "-of", "default=nk=1:nw=1", out], capture_output=True, text=True).stdout.split()
        check("frame is 2160x3840 (4K)", st[0] == "2160" and st[1] == "3840", str(st[:2]))
        check("colour is yuv420p tv/bt709",
              "yuv420p" in st and "tv" in st and st.count("bt709") == 3, str(st))

        l = lufs(out)
        check("the bed is at the house loudness (-14 LUFS)",
              abs(l + 14.0) < 0.5, f"{l:.1f} LUFS")

        print("a build with no usable clip FAILS (never a partial file)")
        try:
            A.assemble([], music, 6.0, os.path.join(td, "w2"), os.path.join(td, "x.mp4"))
            check("empty clip set fails", False, "assemble returned without raising")
        except SystemExit:
            check("empty clip set fails", True)

    print("\n" + ("FAILED" if fails else "all checks passed"))
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
