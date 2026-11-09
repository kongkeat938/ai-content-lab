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

    # 5. The health thresholds must sit ABOVE the real driver cadence, or the
    #    alert fires on a healthy system and the channel learns to ignore it.
    #    Measured 2026-11-09: EXPECTED["foreman"] was 90 min while the chain ticks
    #    the foreman every 2 h, and EXPECTED["set-thumbnails"] was 90 min while the
    #    foreman only dispatches that rail past a 180-min gate -- so 11 rail-health
    #    issues opened and closed in two days, each a false alarm.
    sys.path.insert(0, HERE)
    import health  # noqa: PLC0415
    m = re.search(r'interval:.*?default:\s*"(\d+)"', wf, re.S)
    if not m:
        fail("cannot read the chain interval from watchdog.yml; the health "
             "thresholds cannot be checked against it")
    chain_interval = int(m.group(1)) / 60            # seconds -> minutes
    fm_gate = 180   # the set-thumbnails / ch4-realign style gate in foreman.py, minutes
    if health.EXPECTED["foreman"] <= chain_interval:
        fail(f"health EXPECTED['foreman']={health.EXPECTED['foreman']} min is not "
             f"above the {chain_interval:.0f}-min chain tick; it will cry wolf every link")
    if health.EXPECTED["set-thumbnails"] <= fm_gate:
        fail(f"health EXPECTED['set-thumbnails']={health.EXPECTED['set-thumbnails']} "
             f"min is not above the foreman's {fm_gate}-min dispatch gate")

    print("OK: health thresholds sit above the real driver cadence")

    # 6. Every rail the foreman drives must also be watched by health.py, or it
    #    can fail with nobody told. Measured 2026-11-09: "fetch music" had been
    #    failing for a day and was not in EXPECTED, so health.py said "all rails
    #    fresh". Exempt: the watchdog (it watches itself), and the condition-gated
    #    rails, which are legitimately idle when they have nothing to do (a fixed
    #    age threshold on those would be a false alarm).
    CONDITION_GATED = {"watchdog", "apply-packaging", "remove-bad-cut", "remake shorts"}
    unwatched = [n for n in sorted(referenced) if n not in health.EXPECTED]
    unwatched = [n for n in unwatched if n not in CONDITION_GATED]
    if unwatched:
        fail(f"health.py does not watch {unwatched}; a rail the foreman drives but "
             "health ignores can fail silently -- add it to health.EXPECTED (or to "
             "the condition-gated exemption)")

    print("OK: every foreman-driven rail is watched by health.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
