#!/usr/bin/env python3
"""A long-form build must fit inside the job that runs it.

Measured 2026-11-28: `night-compilation` defaulted to a 120-minute video and its job
had a 120-minute limit. The dispatched run started rendering at 07:48Z and was
cancelled by the limit at 09:47Z, still inside "Build and verify" -- so the default
length could never publish, and every long-form attempt looked like a failure for a
reason nobody could see in the log. The render needs roughly `minutes` of runner time
plus setup, so the job budget must sit well above the longest allowed input.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NEEDS_HEADROOM = 1.25   # a 4-vCPU runner renders a 4K minute in ~1.1-1.2 min
SETUP_MINUTES = 15


def read_minutes(wf: str) -> int:
    m = re.search(r'minutes:\n(?:\s+description:.*\n)?\s+default:\s*"(\d+)"', wf)
    if not m:
        raise SystemExit("FAIL: no minutes input default found")
    return int(m.group(1))


def read_timeout(wf: str) -> int:
    m = re.search(r"timeout-minutes:\s*(\d+)", wf)
    if not m:
        raise SystemExit("FAIL: no timeout-minutes on the job")
    return int(m.group(1))


def check(name: str) -> str:
    wf = open(os.path.join(ROOT, ".github", "workflows", name), encoding="utf-8").read()
    minutes, budget = read_minutes(wf), read_timeout(wf)
    need = minutes * NEEDS_HEADROOM + SETUP_MINUTES
    if budget < need:
        raise SystemExit(
            f"FAIL: {name} defaults to a {minutes}-min video but the job only has "
            f"{budget} min; it needs >= {need:.0f} min (measured: a 120-min render "
            f"exceeded a 120-min limit)")
    return f"ok   {name}: {minutes}-min video inside a {budget}-min job (needs >= {need:.0f})"


def main() -> int:
    # the guard must be able to fail: a job that cannot finish its own default is a bug
    fake = 'minutes:\n        default: "120"\ntimeout-minutes: 120'
    try:
        mins = int(re.search(r'default:\s*"(\d+)"', fake).group(1))
        budget = int(re.search(r"timeout-minutes:\s*(\d+)", fake).group(1))
        if budget >= mins * NEEDS_HEADROOM + SETUP_MINUTES:
            raise SystemExit("FAIL: the reversed case would pass; the guard checks nothing")
    except AttributeError:
        raise SystemExit("FAIL: could not parse the reversed case")
    print("ok   the reversed case (120-min video, 120-min job) is rejected")
    for name in ("night-compilation.yml", "genx-longform.yml"):
        print(check(name))
    return 0


if __name__ == "__main__":
    sys.exit(main())
