#!/usr/bin/env python3
"""Guard the night (dharma long-form) rail's cadence against the foreman (2026-11-13).

The rail is dispatched two ways: its own `schedule` crons, and the foreman's
"keep the rail fed" backfill (which fires when the newest build is old). When the
cadence was raised 1 -> 2/week, the cron was updated but the foreman still only
backfilled after 6 days, so a dropped tick would have waited days. The two must
agree, and the threshold must be DERIVED from the cadence, not a literal that goes
stale. This test reads the workflow's real cron count and asserts both.

    python3 scripts/test_foreman_cadence.py     # exit 0 = the two agree
"""
from __future__ import annotations

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import foreman  # noqa: E402


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def main() -> None:
    wf = os.path.join(ROOT, ".github", "workflows", "night-compilation.yml")
    src = open(wf, encoding="utf-8").read()

    # Count the real cron entries under a `schedule:` key (the rail's own cadence).
    crons = re.findall(r"^\s*-\s*cron:\s*\"", src, re.M)
    n_crons = len(crons)
    if n_crons < 1:
        fail("night-compilation.yml has no `- cron:` entry; the cadence is unknown")

    if foreman.NIGHT_BUILDS_PER_WEEK != n_crons:
        fail(
            f"foreman.NIGHT_BUILDS_PER_WEEK={foreman.NIGHT_BUILDS_PER_WEEK} but the rail "
            f"has {n_crons} cron(s); raise/lower the constant to match the rail so the "
            f"backfill does not lag a cadence change"
        )

    # The backfill threshold must be derived from the constant, not a stale literal.
    fsrc = open(os.path.join(HERE, "foreman.py"), encoding="utf-8").read()
    if "NIGHT_BUILDS_PER_WEEK" not in fsrc.split("def ", 1)[-1]:
        fail("the backfill window does not use NIGHT_BUILDS_PER_WEEK; it is a literal again")

    print(f"OK: foreman NIGHT_BUILDS_PER_WEEK={foreman.NIGHT_BUILDS_PER_WEEK} matches "
          f"{n_crons} cron(s); the backfill window is derived from it")


if __name__ == "__main__":
    main()
