#!/usr/bin/env python3
"""Guard the remake rail against the two ways it could do real damage.

The owner asked (2026-11-07) for new versions of the live Shorts, without
deleting anything. Two failure modes would turn that into a loss, so both are
locked here:

  1. A remake that DELETES the old clip. It must not: the old URL, its views and
     its comments are the only thing the clip still has, and the owner asked to
     keep it. The script may only change the old clip's privacy, never delete it.
  2. A remake that floods. 221 clips are queued, and the whole point of the
     earlier work was that a burst day (26 clips, 11-05) collapsed the views.
     The remake must reuse the rail's daily cap and spacing, and default to one.

    python3 scripts/test_remake_shorts.py    # exit 0 = safe
"""
from __future__ import annotations

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SCRIPT = os.path.join(HERE, "remake_shorts.py")
WORKFLOW = os.path.join(ROOT, ".github", "workflows", "remake-shorts.yml")


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def main() -> int:
    src = open(SCRIPT, encoding="utf-8").read()

    if "videos().delete" in src or ".delete(" in src:
        fail("remake_shorts.py must never delete a video; the owner asked to keep them")

    m = re.search(r'add_argument\("--per-run",\s*type=int,\s*default=(\d+)', src)
    if not m:
        fail("could not find the --per-run default in remake_shorts.py")
    if int(m.group(1)) == 0:
        fail("--per-run defaults to 0 = remake ALL; a missing cap must not flood")
    if int(m.group(1)) > 5:
        fail(f"--per-run default {m.group(1)} is a flood in waiting")

    # The cap and spacing must come from the rail, not a second copy that can drift.
    for need in ("ps.DAILY_CAP", "ps.MIN_GAP_HOURS", "ps.note_upload"):
        if need not in src:
            fail(f"remake_shorts.py does not reuse the rail's {need}")

    if 'default="unlist-low"' not in src:
        fail("--old must default to unlist-low, so a still-earning clip is not hidden")
    if "set_privacy" not in src or "privacyStatus" not in src:
        fail("the old clip must be moved with a privacy change (reversible), not removed")

    wf = open(WORKFLOW, encoding="utf-8").read()
    if "scripts/remake_shorts.py" not in wf:
        fail("remake-shorts.yml does not call remake_shorts.py")
    if re.search(r"cron:\s*\"[^\"]*\*/", wf):
        fail("remake-shorts.yml uses a sub-daily cron; a remake day must not become a burst")

    print("OK: remake keeps the old clips, defaults to one per run, reuses the rail's cap")
    return 0


if __name__ == "__main__":
    sys.exit(main())
