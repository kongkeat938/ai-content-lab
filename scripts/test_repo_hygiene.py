#!/usr/bin/env python3
"""Catch a git conflict that was committed instead of resolved.

Measured 2026-11-09: a `git pull --rebase --autostash` in remake-shorts left
conflict markers inside content/upload_log.json and the markers got committed
(612f185). Every foreman run then crashed on the unparsable JSON, so no rail
was driven from the chain until it was found. Two properties lock that out:

  1. No tracked text file may contain a conflict marker. A marker means a merge
     was committed unresolved, which is always a bug.
  2. Every JSON file the rails read must parse. A committed marker breaks
     json.load, and a broken ledger silently stops a cap from being counted.

    python3 scripts/test_repo_hygiene.py     # exit 0 = no committed conflict
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# A real conflict marker sits at the start of a line. Anchoring there keeps a
# detector's own string literal (e.g. publish_shorts.py's "<<<<<<< ") from
# tripping this guard.
MARKER_RE = re.compile(r"^(<{7} |>{7} )", re.M)
TEXT_EXT = {".py", ".json", ".md", ".yml", ".yaml", ".sh", ".txt", ".html", ".css", ".js"}


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def tracked_files() -> list[str]:
    out = subprocess.run(["git", "-C", ROOT, "ls-files"],
                         capture_output=True, text=True, check=True).stdout
    return [ln for ln in out.splitlines() if ln.strip()]


def main() -> int:
    bad = []
    json_bad = []
    for rel in tracked_files():
        if os.path.splitext(rel)[1].lower() not in TEXT_EXT:
            continue
        path = os.path.join(ROOT, rel)
        try:
            text = open(path, encoding="utf-8").read()
        except (OSError, UnicodeDecodeError):
            continue
        if MARKER_RE.search(text):
            bad.append(rel)
        if rel.endswith(".json"):
            try:
                json.loads(text)
            except ValueError as exc:
                json_bad.append(f"{rel}: {exc}")

    if bad:
        fail(f"committed conflict markers in: {', '.join(bad)} -- resolve and "
             "re-commit; a marker means a merge landed unresolved")
    if json_bad:
        fail("unparsable JSON: " + "; ".join(json_bad) + " -- a rail that reads "
             "this file will crash, as the foreman did on 2026-11-09")

    print(f"OK: no conflict markers, all JSON parses ({len(tracked_files())} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
