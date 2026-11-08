#!/usr/bin/env python3
"""Guard the chapter renderer against a silent return to the one-card loop.

Measured 2026-11-07: the channel's best long-form (a 120-minute file) held an
averageViewDuration of 379 s = 5.2% of its length, because the whole two hours was
one static card drifting under the narration. The advisor panel (four camps) named
the fix: a picture that changes as the narration moves between beats. This test
locks the two properties that make that true -- one card per piece, and a picture
that is not identical from one chapter to the next -- plus the project's hard
gates (colour range, true peak), so a regression fails here instead of on YouTube.

    python3 scripts/test_chapter_video.py    # exit 0 = the picture changes per chapter

Needs ffmpeg. Renders a ~12 s fixture, so it finishes in well under a minute.
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
import make_chapter_video as mcv  # noqa: E402


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def run(cmd: list) -> None:
    subprocess.run(cmd, check=True, capture_output=True)


def main() -> int:
    if not shutil.which("ffmpeg"):
        print("SKIP: ffmpeg not installed")
        return 0
    tmp = tempfile.mkdtemp(prefix="chaptest_")
    try:
        info = {"out": "compilation.mp3",
                "pieces": [{"name": "01_a", "duration_sec": 3.0},
                           {"name": "02_b", "duration_sec": 3.0},
                           {"name": "03_c", "duration_sec": 3.0}],
                "cycles": 1, "duration_sec": 11.0,
                "hook": {"name": "00_hook", "duration_sec": 2.0}}
        segs = mcv.piece_boundaries(info)
        names = [n for n, _ in segs]
        if names != ["00_hook", "01_a", "02_b", "03_c"]:
            fail(f"chapter layout is {names}, expected the hook then the pieces")
        if abs(sum(d for _, d in segs) - 11.0) > 0.01:
            fail("chapter durations do not sum to the audio length")

        # A long sleep file must group pieces rather than build one card each; the
        # grouping must not lose or add time.
        long_segs = [(f"p{i:03d}", 100.0) for i in range(130)]
        grouped = mcv.coalesce(long_segs, mcv.MAX_CARDS)
        if len(grouped) > mcv.MAX_CARDS:
            fail(f"coalesce left {len(grouped)} cards, over the {mcv.MAX_CARDS} cap")
        if abs(sum(d for _, d in grouped) - sum(d for _, d in long_segs)) > 0.01:
            fail("coalesce changed the total length")
        if mcv.coalesce([("a", 1.0), ("b", 1.0)], mcv.MAX_CARDS) != [("a", 1.0), ("b", 1.0)]:
            fail("coalesce touched a file that was already under the cap")

        audio = os.path.join(tmp, "compilation.mp3")
        run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
             "-i", "sine=frequency=200:duration=11", "-c:a", "libmp3lame", audio])
        out = os.path.join(tmp, "video.mp4")
        mcv.build(audio, info, os.path.join(tmp, "images"), out,
                  "ทดสอบบท", "ทดสอบระบบบท")

        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=color_range,pix_fmt,nb_frames",
             "-of", "json", out], capture_output=True, text=True, check=True)
        st = json.loads(probe.stdout)["streams"][0]
        if st.get("color_range") != "tv":
            fail(f"colour range is {st.get('color_range')}, expected tv")
        if st.get("pix_fmt") != "yuv420p":
            fail(f"pix_fmt is {st.get('pix_fmt')}, expected yuv420p")

        peak = mcv.true_peak(out)
        if not (peak <= -2.9):
            fail(f"true peak {peak} above the -2.9 dBFS ceiling")

        # The whole point: consecutive chapters must not look the same. Sample a
        # frame from the middle of each chapter and compare the luma.
        import numpy as np
        from PIL import Image
        starts, t = [], 0.0
        for _, d in segs:
            starts.append(t + d / 2.0)
            t += d
        frames = []
        for i, s in enumerate(starts):
            png = os.path.join(tmp, f"f{i}.png")
            run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{s:.2f}",
                 "-i", out, "-frames:v", "1", png])
            frames.append(np.asarray(Image.open(png).convert("L"), dtype=float))
        diffs = [float(np.abs(frames[i] - frames[i - 1]).mean())
                 for i in range(1, len(frames))]
        if min(diffs) < 3.0:
            fail(f"chapters look near-identical (min luma diff {min(diffs):.2f}); "
                 "the one-card loop is back")
        print(f"chapter luma diffs: {[round(d, 1) for d in diffs]}")
        print(f"OK: {len(segs)} chapter cards, picture changes each beat, "
              f"tv range, true peak {peak:.1f} dBFS")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
