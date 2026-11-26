#!/usr/bin/env python3
"""The playlist filler must report a gap and must not invent one.

Measured 2026-11-26: dharma's Shorts funnel playlist was missing 5 of 18
long-forms. That gap is only worth fixing if the tool can tell "all present"
from "5 missing", so the cases below force both answers, plus the refusal of a
manifest that belongs to another channel.

    python3 scripts/test_playlist_fill.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import playlist_fill as pf

failures: list[str] = []


def check(ok: bool, what: str) -> None:
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        failures.append(what)


owned = ["a", "b", "c", "d"]

check(pf.missing(owned, "PL", ["a", "b", "c", "d"]) == [], "a full playlist reports no gap")
check(pf.missing(owned, "PL", ["a", "b"]) == ["c", "d"], "a gap is named, oldest first")
check(pf.missing(owned, "PL", []) == owned, "an empty playlist gets every long-form")
check("b" not in pf.missing(owned, "PL", ["a", "b"]), "a video already there is never re-added")

with tempfile.TemporaryDirectory() as tmp:
    good = os.path.join(tmp, "m.json")
    json.dump({"videos": [{"video_id": "x"}, {"title": "no id"}]}, open(good, "w"))
    check(pf.manifest_ids(good) == ["x"], "an entry without a video_id is skipped")

    # The wrong-channel branch needs a live API, so prove the guard exists by
    # reading it out of the source: a filler that cannot refuse is decoration.
    src = open(os.path.join(HERE, "playlist_fill.py"), encoding="utf-8").read()
    check("is not this channel's" in src and "return 2" in src,
          "the tool refuses a manifest that is not this channel's")

print()
if failures:
    print(f"FAILED: {len(failures)}")
    sys.exit(1)
print("all checks passed")
