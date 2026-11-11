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
    if health.EXPECTED["foreman"] <= chain_interval:
        fail(f"health EXPECTED['foreman']={health.EXPECTED['foreman']} min is not "
             f"above the {chain_interval:.0f}-min chain tick; it will cry wolf every link")

    # 5b. GENERALISE the rule: for every rail the foreman dispatches past a gate,
    #     health's threshold must sit above gate + one chain tick. Checking only a
    #     hardcoded pair (the original bug) let the same defect survive in
    #     link-shorts (gate 360 + 120 = 480 > EXPECTED 420) -- issue #20 was exactly
    #     that false alarm. Parse every `last_success_min("X")` gate in foreman.py.
    fsrc = open(FOREMAN, encoding="utf-8").read().splitlines()
    gates: dict[str, int] = {}
    for i, line in enumerate(fsrc):
        mm = re.search(r'last_success_min\("([^"]+)"', line)
        if not mm:
            continue
        window = " ".join(fsrc[i:i + 4])
        gm = re.search(r'>\s*([0-9]+(?:\s*\*\s*[0-9]+)*)', window)
        if not gm:
            continue
        val = 1
        for f in re.findall(r"[0-9]+", gm.group(1)):
            val *= int(f)
        gates[mm.group(1)] = val
    if len(gates) < 5:
        fail(f"parsed only {len(gates)} foreman gates; the health-threshold sweep "
             "is not seeing the foreman -- check the regex, not just the thresholds")
    for name, gate in sorted(gates.items()):
        exp = health.EXPECTED.get(name)
        if exp is None:
            continue          # guarded separately by check 6 below
        worst = gate + chain_interval
        if exp <= worst:
            fail(f"health EXPECTED[{name!r}]={exp} min is not above the foreman's "
                 f"{gate}-min gate + a {chain_interval:.0f}-min chain tick ({worst} min); "
                 "it will open a false rail-health issue (this is the issue #20 bug)")

    print(f"OK: health thresholds sit above the real driver cadence "
          f"({len(gates)} foreman gates swept)")

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

    # 7. workflow_ids() must not rely on the API's 30-per-page default. Measured
    #    2026-11-11 the repo has 32 workflows, so the default first page omitted
    #    `watchdog`; the foreman then planned to dispatch it and exited 1 with
    #    "watchdog: no such workflow" -- exactly when the chain is quiet and the
    #    watchdog is the rail that revives it. The static reachability check above
    #    cannot catch this; it needs a run.
    sys.path.insert(0, HERE)
    import foreman as fm  # noqa: E402

    paths = []

    def fake_gh(path, method="GET", body=None):
        paths.append(path)
        if "per_page=100" not in path:
            # What the API really does with no per_page: 30 items, then a next page.
            page = int(re.search(r"page=(\d+)", path).group(1)) if "page=" in path else 1
            names = ["w%d" % i for i in range(page * 30, min(page * 30 + 30, 32))]
            return {"workflows": [{"name": n, "id": i} for i, n in enumerate(names)]}
        page = int(re.search(r"page=(\d+)", path).group(1))
        if page == 1:
            return {"workflows": [{"name": f"w{i}", "id": i} for i in range(100)]}
        return {"workflows": [{"name": "watchdog", "id": 999}]}

    fm.gh = fake_gh
    ids = fm.workflow_ids()
    if not any("per_page=100" in p for p in paths):
        fail("workflow_ids() does not request per_page=100; with >30 workflows "
             "the default first page omits some and the foreman exits 1 on a "
             "dispatch it cannot resolve")
    if ids.get("watchdog") != 999:
        fail("workflow_ids() did not follow the next page; a workflow past the "
             "first 100 would be invisible to the foreman")

    print("OK: workflow_ids() requests per_page=100 and pages past it")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
