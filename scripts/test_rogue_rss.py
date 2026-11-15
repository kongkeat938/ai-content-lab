#!/usr/bin/env python3
"""Guard: the quota-free rogue watcher must actually SEE a rogue upload.

A detector that only ever says "clean" is worthless. This drives `find_rogue`
with hand-built feed entries so it FAILS if the detection ever stops working:
a fresh unrecorded id must be reported, a recorded id must not, and an OLD
unrecorded id (the pre-manifest backlog) must not -- otherwise the rail would
cry wolf on every historical clip and be ignored.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from rogue_watch_rss import find_rogue  # noqa: E402

NOW = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)


def iso(hours_ago: float) -> str:
    return (NOW - timedelta(hours=hours_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")


def entry(vid: str, hours_ago: float) -> dict:
    return {"video_id": vid, "title": f"t {vid}", "published": iso(hours_ago)}


def main() -> int:
    fails = []

    # A fresh id no manifest records -> the rogue stream. MUST be reported.
    got = find_rogue([entry("ROGUE000001", 0.5)], recorded=set(), now=NOW)
    if [r["video_id"] for r in got] != ["ROGUE000001"]:
        fails.append("fresh unrecorded id was NOT reported (blind detector)")

    # A recorded id -> ours, never a rogue.
    got = find_rogue([entry("OURS0000001", 0.5)], recorded={"OURS0000001"}, now=NOW)
    if got:
        fails.append("a recorded id was reported as rogue (false positive)")

    # An OLD unrecorded id -> the pre-manifest backlog, not the live stream.
    got = find_rogue([entry("OLD00000001", 24 * 30)], recorded=set(), now=NOW)
    if got:
        fails.append("an old unrecorded id was reported as live rogue (cry wolf)")

    # Mixed: only the fresh unrecorded one survives.
    got = find_rogue([entry("ROGUE000001", 1), entry("OURS0000001", 1),
                      entry("OLD00000001", 24 * 30)],
                     recorded={"OURS0000001"}, now=NOW)
    if [r["video_id"] for r in got] != ["ROGUE000001"]:
        fails.append(f"mixed feed filtered wrong: {[r['video_id'] for r in got]}")

    if fails:
        for f in fails:
            print("FAIL:", f)
        return 1
    print("ok: rogue watcher reports a fresh unrecorded id and nothing else")
    return 0


if __name__ == "__main__":
    sys.exit(main())
