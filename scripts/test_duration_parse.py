#!/usr/bin/env python3
"""Guard the ISO-8601 duration parser: it must never raise, and must be the only one.

Two checks, both of which can FAIL:

  1. `yt_duration.seconds` returns the right value for every shape YouTube sends --
     including the ones the old inline regex crashed on (`P0D`, `""`, `P1DT2H`).
     Measured 2026-11-13: `channel_overhaul.secs()` raised
     `AttributeError: 'NoneType' object has no attribute 'groups'` on `P0D`, killing
     the ch4-realign rail at the playlist-rename step.
  2. NO script carries the fragile inline pattern again. The same two-line parser
     had been copy-pasted into ten files; a fix in one would leave nine crashes.
     The sweep reads the source (never a hardcoded list of files), so a new copy
     is caught.

    python3 scripts/test_duration_parse.py     # exit 0 = safe and unique
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import yt_duration  # noqa: E402

# The exact shapes that broke the old regex, plus ordinary ones.
CASES = {
    "PT2H3M4S": 7384, "PT45S": 45, "PT1H": 3600, "PT1M": 60, "PT0S": 0,
    "P0D": 0,            # a zero-length item -- old code crashed here
    "": 0,               # empty -- old code crashed here
    "P1DT2H": 93600,     # a day component -- old code crashed here
    "P1DT1H1M1S": 90061, "PT1.5S": 1, "garbage": 0, None: 0,
}


def fail(msg: str) -> None:
    print("FAIL:", msg, file=sys.stderr)
    sys.exit(1)


def main() -> int:
    for iso, want in CASES.items():
        try:
            got = yt_duration.seconds(iso)
        except Exception as exc:  # noqa: BLE001 - the whole point is "never raises"
            fail(f"seconds({iso!r}) raised {type(exc).__name__}: {exc}")
        if got != want:
            fail(f"seconds({iso!r}) = {got}, expected {want}")

    # The fragile inline pattern: a duration regex whose result is used with
    # .groups() without a None guard. Sweep the source, do not hardcode the set.
    fragile = []
    for name in sorted(os.listdir(HERE)):
        if not name.endswith(".py") or name.startswith("test_"):
            continue
        if name == "yt_duration.py":
            continue
        path = os.path.join(HERE, name)
        text = open(path, encoding="utf-8").read()
        for i, line in enumerate(text.splitlines(), 1):
            if "PT(?:" in line and "match" in line:
                fragile.append(f"{name}:{i}")
    if fragile:
        fail("the fragile inline duration parser is back in: "
             + ", ".join(fragile)
             + " -- import yt_duration.seconds() instead (one parser, no crash)")

    print(f"OK: yt_duration.seconds passes {len(CASES)} shapes and is the only "
          "duration parser in scripts/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
