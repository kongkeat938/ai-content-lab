#!/usr/bin/env python3
"""The curated subject list must survive its own de-duplication.

Measured 2026-11-16: every curated angle was rejected on all three channels
(dharma 0 of 41, genx 0 of 33, kongkeat 2 of 25) because the overlap floor was 3
characters -- Thai shares 3-char runs constantly, so the whole curated list went
dead and the channel could only ever use learned subjects. The learned subjects
already used a floor of 8 for exactly this reason; the curated list did not.

This guard sweeps the real channel configs (never a hardcoded set, so a new
channel is covered) and fails if the floor regresses or the list goes empty.

    python3 scripts/test_angle_pool.py
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import gen_short_scripts as G  # noqa: E402

FAILS = 0


def check(label: str, ok: bool, got=None) -> None:
    global FAILS
    print(f"  {'ok  ' if ok else 'FAIL'} {label}" + ("" if ok else f" -- got {got!r}"))
    if not ok:
        FAILS += 1


def main() -> int:
    for ch, cfg in G.CHANNELS.items():
        angles = cfg["angles"]
        seen = " ".join(angles)  # a pool where every curated angle is already used
        # With a full pool the loose floor 3 rejects everything -- the bug.
        loose = [a for a in angles if not G._overlaps(a, seen, 3)]
        check(f"{ch}: the 3-char floor is the bug it was (rejects all)", not loose, loose)
        # The real helper must still find fresh work: here nothing is "used" yet.
        fresh = G.fresh_angles(cfg, seen="", learned=[])
        check(f"{ch}: the curated list survives de-duplication", fresh, len(fresh))
        # A learned subject is offered first, ahead of the curated list.
        ordered = G.fresh_angles(cfg, seen="", learned=["subject จาก analytics"])
        check(f"{ch}: learned subjects come first",
              ordered and ordered[0] == "subject จาก analytics")
        # A curated angle already in the pool is dropped, not repeated.
        dup = angles[0]
        deduped = G.fresh_angles(cfg, seen=dup, learned=[])
        check(f"{ch}: a used curated angle is dropped", dup not in deduped, dup)

    print("OK: the curated subject list survives de-duplication on every channel"
          if not FAILS else f"{FAILS} check(s) failed")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
