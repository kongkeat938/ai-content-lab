#!/usr/bin/env python3
"""MEMORY.md is injected every session and its tail is truncated -- keep it a map.

Measured 2026-11-11: MEMORY.md had grown to 13,039 chars, ~2x the 6,000 budget, so
the tail (usually the newest, most important facts) was being cut silently. This
guard fails before that can happen again, and it must be able to FAIL.

Thresholds:
  * warn  > 6,000 chars  (the budget; the file should stay a map)
  * FAIL  > 9,000 chars  (the truncation zone -- content is being lost)
"""
from __future__ import annotations

import sys
from pathlib import Path

MEMORY = Path(__file__).resolve().parent.parent / ".openhands" / "memory" / "MEMORY.md"
WARN = 6000
FAIL = 9000


def main() -> int:
    if not MEMORY.exists():
        print(f"FAIL: {MEMORY} is missing")
        return 1
    text = MEMORY.read_text(encoding="utf-8")
    n = len(text)
    print(f"MEMORY.md = {n} chars (budget {WARN}, fail {FAIL})")

    if n > FAIL:
        print(f"FAIL: MEMORY.md is {n} chars, over the {FAIL} truncation zone -- the "
              "tail is being cut every session. Move detail to topics/ and slim the index.")
        return 1
    # A map is only a map if it points at the detail. Without this it drifts back
    # into being a log.
    if "topics/" not in text:
        print("FAIL: MEMORY.md names no topics/ file -- it is a log, not a map")
        return 1
    if n > WARN:
        print(f"WARN: MEMORY.md is {n} chars, over the {WARN} budget; slim it soon")
    print("OK: MEMORY.md is within budget and points at topics/ for the detail")
    return 0


if __name__ == "__main__":
    sys.exit(main())
