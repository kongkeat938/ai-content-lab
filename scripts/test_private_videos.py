#!/usr/bin/env python3
"""The delete must remove parked clips and MUST NOT touch a scheduled release.

A scheduled release is `private` with a future `publishAt` -- YouTube flips it
public at the slot (that is what `publish_batch --publish-at` is for), so deleting
one throws away a queued video. A parked clip is `private` with no future
`publishAt` (a rogue upload we hid, or a paused bad cut). This locks the split, and
proves the guard can fail: a past `publishAt` is parked, a future one is not.

    python3 scripts/test_private_videos.py
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import private_videos as pv  # noqa: E402

FAILS = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" -- {detail}" if detail and not ok else ""))
    if not ok:
        FAILS.append(name)


def vid(vid: str, privacy: str, publish_at: str | None = None) -> dict:
    st = {"privacyStatus": privacy}
    if publish_at:
        st["publishAt"] = publish_at
    return {"id": vid, "status": st, "snippet": {"title": vid}, "statistics": {}}


def iso(delta_hours: float) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=delta_hours)).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


def main() -> int:
    future = iso(+6)
    past = iso(-6)

    print("the classification")
    check("a public video is 'public'", pv.kind(vid("a", "public")) == "public")
    check("a private video with no publishAt is 'parked'",
          pv.kind(vid("b", "private")) == "parked")
    check("an unlisted video with no publishAt is 'parked'",
          pv.kind(vid("c", "unlisted")) == "parked")
    check("a private video scheduled in the FUTURE is 'scheduled'",
          pv.kind(vid("d", "private", future)) == "scheduled")
    check("a private video whose publishAt already PASSED is 'parked'",
          pv.kind(vid("e", "private", past)) == "parked")

    print("what a delete would remove")
    rows = [vid("a", "public"), vid("b", "private"), vid("c", "unlisted"),
            vid("d", "private", future), vid("e", "private", past)]
    doomed = {v["id"] for v in pv.parked_only(rows)}
    check("private parked clips are the ones deleted", doomed == {"b", "e"}, str(doomed))
    check("the scheduled release is NOT deleted", "d" not in doomed)
    check("a public video is NOT deleted", "a" not in doomed)
    check("an unlisted clip is NOT deleted by default", "c" not in doomed)

    print("the guard can fail: it is not vacuously true")
    # If kind() ignored publishAt, the scheduled release would look parked and be deleted.
    check("a scheduled release is distinguishable from a parked clip",
          pv.kind(vid("d", "private", future)) != pv.kind(vid("b", "private")))

    print()
    if FAILS:
        print(f"FAIL: {len(FAILS)} check(s) failed: {FAILS}")
        return 1
    print("OK: deletes remove parked clips and never a scheduled release")
    return 0


if __name__ == "__main__":
    sys.exit(main())
