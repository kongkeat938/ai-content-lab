#!/usr/bin/env python3
"""Guard the kinetic-chapters engine against a silent return to a single picture.

The five-advisor panel (2026-11-16) ruled that a moving gradient with captions
alone still reads as low-effort: it lifts AVD only ~5->12%. What escapes that
signal is a picture that CHANGES as the narration moves between beats, over a base
that moves every frame. Two properties must hold, and each has a test that FAILS
if it regresses:

  1. the picture differs from one chapter to the next (chapter-to-chapter luma
     diff over a floor), and
  2. the picture still moves WITHIN a chapter (non-zero intra-chapter diff), so
     the per-chapter illustration is a layer on a moving base, not a new static
     card.

Renders a ~12 s two-chapter fixture, so it finishes in well under a minute.

    python3 scripts/test_kinetic_chapters.py    # exit 0 = both properties hold
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


def luma_diff(a: str, b: str) -> float:
    from PIL import Image
    import numpy as np
    x = np.asarray(Image.open(a).convert("L"), dtype=float)
    y = np.asarray(Image.open(b).convert("L"), dtype=float)
    return float(abs(x - y).mean())


def frame(video: str, t: float, dst: str) -> None:
    run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(t), "-i", video,
         "-frames:v", "1", dst])


def main() -> int:
    if not shutil.which("ffmpeg"):
        print("SKIP: ffmpeg not installed")
        return 0

    # The plan maths: every illustration must be laid out over the moving base,
    # and the fragments must reference the overlay of each chapter.
    chs = [{"image": "/tmp/a.jpg", "start": 0, "end": 6},
           {"image": "/tmp/b.jpg", "start": 6, "end": 12}]
    # chapter_overlay_chain only needs the files to exist to be planned; use the
    # real fixture files created below.
    tmp = tempfile.mkdtemp(prefix="kchaptest_")
    try:
        from PIL import Image
        for i, c in enumerate(chs):
            p = os.path.join(tmp, f"il{i}.jpg")
            Image.new("RGB", (1280, 720), (20 + i * 90, 60, 120 - i * 40)).save(p)
            c["image"] = p
        frags, last = mk.chapter_overlay_chain(chs, 0)
        joined = ";".join(frags)
        assert any(tok in joined for tok in mk.MOTION_TOKENS), (
            "the moving base was dropped from the chain -- the picture would "
            "freeze between chapters")
        assert joined.count("overlay=") == 2, \
            f"expected one overlay per chapter, got {joined.count('overlay=')}"
        assert "enable='between(t,0.000,6.000)'" in joined and \
            "enable='between(t,6.000,12.000)'" in joined, \
            "a chapter is not time-gated, so both would show at once"
        # both illustrations must be faded, not hard-cut
        assert joined.count("fade=t=in") == 2 and joined.count("fade=t=out") == 2, \
            "chapter illustrations are not dissolved in/out"

        # End to end: render two chapters and measure the two properties.
        audio = os.path.join(tmp, "a.mp3")
        run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
             "sine=frequency=200:duration=12", "-c:a", "libmp3lame", audio])
        timing = os.path.join(tmp, "a.mp3.timing.json")
        json.dump({"duration_sec": 12, "lines": [
            {"text": "บทหนึ่ง", "start": 0.5},
            {"text": "บทสอง", "start": 6.5}]}, open(timing, "w"))
        out = os.path.join(tmp, "v.mp4")
        mk.build(audio, timing, out, "หัวข้อ", "แบรนด์", 0, 24, "veryfast", chs)

        f1 = os.path.join(tmp, "f1.png")
        f2 = os.path.join(tmp, "f2.png")
        f3 = os.path.join(tmp, "f3.png")
        frame(out, 2.0, f1)   # chapter 1
        frame(out, 3.0, f3)   # chapter 1, one second later
        frame(out, 9.0, f2)   # chapter 2
        d_ch = luma_diff(f1, f2)
        d_mo = luma_diff(f1, f3)
        print(f"chapter-to-chapter luma diff: {d_ch:.1f} (need > 8)")
        print(f"intra-chapter motion diff  : {d_mo:.1f} (need > 0.3)")
        if d_ch <= 8:
            fail(f"the picture barely changes between chapters ({d_ch:.1f}) -- "
                 "this is the low-effort signal the panel warned about")
        if d_mo <= 0.3:
            fail(f"the picture is frozen within a chapter ({d_mo:.1f}) -- the "
                 "moving base was lost")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("OK: the picture changes per chapter and still moves within one")
    return 0


if __name__ == "__main__":
    sys.exit(main())
