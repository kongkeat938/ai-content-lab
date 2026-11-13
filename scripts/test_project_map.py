#!/usr/bin/env python3
"""The project map must exist, and no live script may be an orphan.

K (2026-11-13): the repo got messy -- work that already existed was redone under a
new name, so a search took long or found nothing. Two properties lock that out:

  1. `docs/PROJECT-MAP.md` exists and names the one project goal. It is the anchor
     every agent reads first.
  2. Every non-test script in `scripts/` (excluding `scripts/legacy/`, which is the
     archive) is referenced somewhere else -- a script nobody calls is either dead
     or a second copy of something that already exists.

This guard can FAIL: remove the map, or add an unreferenced `scripts/foo.py`, and it
exits 1. A guard that only checks the happy path proves nothing.

    python3 scripts/test_project_map.py     # exit 0 = map present, no orphan script
"""
from __future__ import annotations

import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MAP = os.path.join(ROOT, "docs", "PROJECT-MAP.md")

# Scripts kept for the record, called by hand or by nothing -- not part of a rail.
ALLOW_ORPHAN = {
    "test_project_map",     # this guard itself
}


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def tracked_text() -> dict[str, str]:
    files = subprocess.run(["git", "-C", ROOT, "ls-files"], capture_output=True,
                           text=True, check=True).stdout.split()
    out = {}
    for rel in files:
        if os.path.splitext(rel)[1].lower() not in {".py", ".yml", ".yaml", ".sh", ".md", ".json"}:
            continue
        try:
            out[rel] = open(os.path.join(ROOT, rel), encoding="utf-8").read()
        except (OSError, UnicodeDecodeError):
            continue
    return out


def main() -> int:
    if not os.path.exists(MAP):
        fail("docs/PROJECT-MAP.md is missing -- the one map that anchors the project is gone")
    text = open(MAP, encoding="utf-8").read()
    if "yt938-2" not in text:
        fail("docs/PROJECT-MAP.md does not name the project `yt938-2`")

    corpus = tracked_text()
    scripts = sorted(f for f in corpus
                     if f.startswith("scripts/") and f.endswith(".py")
                     and not f.startswith("scripts/legacy/")
                     and not os.path.basename(f).startswith("test_"))
    orphans = []
    for rel in scripts:
        name = os.path.splitext(os.path.basename(rel))[0]
        if name in ALLOW_ORPHAN:
            continue
        pattern = re.compile(r"\b" + re.escape(name) + r"\b")
        refs = [f for f, body in corpus.items() if f != rel and pattern.search(body)]
        if not refs:
            orphans.append(rel)

    print(f"project map present; live scripts = {len(scripts)}; orphans = {len(orphans)}")
    if orphans:
        for o in orphans:
            print(f"  orphan: {o}")
        fail("a live script is referenced nowhere -- archive it under scripts/legacy/ "
             "or name it in docs/PROJECT-MAP.md (it may be a second copy of an existing one)")
    print("OK: the map exists and no live script is an orphan")
    return 0


if __name__ == "__main__":
    sys.exit(main())
