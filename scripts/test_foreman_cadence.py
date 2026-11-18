#!/usr/bin/env python3
"""Guard each long-form rail's cadence against the foreman (2026-11-13, swept 2026-11-19).

A rail is dispatched two ways: its own `schedule` crons, and the foreman's "keep
the rail fed" backfill (which fires when the newest build is old). When the night
cadence was raised 1 -> 2/week, the cron was updated but the foreman still only
backfilled after 6 days, so a dropped tick would have waited days. The two must
agree, and the threshold must be DERIVED from the cadence, not a literal that goes
stale.

Swept, never hardcoded (2026-11-19, when genx was raised too): every (workflow,
constant) pair is checked, so raising a third rail cannot silently skip the guard.

    python3 scripts/test_foreman_cadence.py     # exit 0 = every pair agrees
"""
from __future__ import annotations

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import foreman  # noqa: E402

# (workflow file, the foreman constant that must equal its cron count). Add a row
# when a rail gains a cadence of its own.
RAILS = [
    ("night-compilation.yml", "NIGHT_BUILDS_PER_WEEK"),
    ("genx-longform.yml", "GENX_BUILDS_PER_WEEK"),
    ("ch4-longform.yml", "CH4_BUILDS_PER_WEEK"),
]

FAILS = []


def check(name: str, ok: bool, got: str = "") -> None:
    print(("  ok   " if ok else "  FAIL ") + name + (f" -- {got}" if got else ""))
    if not ok:
        FAILS.append(name)


def main() -> int:
    for wf_name, const in RAILS:
        wf = os.path.join(ROOT, ".github", "workflows", wf_name)
        src = open(wf, encoding="utf-8").read()
        n_crons = len(re.findall(r"^\s*-\s*cron:\s*\"", src, re.M))
        want = getattr(foreman, const)
        check(f"{wf_name}: foreman.{const}={want} matches {n_crons} cron(s)",
              n_crons >= 1 and want == n_crons,
              "" if n_crons >= 1 and want == n_crons
              else f"the rail has {n_crons} cron(s); set {const} to match")

    # Every long-form backfill window must be DERIVED, not a stale literal.
    fsrc = open(os.path.join(HERE, "foreman.py"), encoding="utf-8").read()
    for const in [c for _, c in RAILS]:
        check(f"the backfill window uses {const}",
              re.search(rf"backfill_window_days\(\s*{const}\s*\)", fsrc) is not None)

    # A rail that builds more than once a week must NOT pick its theme by ISO week:
    # a week-based index ships the same theme on every build in a week -- the exact
    # "repetitious content" shape the panel warned about (the reason the theme must
    # advance per RUN). Swept over every workflow that carries a THEMES=( array, so
    # a rail added later is covered without editing this list.
    wf_dir = os.path.join(ROOT, ".github", "workflows")
    for name in sorted(os.listdir(wf_dir)):
        if not name.endswith(".yml"):
            continue
        src = open(os.path.join(wf_dir, name), encoding="utf-8").read()
        if "THEMES=(" not in src:
            continue
        n_crons = len(re.findall(r"^\s*-\s*cron:\s*\"", src, re.M))
        week_based = re.search(r"%V\)\s*%", src) is not None
        check(f"{name}: {'multi' if n_crons > 1 else 'single'}-per-week rail "
              f"rotates its theme per run",
              not (n_crons > 1 and week_based),
              "theme index uses date +%V; use a per-run counter" if week_based else "")

    if FAILS:
        print(f"\nFAILED: {FAILS}")
        return 1
    print(f"\nOK: {len(RAILS)} rail cadence(s) agree with the foreman; windows are derived")
    return 0


if __name__ == "__main__":
    sys.exit(main())
