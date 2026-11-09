#!/usr/bin/env python3
"""Guard the night hand-off: a built-but-unqueued release must be re-queued.

Measured 2026-11-09: the night build passed its gates and created the release,
then its manifest push lost a race. Re-running saw "release exists" and skipped
the hand-off, so the finished video was stranded on a Release forever. The fix
splits one skip flag into two: skip (the build) and skip_pub (the hand-off).

    python3 scripts/test_night_queued.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import night_built_queued as Q  # noqa: E402

FAILS = []


def check(name: str, ok: bool, got: str = "") -> None:
    print(("  ok   " if ok else "  FAIL ") + name + (f" -- {got}" if got else ""))
    if not ok:
        FAILS.append(name)


def write(doc: dict) -> str:
    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False)
    return path


TAG = "night-ea56967db80d-a74f6e"


def main() -> int:
    # A release that is queued and published -> do not re-queue.
    p = write({"videos": [{"key": "night_auto_202646", "video_id": "abc",
                           "video_url": f"https://.../releases/download/{TAG}/video.mp4"}]})
    check("a published release reads as queued", Q.is_queued(TAG, p) is True)
    os.unlink(p)

    # The stranded case: the release exists but has no manifest entry at all.
    p = write({"videos": [{"key": "other", "video_url": "https://.../night-xxxx/video.mp4"}]})
    check("a release with no manifest entry is NOT queued", Q.is_queued(TAG, p) is False)
    os.unlink(p)

    # Queued but not yet uploaded (no video_id) must still be handed off.
    p = write({"videos": [{"key": "night_auto_202646", "state": "ready",
                           "video_url": f"https://.../releases/download/{TAG}/video.mp4"}]})
    check("a ready-but-unuploaded entry is NOT queued", Q.is_queued(TAG, p) is False)
    os.unlink(p)

    # A missing / unreadable manifest must not crash the rail.
    check("a missing manifest reads as not queued",
          Q.is_queued(TAG, "/nonexistent/manifest.json") is False)

    if FAILS:
        print(f"\nFAILED: {FAILS}")
        return 1
    print("\nOK: a built release is only skipped once it is queued for publish")
    return 0


if __name__ == "__main__":
    sys.exit(main())
