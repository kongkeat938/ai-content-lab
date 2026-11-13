#!/usr/bin/env python3
"""A channel that is not paused must be in every rail that produces for it.

Measured 2026-11-13: pausing kongkeat removed it from the `matrix.include` of
publish-shorts / grow-shorts-pool / remake-shorts (a correct move at the time).
UNPAUSING it cleared content/PAUSED and restored the ch4 schedules -- but nobody
put kongkeat back into those three matrices, so the team's new Shorts would never
have reached the feed. The rail looked healthy and produced nothing.

This guard sweeps the workflow matrices and enforces the invariant:

    a channel is in a rail's matrix  <=>  it is NOT named in content/PAUSED

So it fails both ways: a non-paused channel missing from a matrix (a silent drop)
and a paused channel still in a matrix (wasteful CI the workflow's own tripwire
would abort anyway).

    python3 scripts/test_rail_channels.py
"""
from __future__ import annotations

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

# rail workflow -> (matrix key, registry module, registry attribute)
# The registry is the source of truth for the full channel set, so the guard
# never hardcodes the list of channels (a hardcoded set cannot notice a new one).
RAILS = {
    "publish-shorts.yml": ("channel", "publish_shorts", "CHANNELS"),
    "remake-shorts.yml": ("slug", "publish_shorts", "CHANNELS"),
    "grow-shorts-pool.yml": ("channel", "gen_short_scripts", "CHANNELS"),
}

FAILS: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" -- {detail}" if detail and not ok else ""))
    if not ok:
        FAILS.append(name)


def paused(root: str) -> set:
    path = os.path.join(root, "content", "PAUSED")
    try:
        with open(path, encoding="utf-8") as fh:
            return {ln.strip() for ln in fh if ln.strip() and not ln.startswith("#")}
    except OSError:
        return set()


def matrix_names(workflow: str, key: str) -> set:
    text = open(workflow, encoding="utf-8").read()
    return set(re.findall(rf"^\s*-\s*{key}:\s*(\S+)\s*$", text, re.M))


def main() -> int:
    import importlib

    for wf, (key, mod_name, attr) in RAILS.items():
        mod = importlib.import_module(mod_name)
        registry = set(getattr(mod, attr))
        path = os.path.join(ROOT, ".github", "workflows", wf)
        present = matrix_names(path, key)
        p = paused(ROOT)
        # A paused channel keeps its manifest but must not be produced for; a
        # non-paused one must be produced for. Both spellings live in PAUSED, so
        # compare against the registry names plus the ch4 long-form slug.
        paused_here = {c for c in registry if c in p or f"{c}-story" in p}
        expected = registry - paused_here
        print(f"{wf} (matrix key '{key}', registry {mod_name}.{attr})")
        missing = expected - present
        extra = present - expected
        check("every non-paused channel is in the matrix", not missing, str(missing))
        check("no paused channel is left in the matrix", not extra, str(extra))

    print()
    if FAILS:
        print(f"FAIL: {len(FAILS)} check(s) failed: {FAILS}")
        return 1
    print("OK: every rail's matrix matches content/PAUSED (nothing dropped, nothing stale)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
