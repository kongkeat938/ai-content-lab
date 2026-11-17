#!/usr/bin/env python3
"""Guard the chapter plan: a missing/failed still must FAIL, not drop a chapter.

Measured 2026-11-17: the first cut of `build_chapter_plan` printed "could not
generate art for <piece>; skipping its chapter" and continued, so a rate-limited
free image generator quietly shipped a video with one chapter's picture missing --
and because `gen_cover_image` falls back to a procedural gradient when the AI
generator is rate-limited, it could also ship a photoreal set with one gradient
card dropped in (reads as broken). K's rule: a generator that can drop a piece must
FAIL, not write a partial set. This test makes both failure modes fail:

  1. the generator errors        -> build_chapter_plan raises (no partial plan);
  2. the generator returns a
     procedural gradient         -> raises (no mixed set);
  3. the generator succeeds      -> every chapter is present.

    python3 scripts/test_chapter_plan.py    # exit 0 = the plan is all-or-nothing
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_night as bn  # noqa: E402


class Failed(Exception):
    """A test failure. Deliberately NOT SystemExit: the 'must raise' cases below
    catch SystemExit (what build_chapter_plan raises), so a plain sys.exit() would
    be swallowed by that handler and the guard could never fail."""


def expect_raise(fn, msg: str) -> None:
    try:
        fn()
    except SystemExit:
        return
    raise Failed(msg)


INFO = {
    "pieces": [{"name": "01_sky.txt", "duration_sec": 30},
               {"name": "02_sea.txt", "duration_sec": 40}],
    "cycles": 1,
    "hook": {"name": "00_hook", "duration_sec": 5},
}


def fake_run(result: tuple, write: bool):
    """A stand-in for build_night.run that fakes gen_cover_image's effect."""
    def _run(cmd):
        if write:
            out = cmd[cmd.index("--out") + 1]
            with open(out, "wb") as f:
                f.write(b"\xff\xd8" + b"0" * 6000)
        return result
    return _run


def plan_for(tmp: str, result: tuple, write: bool) -> list:
    info = os.path.join(tmp, "info.json")
    json.dump(INFO, open(info, "w"))
    bn.run = fake_run(result, write)
    bn.time.sleep = lambda *_: None  # the retry backoff is not what this tests
    return json.load(open(bn.build_chapter_plan(tmp, info, os.path.join(tmp, "img"))))


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="chapter_plan_")
    try:
        # 1. generator error -> must raise, not return a short plan
        expect_raise(lambda: plan_for(tmp, (1, "boom"), write=False),
                     "build_chapter_plan returned a plan even though art generation failed")

        # 2. procedural gradient -> must raise (no photoreal/gradient mix)
        expect_raise(lambda: plan_for(tmp, (0, "x.jpg (37 KB, procedural, md5 abcd)"), write=True),
                     "build_chapter_plan accepted a procedural (gradient) chapter")

        # 3. success -> every chapter present
        plan = plan_for(tmp, (0, "x.jpg (40 KB, pollinations, md5 abcd)"), write=True)
        if len(plan) != 3:  # hook + 2 pieces, under the card ceiling
            raise Failed(f"expected 3 chapters, got {len(plan)}")
        if not all(os.path.exists(c["image"]) for c in plan):
            raise Failed("a planned chapter points at a missing image")
        # starts must be contiguous and cover the whole narration
        if plan[0]["start"] != 0 or abs(plan[-1]["end"] - 75.0) > 0.01:
            raise Failed(f"chapter timings do not span the narration: {plan[0]} .. {plan[-1]}")
    except Failed as e:
        print(f"FAIL: {e}")
        return 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("PASS: the chapter plan is all-or-nothing and covers every beat")
    return 0


if __name__ == "__main__":
    sys.exit(main())

