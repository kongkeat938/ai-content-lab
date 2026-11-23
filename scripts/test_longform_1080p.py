#!/usr/bin/env python3
"""The long-form rail must render at K's 1080p, not at the gate's 720p floor.

Measured 2026-11-23: the first successful story build came out 1280x720 and the
gate still said "pass", because 720 is the floor the approved demo set. K's
reference look for every channel is 1080p, so the floor and the target had
drifted apart -- a build could pass the gate and still be below the bar.

This guard reads the workflow and the module, so it fails if either side is
walked back to 720p.

    python3 scripts/test_longform_1080p.py
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


def main() -> int:
    text = open(WORKFLOW, encoding="utf-8").read()
    check(re.search(r"CLIP_W:\s*1920", text) is not None, "workflow asks for width 1920")
    check(re.search(r"CLIP_H:\s*1080", text) is not None, "workflow asks for height 1080")

    # The module must honour the request, and keep the old default for other builders.
    for env, want in (({"CLIP_W": "1920", "CLIP_H": "1080"}, (1920, 1080)),
                      ({}, (1280, 720))):
        code = ("import standard_clip as s; print(s.W, s.H)")
        out = subprocess.run([sys.executable, "-c", code], cwd=HERE, capture_output=True,
                             text=True, env={**os.environ, **env}, stdin=subprocess.DEVNULL)
        got = tuple(int(x) for x in out.stdout.split()) if out.returncode == 0 else ()
        check(got == want, f"standard_clip honours {env or 'the default'} -> {want} (got {got})")

    gate = open(os.path.join(HERE, "clip_standard.py"), encoding="utf-8").read()
    check("MIN_H = 720" in gate or "MIN_W, MIN_H" in gate,
          "the gate still documents 720p as its floor")
    print(f"\n{'FAILED' if failures else 'PASS'} ({len(failures)} failures)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
