#!/usr/bin/env python3
"""Guard the b-roll grade chain against drift between the two renderers.

Measured 2026-11-17: the ch4 rail shipped `make_kinetic_video.py` while the
owner-approved look lived in `make_qa_video.py`, and the two had drifted -- on the
SAME real clip the rail scored **LapVar 15.4** against the approved **46.6** (~3x
softer). A five-advisor panel was unanimous: do not copy the chain into both files,
extract it and let both import it, and guard the drift. `video_grade` is that one
source. This test FAILS the moment either renderer grows its own divergent chain,
so the rail can never silently stop shipping the approved look.

    python3 scripts/test_video_grade.py    # exit 0 = the two renderers agree
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fetch_broll  # noqa: E402
import make_kinetic_video as kin  # noqa: E402
import make_qa_video as qa  # noqa: E402
import video_grade  # noqa: E402

fails = 0


def fail(msg: str) -> None:
    global fails
    fails += 1
    print(f"  FAIL: {msg}")


def lapvar(clip: str, chain: str, t: float = 1.0) -> float:
    out = os.path.join(tempfile.gettempdir(), "vg_frame.png")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(t), "-i", clip,
                    "-vf", chain, "-frames:v", "1", out], check=True)
    g = np.asarray(Image.open(out).convert("L"), dtype=float)
    return float((-4 * g[1:-1, 1:-1] + g[:-2, 1:-1] + g[2:, 1:-1]
                  + g[1:-1, :-2] + g[1:-1, 2:]).var())


def main() -> int:
    d = tempfile.mkdtemp(prefix="vgrade_")
    clip = os.path.join(d, "clip.mp4")
    # A moving, detailed base so the LapVar measurement is meaningful.
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                    "-i", "testsrc2=size=1920x1080:rate=30:duration=3",
                    "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt",
                    "yuv420p", "-color_range", "tv", clip], check=True)
    lum = fetch_broll.mean_luma(clip)

    # 1. Both renderers must resolve to the SAME format constants.
    if (qa.W, qa.H, qa.FPS) != (kin.W, kin.H, kin.FPS):
        fail(f"format drift: qa {(qa.W, qa.H, qa.FPS)} vs kin {(kin.W, kin.H, kin.FPS)}")
    else:
        print(f"  ok: both render {qa.W}x{qa.H} @ {qa.FPS}fps")

    # 2. Both must emit the IDENTICAL chain for the same clip.
    qa_chain = qa.broll_chain(clip)
    kin_chain = kin.broll_seg_chain(0, 0, 3.0, lum).split("]", 1)[1].split(",trim")[0]
    if qa_chain != kin_chain:
        fail("the two renderers no longer share one grade chain:\n"
             f"    qa : {qa_chain}\n    kin: {kin_chain}")
    else:
        print("  ok: the two renderers share one grade chain")

    # 3. Both must import the shared module's constants (not a private copy).
    for name, obj, want in (("qa.GRADE", qa.GRADE, video_grade.GRADE),
                            ("kin.BROLL_GRADE", kin.BROLL_GRADE, video_grade.GRADE),
                            ("qa.BROLL_ZOOM", qa.BROLL_ZOOM, video_grade.BROLL_ZOOM),
                            ("kin zoom", video_grade.BROLL_ZOOM, 1.06)):
        if obj != want:
            fail(f"{name} drifted from video_grade ({obj!r} != {want!r})")
    if "cas=" not in video_grade.GRADE:
        fail("the shared grade lost its cas (local contrast) term")
    else:
        print("  ok: constants come from video_grade; cas present")

    # 4. Rendered sharpness must agree (the drift the guard exists to catch).
    a = lapvar(clip, qa_chain.replace(",setsar=1", ""))
    b = lapvar(clip, kin_chain)
    ratio = b / a if a else 0.0
    if not (0.95 <= ratio <= 1.05):
        fail(f"rendered sharpness differs: qa LapVar {a:.1f} vs kin {b:.1f} "
             f"({ratio:.0%}); the rail is not shipping the approved look")
    else:
        print(f"  ok: rendered LapVar agrees (qa {a:.1f} / kin {b:.1f})")

    print(f"\n{'PASS' if not fails else f'FAIL ({fails})'} -- b-roll grade has one source")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
