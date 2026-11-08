#!/usr/bin/env python3
"""Guard the self-timer so it cannot need a hand to keep running.

The chain is the one thing that has to survive on its own: if it stops, every
scheduled rail stops with it and only a person could restart it. Two properties
keep that from happening, and this test locks both:

  1. A link queues its successor BEFORE it does any work, so a link that is
     cancelled or times out mid-run leaves the next one already waiting.
  2. A link never needs a hand to start: the foreman revives the chain when it
     goes quiet, and the workflow carries a backup schedule.

    python3 scripts/test_watchdog.py     # exit 0 = the chain heals itself
"""
from __future__ import annotations

import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SCRIPT = os.path.join(HERE, "watchdog.py")
FOREMAN = os.path.join(HERE, "foreman.py")
WORKFLOW = os.path.join(ROOT, ".github", "workflows", "watchdog.yml")


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def main() -> int:
    src = open(SCRIPT, encoding="utf-8").read()

    # 1. The successor dispatch must come before the tick loop, not after it.
    queue_at = src.find('print("queuing the next link before work")')
    loop_at = src.find("for i in range(args.cycles):")
    if queue_at < 0:
        fail("watchdog.py no longer queues its successor before work; a link that "
             "dies mid-run would break the chain")
    if loop_at < 0 or queue_at > loop_at:
        fail("the successor dispatch is not before the tick loop")

    # 2. The chain must not be startable only by hand.
    fm = open(FOREMAN, encoding="utf-8").read()
    if 'plan.append(("watchdog"' not in fm:
        fail("foreman.py no longer revives the watchdog; a dead chain would stay dead")
    wf = open(WORKFLOW, encoding="utf-8").read()
    if "schedule:" not in wf:
        fail("watchdog.yml has no backup schedule; if the chain dies nothing restarts it")

    # 3. The kill switch must still work, so a person can stop it on purpose.
    if "content" not in src or "STOP" not in src:
        fail("the STOP kill switch is gone from watchdog.py")

    # 4. Every workflow must be reachable without a person. GitHub's cron is
    #    unreliable here (measured: the */30 foreman cron fired once in 30 runs),
    #    so a rail that lives only on a `schedule` can be missed for days. The
    #    foreman must name every workflow except the foreman itself (the watchdog
    #    drives that one). A new workflow added with only a schedule would silently
    #    never run, so this fails until the foreman knows about it.
    #
    #    A workflow with no `schedule` at all is exempt: it is on-demand by design
    #    (it takes inputs, or a person runs it), so it is not a rail that can be
    #    missed. Demanding the foreman dispatch it would be wrong -- the foreman
    #    would call it with no inputs.
    referenced = set(re.findall(r'plan\.append\(\("([^"]+)"', fm))
    for path in sorted(glob.glob(os.path.join(ROOT, ".github", "workflows", "*.yml"))):
        text = open(path, encoding="utf-8").read()
        m = re.search(r"^name:\s*(.+)$", text, re.M)
        if not m:
            fail(f"{os.path.basename(path)} has no name; the foreman cannot address it")
        name = m.group(1).strip().strip('"')
        if name in ("foreman", "watchdog"):
            continue
        if re.search(r"^\s{2}schedule:", text, re.M) is None:
            continue
        if name not in referenced:
            fail(f"the foreman never dispatches {name!r} ({os.path.basename(path)}); "
                 "with only a schedule it may never run -- add a rule in foreman.py")

    print("OK: successor queued before work, foreman revives the chain, backup "
          "schedule present, every workflow is foreman-reachable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
