#!/usr/bin/env python3
"""Guard the manual vision grader -- it must stay OUT of CI.

The 2026-11-17 panel was unanimous: a vision model's score is not reproducible
(the same unchanged cut scored 9 then 5/10), so it may NEVER gate a release. That
decision is only real if a rail cannot quietly wire the grader in later. This test
sweeps the source and FAILS if any workflow, rail script, or CI test calls it.

It also checks the grader keeps the two properties that make it honest:
  * it samples more than one frame (a single opening frame hides the card beats);
  * it reads the reply through the one reader (`gemini_text.text_of`), never
    `parts[0]` alone.

    python3 scripts/test_vision_grader.py    # exit 0 = the grader stays manual

No network: it reads files only, so it cannot flake.
"""
from __future__ import annotations

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GRADER = os.path.join(HERE, "grade_video_vision.py")


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def sweep_files() -> dict[str, str]:
    out = {}
    wf = os.path.join(ROOT, ".github", "workflows")
    for d, _, names in os.walk(wf):
        for n in names:
            p = os.path.join(d, n)
            out[os.path.relpath(p, ROOT)] = open(p, encoding="utf-8").read()
    for n in os.listdir(HERE):
        if n.endswith(".py"):
            p = os.path.join(HERE, n)
            out[os.path.relpath(p, ROOT)] = open(p, encoding="utf-8").read()
    return out


def main() -> int:
    if not os.path.exists(GRADER):
        fail("scripts/grade_video_vision.py is missing")
    src = open(GRADER, encoding="utf-8").read()

    # 1. multi-frame sampling: a single frame is not a video check.
    if "def sample_frames" not in src or "range(n)" not in src:
        fail("the grader must sample several frames, not one")
    if 'default=5' not in src and "default=5" not in src:
        fail("the frame count should default above 1")

    # 2. the one reader: never read parts[0] alone.
    if "gemini_text" not in src or "text_of" not in src:
        fail("the grader must read the reply through gemini_text.text_of")
    if re.search(r'parts"\s*\]\s*\[\s*0\s*\]', src):
        fail("the grader reads parts[0] directly -- use gemini_text.text_of")

    # 3. it must NOT be wired into any workflow, rail, or another test.
    for rel, text in sweep_files().items():
        if rel.endswith("grade_video_vision.py") or rel.endswith("test_vision_grader.py"):
            continue
        if "grade_video_vision" in text:
            fail(f"{rel} references the vision grader -- it must stay manual (not in CI)")

    print("OK: the vision grader stays manual and keeps its two honest properties")
    return 0


if __name__ == "__main__":
    sys.exit(main())
