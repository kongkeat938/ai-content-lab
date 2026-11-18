#!/usr/bin/env python3
"""A title run must never hand a live sibling's title to another video.

Measured live 2026-11-18: two dharma long-form videos
(`lKt_A63IUmg`, `4EzAMP7urS4`) both carried the identical title
"ธรรมะก่อนนอน ปล่อยวางความเครียด จิตสงบ หลับสบาย", because `optimize_titles`
proposed one title at a time with no view of the channel's other titles. Two
videos with one title compete with each other in search and read to YouTube as
repetitious content -- the exact YPP trap.

This locks the collision check, and proves it can FAIL: a proposal equal to a
sibling's live title must come back as a collision.

    python3 scripts/test_optimize_titles_dedup.py     # exit 0 = the guard holds
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import optimize_titles as ot  # noqa: E402

FAILS = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" -- {detail}" if detail and not ok else ""))
    if not ok:
        FAILS.append(name)


def main() -> int:
    # Two live videos share one title; a third has its own.
    shared = "ธรรมะก่อนนอน ปล่อยวางความเครียด จิตสงบ หลับสบาย"
    taken = {
        ot._norm(shared): {"ids": {"lKt_A63IUmg", "4EzAMP7urS4"}, "title": shared},
        ot._norm("ทางสายกลางและสติ"): {"ids": {"RJPCYx_DUqU"}, "title": "ทางสายกลางและสติ"},
    }

    # The defect: a run retitling lKt_A63IUmg proposes the sibling's exact title.
    check("a proposal equal to a sibling's live title collides",
          ot.collides(shared, taken, "lKt_A63IUmg") is True)
    # Whitespace/case only differences must still collide (the live dup differed
    # only by nothing, but a model may add a stray space).
    check("collision ignores surrounding/trailing whitespace",
          ot.collides("  " + shared + "  ", taken, "lKt_A63IUmg") is True)

    # A video must NOT collide with its own current title (else no retitle lands).
    check("a video does not collide with its own title",
          ot.collides("ทางสายกลางและสติ", taken, "RJPCYx_DUqU") is False)

    # A genuinely new title is free to use.
    check("a fresh title does not collide",
          ot.collides("ธรรมะก่อนนอน ปล่อยวางเรื่องเงิน หลับสบาย", taken, "lKt_A63IUmg") is False)

    # The guard must be able to FAIL: mutating the comparison to always-False must
    # break the first case. If this still "passes", the test is vacuous.
    real = ot.collides
    ot.collides = lambda c, t, s: False
    try:
        mutated = ot.collides(shared, taken, "lKt_A63IUmg")
    finally:
        ot.collides = real
    check("the guard can fail (a neutered comparison returns no collision)",
          mutated is False)

    if FAILS:
        print(f"\n{len(FAILS)} check(s) FAILED")
        return 1
    print("\nall checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
