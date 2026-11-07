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

    print("OK: successor queued before work, foreman revives the chain, backup schedule present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
