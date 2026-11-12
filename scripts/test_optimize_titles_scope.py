#!/usr/bin/env python3
"""A title run must never re-title a clip no manifest names (the rogue stream).

Measured 2026-11-12: the uploads listing swept in the rogue stream's clips and
`optimize_titles` re-titled 9 of 17 -- editing videos we do not own and writing
them into `docs/title_changes.json` with no baseline. This locks the scope, and
proves the guard can FAIL: a set that is entirely unrecorded must come back empty.

    python3 scripts/test_optimize_titles_scope.py
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import optimize_titles as ot  # noqa: E402

FAILS = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" -- {detail}" if detail and not ok else ""))
    if not ok:
        FAILS.append(name)


def main() -> int:
    vids = [{"id": "ours1"}, {"id": "rogueX"}, {"id": "ours2"}]
    rec = {"ours1", "ours2"}

    print("a title run keeps only the clips a manifest names")
    kept = [v["id"] for v in ot.only_recorded(vids, rec)]
    check("the recorded clips are kept", kept == ["ours1", "ours2"], str(kept))
    check("an unrecorded (rogue) clip is dropped", "rogueX" not in kept)
    check("the override keeps the rogue clip only on purpose",
          len(ot.only_recorded(vids, rec, allow_unrecorded=True)) == 3)

    print("the guard can fail: it is not vacuously true")
    # If the filter did nothing, this would return the clip instead of [].
    check("an all-unrecorded set comes back empty", ot.only_recorded([{"id": "x"}], set()) == [])

    print()
    if FAILS:
        print(f"FAILED: {len(FAILS)} check(s): {', '.join(FAILS)}")
        return 1
    print("OK: a title run never touches a clip no manifest names")
    return 0


if __name__ == "__main__":
    sys.exit(main())
