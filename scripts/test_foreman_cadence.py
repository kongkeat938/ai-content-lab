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


def cron_weekdays(src: str) -> list[int]:
    """The weekdays (0=Sun..6=Sat) a workflow's crons land on.

    Only `* * *` day-of-week crons with a fixed weekday are counted; a `*`
    (every day) is ignored because it has no inter-build gap to reason about.
    """
    days = []
    for m in re.finditer(r"^\s*-\s*cron:\s*\"([^\"]+)\"", src, re.M):
        parts = m.group(1).split()
        if len(parts) != 5:
            continue
        dow = parts[4]
        if dow.isdigit():
            days.append(int(dow) % 7)
    return sorted(set(days))


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

        # The backfill window must EXCEED the longest real gap between crons, or the
        # foreman fires an extra build every week (measured 2026-11-19: a Mon/Wed/Thu
        # dharma rail has a 4-day Thu->Mon gap but a 7/3+1 = 3.33-day window).
        # The gap set is a cycle, so its max is rotation-invariant (sorting the
        # weekdays is safe: Sun=0 wraps correctly) and it must always sum to 7 --
        # that sum is the invariant that catches a cron-parsing slip.
        days = cron_weekdays(src)
        if len(days) > 1:
            gaps = [days[i + 1] - days[i] for i in range(len(days) - 1)]
            gaps.append((days[0] + 7) - days[-1])
            window = foreman.backfill_window_days(want)
            check(f"{wf_name}: backfill window {window:.2f}d > max cron gap {max(gaps)}d",
                  window > max(gaps),
                  "" if window > max(gaps) else "space the crons evenly or the foreman over-fires")
            check(f"{wf_name}: cron gaps sum to 7 (parsed {days})", sum(gaps) == 7)

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

    # The health report must be able to SEE a silence on these rails. Measured
    # 2026-11-19: all three carried the literal 11520 (8 d) while the night rail's
    # real backfill window is 3.33 d, so a night rail dead for 6 days still read
    # "all rails fresh" -- the one report that exists to catch a silence could not.
    # The watchdog sweep cannot cover this: it parses numeric `> N` gates only, so
    # a window derived through backfill_window_days() is invisible to it.
    #
    # Two bounds, both needed. Below the foreman's window is a false alarm on a
    # healthy rail. Above twice that window is a silence the report would miss --
    # the shape the old 8-day literals had (night: 2.4x its own window).
    import health  # noqa: PLC0415
    for wf_name, const in RAILS:
        rail = wf_name.removesuffix(".yml")
        exp = health.EXPECTED.get(rail)
        if exp is None:
            check(f"health watches {wf_name}", False, "add it to health.EXPECTED")
            continue
        window_min = foreman.backfill_window_days(getattr(foreman, const)) * 24 * 60
        check(f"{wf_name}: health threshold {exp} min is inside "
              f"({window_min:.0f}, {2 * window_min:.0f}] min",
              window_min < exp <= 2 * window_min,
              "" if window_min < exp <= 2 * window_min
              else ("too tight: fires on a healthy rail" if exp <= window_min
                    else "too loose: a rail dead twice its window still reads fresh"))

    # And it must be DERIVED. A literal that happens to pass today is the exact
    # shape that went stale when the cadence was raised 2 -> 3/week.
    hsrc = open(os.path.join(HERE, "health.py"), encoding="utf-8").read()
    for _, const in RAILS:
        check(f"health derives the threshold from {const}",
              re.search(rf"longform_expected\(\s*foreman\.{const}", hsrc) is not None)

    if FAILS:
        print(f"\nFAILED: {FAILS}")
        return 1
    print(f"\nOK: {len(RAILS)} rail cadence(s) agree with the foreman; windows are derived")
    return 0


if __name__ == "__main__":
    sys.exit(main())
