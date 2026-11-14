#!/usr/bin/env python3
"""Guard: a test must not pin a "recent" date to a fixed calendar day.

Measured 2026-11-14: `test_audit_unrecorded.py` set `recent = "2026-11-11T00:00:00Z"`
and passed it to a check that compares the age against `now()` (`RECENT_DAYS = 3`).
The test passed on 2026-11-13 and FAILED on 2026-11-14 -- 3.25 days later -- with no
code change. A test whose result depends on the wall clock is a time bomb: it goes
red on its own and, worse, would have masked a real regression.

The rule: a value that means "recent / now / today / fresh / current / latest" must
be computed from `datetime.now()`, never written as a literal date. A literal date
that is NOT compared to the clock (e.g. a recorded-video fixture) is fine and is
not flagged.

The sweep reads every `scripts/test_*.py`, so a new test cannot reintroduce it.

    python3 scripts/test_no_pinned_recent_date.py     # exit 0 = no time bombs
"""
from __future__ import annotations

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# `recent = "2026-11-11T..."` / `now = "2026-..."` / `fresh_at = "..."` etc.
PINNED = re.compile(
    r"\b(recent|now|today|fresh|current|latest)\w*\s*=\s*[^#\n]*\b20\d\d-\d\d-\d\d")
DATE_LITERAL = re.compile(r"\b20\d\d-\d\d-\d\d")


def main() -> int:
    bad = []
    for name in sorted(os.listdir(HERE)):
        if not name.startswith("test_") or not name.endswith(".py"):
            continue
        if name == os.path.basename(__file__):   # this file quotes the pattern
            continue
        path = os.path.join(HERE, name)
        for i, line in enumerate(open(path, encoding="utf-8").read().splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            if PINNED.search(line) and DATE_LITERAL.search(line):
                bad.append(f"{name}:{i}: {line.strip()}")
    if bad:
        print("FAIL: a test pins a 'recent' value to a fixed date; it will go red "
              "on its own once the clock passes the threshold. Compute it from "
              "datetime.now() instead:", file=sys.stderr)
        for b in bad:
            print("  " + b, file=sys.stderr)
        return 1
    print("OK: no test pins a 'recent'/'now' value to a literal date")
    return 0


if __name__ == "__main__":
    sys.exit(main())
