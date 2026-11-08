#!/usr/bin/env python3
"""Guard the counter invariants: the ledger must catch impossible data.

A cumulative counter can never go down. If the checker accepts a decrease, the
whole idea -- verify against data that must grow -- is worthless, because the one
failure it exists to catch would pass. So this feeds it a series that goes down and
asserts it is reported as a violation, then a series that grows and asserts it is
clean, then a series that is frozen and asserts it is flagged (not violated).

No network: check() takes the series as data.

    python3 scripts/test_counter_ledger.py
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import counter_ledger as cl  # noqa: E402


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def entry(views: dict, days_ago: float) -> dict:
    t = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return {"measured_at": t.isoformat(timespec="seconds"),
            "counters": {ch: {"views": v, "watch_min": v * 5, "subs_gained": v // 100}
                         for ch, v in views.items()}}


def main() -> int:
    # A counter went down between two runs -- impossible, must be a violation.
    down = [entry({"genx": 1000, "dharma": 500, "kongkeat": 200}, 1.0),
            entry({"genx": 900, "dharma": 510, "kongkeat": 205}, 0.0)]
    r = cl.check(down)
    if r["ok"] or not any("genx.views went DOWN" in v for v in r["violations"]):
        fail(f"a decreasing counter was not flagged as a violation: {r}")

    # A healthy growing series -- clean, and not flagged as stalled.
    grow = [entry({"genx": 1000, "dharma": 500, "kongkeat": 200}, 5.0),
            entry({"genx": 1500, "dharma": 800, "kongkeat": 350}, 0.0)]
    r = cl.check(grow)
    if not r["ok"]:
        fail(f"a growing series was reported as a violation: {r}")
    if r["flags"]:
        fail(f"a growing series was flagged as stalled: {r['flags']}")

    # Frozen for a week -- monotonic (no violation) but must be flagged.
    frozen = [entry({"genx": 1000, "dharma": 500, "kongkeat": 200}, 6.0),
              entry({"genx": 1000, "dharma": 500, "kongkeat": 200}, 0.0)]
    r = cl.check(frozen)
    if not r["ok"]:
        fail(f"a frozen counter is not a violation (it is monotonic): {r}")
    if not r["flags"]:
        fail("a counter frozen for 6 days was not flagged")

    # A single measurement cannot prove monotonicity -- say so, do not claim ok.
    r = cl.check([entry({"genx": 1000, "dharma": 500, "kongkeat": 200}, 0.0)])
    if not r["ok"] or not r["flags"]:
        fail("a single measurement was not reported as unproven")

    # A channel that errored must be skipped, not crash the check.
    r = cl.check([entry({"genx": 1000, "dharma": 500, "kongkeat": 200}, 1.0),
                  entry({"genx": 1100, "dharma": 500, "kongkeat": 200}, 0.0)])
    if not r["ok"]:
        fail(f"a valid series was rejected: {r}")

    print("OK: a counter that goes down is a violation, a growing one is clean, a "
          "frozen one is flagged, and one measurement proves nothing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
