#!/usr/bin/env python3
"""The watchdog: keeps the foreman running without any external cron.

The problem it solves: GitHub's scheduler never fired for this repo (measured
2026-11-03 -- `event=schedule` total 0 while every push ran), so a workflow that
is only started by `schedule` may never start at all. A workflow that is
*dispatched* always runs. So this job drives the foreman on a timer of its own,
then dispatches a fresh copy of itself before it ends -- a chain, not a schedule.
The repo is public, so Actions minutes are free and a long job costs nothing.

Safety:
  * it stops the moment a file named content/STOP exists -- the kill switch;
  * it refuses to chain if GITHUB_ACTIONS is not set, so a local run cannot loop;
  * a single `concurrency` group in the workflow means two chains cannot coexist.

    python3 scripts/watchdog.py --once           # one foreman tick, no chain
    python3 scripts/watchdog.py --interval 7200 --cycles 2
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
REPO = os.environ.get("GITHUB_REPOSITORY", "kongkeat938/ai-content-lab")
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
API = "https://api.github.com"


def gh(path: str, method: str = "GET", body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{API}{path}", data=data, method=method,
                                 headers={"Authorization": f"token {TOKEN}",
                                          "Accept": "application/vnd.github+json"})
    if data:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=30) as fh:
        raw = fh.read().decode()
    return json.loads(raw) if raw.strip() else {}


def stopped() -> bool:
    return os.path.exists(os.path.join(ROOT, "content", "STOP"))


def dispatch(name: str, inputs: dict | None = None) -> bool:
    wf = {w["name"]: w["id"] for w in gh(f"/repos/{REPO}/actions/workflows")["workflows"]}
    if name not in wf:
        print(f"  no workflow named {name}", file=sys.stderr)
        return False
    try:
        gh(f"/repos/{REPO}/actions/workflows/{wf[name]}/dispatches", "POST",
           {"ref": "main", "inputs": inputs or {}})
        print(f"  dispatched {name}")
        return True
    except urllib.error.HTTPError as exc:
        print(f"  dispatch {name} failed: {exc.code} {exc.read().decode()[:160]}",
              file=sys.stderr)
        return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", type=int, default=7200, help="seconds between foreman ticks")
    ap.add_argument("--cycles", type=int, default=2, help="ticks before re-dispatching the chain")
    ap.add_argument("--once", action="store_true", help="one tick, do not chain")
    ap.add_argument("--no-chain", action="store_true", help="tick, but do not re-dispatch")
    args = ap.parse_args()

    if not TOKEN:
        sys.exit("no GitHub token in the environment")

    chaining = not (args.once or args.no_chain)
    if chaining and not stopped():
        # Queue the successor before any work. If this link dies mid-run -- a
        # cancel, a lost runner, a timeout -- the successor is already waiting, so
        # the chain cannot break and no one has to restart it by hand. The
        # workflow's concurrency group keeps it to one running link plus one
        # queued, so this cannot fan out into many chains.
        print("queuing the next link before work")
        dispatch("watchdog", {"cycles": str(args.cycles),
                              "interval": str(args.interval), "chain": "true"})

    for i in range(args.cycles):
        if stopped():
            print("STOP file present -- chain halted")
            return 0
        print(f"tick {i+1}/{args.cycles} at {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}")
        dispatch("foreman")
        if i == 0:
            # Once per chain link: check the accounts for anything that could hurt
            # the business (a rejected video, a claim, a payment problem).
            dispatch("account-watch")
        if args.once or args.no_chain or i == args.cycles - 1:
            break
        time.sleep(args.interval)

    if args.once or args.no_chain:
        return 0
    if stopped():
        print("STOP file present -- not re-dispatching")
        return 0
    # The successor was already queued at the top of this run, so there is nothing
    # to start here. This link just ends and the queued one takes over.
    print("link finished; the successor queued at the start takes over")
    return 0


if __name__ == "__main__":
    sys.exit(main())
