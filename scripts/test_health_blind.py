#!/usr/bin/env python3
"""A blind health report must not read as "fresh".

`health.py` decides freshness from the GitHub run history. When that read fails
(401, rate limit, a proxy blip) the report has *no* information -- yet it used to
skip the stale check and still print "all rails fresh" and exit 0. Worse, with
`--alert` it would have closed the alert issue, silencing a real alert during the
one window where the rails are unobserved.

The fix: a blind read is its own state ("UNKNOWN"), it exits non-zero, and it
never clears the alert. This test locks that in -- it FAILS on the old behaviour.

    python3 scripts/test_health_blind.py     # exit 0 = blind is not fresh
"""
from __future__ import annotations

import contextlib
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import health  # noqa: E402

FAILS = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" -- {detail}" if detail and not ok else ""))
    if not ok:
        FAILS.append(name)


def run_main(monkey: dict) -> tuple[int, str]:
    """Call health.main() with last_runs replaced, capturing stdout and exit code."""
    orig = health.last_runs
    health.last_runs = lambda: monkey
    buf = io.StringIO()
    argv = sys.argv
    sys.argv = ["health.py"]
    try:
        with contextlib.redirect_stdout(buf):
            rc = health.main()
    finally:
        health.last_runs = orig
        sys.argv = argv
    return rc, buf.getvalue()


def main() -> int:
    print("a blind run history is UNKNOWN, not fresh")
    rc, out = run_main({"_error": "HTTP Error 401: Unauthorized"})
    check("exit code is non-zero", rc != 0, f"rc={rc}")
    check("report says UNKNOWN", "UNKNOWN" in out, out[-200:])
    check("report does NOT claim all rails fresh", "all rails fresh" not in out, out[-200:])
    check("report explains it is blind", "blind" in out.lower(), out[-200:])

    print("a readable, all-fresh history is still reported fresh")
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    fresh = {name: {"last": now, "last_status": "success", "last_success": now}
             for name in health.EXPECTED}
    rc2, out2 = run_main(fresh)
    check("exit code is zero", rc2 == 0, f"rc={rc2}")
    check("report says all rails fresh", "all rails fresh" in out2, out2[-200:])

    print()
    if FAILS:
        print(f"FAIL: {len(FAILS)} check(s) failed: {FAILS}")
        return 1
    print("OK: a blind report is not reported as fresh")
    return 0


if __name__ == "__main__":
    sys.exit(main())
