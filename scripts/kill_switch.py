#!/usr/bin/env python3
"""The kill switch every build/publish rail must honour: content/STOP.

K's stop order (2026-11-20: "หยุดสร้างคลิปให้หมด งานรออัพก็หยุดให้หมด") was only
enforced in `watchdog.py` and `publish_shorts.py`. Measured the same day: all four
content generators and `publish_batch`/`remake_shorts`/`publish_motion` ignored the
file, so a manual dispatch or a stray cron would keep building and uploading while
K believed everything was stopped. This module is the one place that answers the
question, so the answer cannot drift per rail.

A rail calls `require_running()` at the top of main(); when the file exists the
rail exits 3 and does nothing. Exit 3 is distinct from 0 so a "stopped" run is
never read as a successful build.

    from kill_switch import require_running
    require_running()   # exits 3 when content/STOP is present
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STOP_PATH = os.path.join(ROOT, "content", "STOP")
STOPPED_EXIT = 3

# The only seam: a test that has to exercise a rail's real logic points the switch at
# its own temp file. `test_kill_switch.py` fails if any workflow sets this variable, so
# a rail in CI can never be talked out of the switch.
STOP_ENV = "CONTENT_STOP_PATH"


def stop_path() -> str:
    override = os.environ.get(STOP_ENV, "").strip()
    return override or STOP_PATH


def stopped() -> bool:
    return os.path.exists(stop_path())


def reason() -> str:
    try:
        with open(stop_path(), encoding="utf-8", errors="replace") as fh:
            text = " ".join(fh.read().split())
    except OSError:
        return ""
    return text[:300]


def require_running(what: str = "this rail") -> None:
    """Exit 3 without doing any work when the kill switch is on."""
    if not stopped():
        return
    why = reason()
    print(f"STOP file present -- {what} will not run"
          + (f" ({why})" if why else ""), file=sys.stderr)
    raise SystemExit(STOPPED_EXIT)
