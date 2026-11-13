#!/usr/bin/env python3
"""Guard that a long-form rail's generated content dir is per-RUN, not per-week.

Measured 2026-11-13: three rails dated their content dir by ISO week
(`date -u +%G%V`). When a rail runs twice in one week -- which is the whole point
of a raised cadence -- both runs generate the SAME directory and both commit it,
producing an add/add conflict on every piece, a rejected push, and a stranded
finished video (issues #28/#29 on ch4-longform). A rail that may run more than
once a week must date its dir per run (add `_r${GITHUB_RUN_NUMBER}`).

This test sweeps EVERY workflow that builds a `*_auto_$(date -u +%G%V)` dir and
requires the run-number suffix, so a new rail cannot reintroduce the bug (never
hardcode the set a guard sweeps).

    python3 scripts/test_per_run_content_dir.py     # exit 0 = no weekly dirs left
"""
from __future__ import annotations

import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def main() -> None:
    offenders: list[str] = []
    for wf in sorted(glob.glob(os.path.join(ROOT, ".github", "workflows", "*.yml"))):
        src = open(wf, encoding="utf-8").read()
        for m in re.finditer(r'CONTENT="([^"]*\$\(date -u \+%G%V[^"]*)"', src):
            value = m.group(1)
            if "GITHUB_RUN_NUMBER" not in value:
                offenders.append(f"{os.path.basename(wf)}: {value}")

    if offenders:
        fail(
            "these rails date their content dir per ISO week, so a 2nd run in the "
            "same week reuses/conflicts on the same files (add the "
            "_r${GITHUB_RUN_NUMBER} suffix):\n  " + "\n  ".join(offenders)
        )

    print("OK: every per-week content dir is run-scoped (no weekly dirs left)")


if __name__ == "__main__":
    main()
