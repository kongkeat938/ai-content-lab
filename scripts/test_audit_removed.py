#!/usr/bin/env python3
"""The channel audit must notice a recorded video that is GONE from the channel.

The audit has always diffed channel -> manifest: a video on the channel that no
manifest names came from outside the rails. It never diffed the other way, so a
video that YouTube removed (a policy take-down) simply disappeared and no report
said so. Measured 2026-11-13: genx carried an ACTIVE community-guidelines warning
whose removed content never appeared anywhere -- the blind spot is real, not
theoretical.

This guard must be able to FAIL: it fails if find_removed stops naming a recorded
video that is no longer on the uploads playlist.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import audit_channels as ac  # noqa: E402


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def main() -> int:
    recorded = {"KEEP": {"title": "ยังอยู่", "posted": "2026-11-01T00:00:00Z"},
                "GONE": {"title": "ถูกนำออกโดย YouTube", "posted": "2026-11-02T00:00:00Z"},
                "WE_DELETED": {"title": "เราลบเอง", "posted": "2026-11-03T00:00:00Z"}}
    present = {"KEEP", "WE_DELETED"}
    removed = {"WE_DELETED"}

    out = "\n".join(ac.find_removed(recorded, present, removed))
    if "KEEP" in out:
        fail("a video still on the channel was wrongly flagged as removed")
    if "WE_DELETED" in out:
        fail("a video we deleted on purpose (backup in content/deleted/) was "
             "flagged as a take-down; the audit would cry wolf")
    if "GONE" not in out:
        fail("a recorded video missing from the uploads playlist was NOT named; "
             "the audit is blind to a YouTube take-down")

    # A guard that only marks SUCCESS cannot fail. Prove it can: with every id
    # marked present, nothing must be flagged.
    clean = ac.find_removed(recorded, set(recorded), removed)
    if clean:
        fail("find_removed flagged videos that are all present")

    # The detection is worthless unless main() actually runs it, or the blind spot
    # returns. Match the call, not a bare substring (the docstring names it).
    src = (Path(__file__).resolve().parent / "audit_channels.py").read_text(encoding="utf-8")
    if not re.search(r"defects \+= removed_defects\(", src):
        fail("main() no longer folds removed_defects() into the report; a "
             "take-down would be measured but never reported")
    if not re.search(r"def removed_defects\(", src):
        fail("removed_defects() is gone; the take-down check was dropped")

    print("OK: the audit names a recorded video that YouTube removed, ignores our "
          "own deletions, and main() runs the check")
    return 0


if __name__ == "__main__":
    sys.exit(main())
