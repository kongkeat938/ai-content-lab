#!/usr/bin/env python3
"""The foreman: one job that drives every rail, so the channel runs without cron.

GitHub's own scheduler never fired for this repo -- measured 2026-11-03, `event=schedule`
total_count 0 while every push ran -- so nothing may depend on a cron expression. A job
that is *started* can start the others. That is all this does: look at what is due, and
dispatch the workflow that does it. It decides nothing about content; the rails own their
own ledgers and their own double-post guards.

    python3 scripts/foreman.py --dry-run     # say what it would dispatch
    python3 scripts/foreman.py               # dispatch what is due

Idempotent by construction: a rail that already did its job is not dispatched again,
because the due-check reads the same ledgers the rails write. Running the foreman twice
in a row dispatches nothing the second time.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
REPO = os.environ.get("GITHUB_REPOSITORY", "kongkeat938/ai-content-lab")
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or os.environ.get("KONGKEAT_GH_TOKEN")
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


def load(rel: str, default):
    p = os.path.join(ROOT, rel)
    if not os.path.exists(p):
        return default
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def now() -> datetime:
    return datetime.now(timezone.utc)


def parse(iso: str) -> datetime:
    return datetime.fromisoformat(iso.replace("Z", "+00:00"))


def workflow_ids() -> dict:
    return {w["name"]: w["id"] for w in gh(f"/repos/{REPO}/actions/workflows")["workflows"]}


def recent(name: str, ids: dict) -> list:
    """Runs of one workflow, newest first (by name via the id list)."""
    if name not in ids:
        return []
    d = gh(f"/repos/{REPO}/actions/workflows/{ids[name]}/runs?per_page=10")
    return d["workflow_runs"]


def last_success_min(name: str, ids: dict) -> float | None:
    for r in recent(name, ids):
        if r["conclusion"] == "success":
            return (now() - parse(r["created_at"])).total_seconds() / 60
    return None


def busy(name: str, ids: dict) -> bool:
    """A run of this workflow is already going -- do not start a second."""
    for r in recent(name, ids):
        if r["status"] in ("in_progress", "queued", "pending"):
            return True
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if not TOKEN:
        sys.exit("no GitHub token in the environment (GH_TOKEN / GITHUB_TOKEN)")

    ids = workflow_ids()
    plan: list[tuple[str, dict]] = []

    # 1. Covers: due whenever the manifest holds an entry whose thumbnail is not
    #    confirmed live. set_thumbnails is idempotent and defers on quota, so the
    #    cheap correct move is: if anything is queued and the rail has not run in
    #    the last 3 h, dispatch it.
    thumbs = load("content/ch2_thumbnails.json", {"thumbnails": {}})
    t_age = last_success_min("set-thumbnails", ids)
    if thumbs.get("thumbnails") and (t_age is None or t_age > 180):
        plan.append(("set-thumbnails", {}))

    # 2. Long videos: due whenever an entry has no id and its hold has passed.
    pub = load("content/ch2_publish.json", {"videos": []})
    due_long = [v for v in pub["videos"] if not v.get("video_id")
                and (not v.get("not_before") or parse(v["not_before"]) <= now())]
    if due_long:
        plan.append(("publish-batch", {}))

    # 3. Shorts: drip a couple per dispatch, but only for a channel that still
    #    has material and has not exhausted its daily upload slots. The workflow
    #    is a matrix over the channels, so one dispatch covers both; a capped
    #    channel's job short-circuits on its own limit note.
    channels = [
        ("dharma", "content/ch2_shorts.json", "content/ch2_shorts/scripts.json",
         "UCM3QO5L_pmj34n1JVlbhh-w"),
        ("genx", "content/ch1_shorts.json", "content/ch1_shorts/scripts.json",
         "UCI6EfsgM1HNjrYarvigxyrQ"),
        ("kongkeat", "content/ch4_shorts.json", "content/ch4_shorts/scripts.json",
         "UC7gCIu4G_7QCEJ8hJ-34zoQ"),
    ]
    limits = load("content/upload_limit.json", {})
    if not isinstance(limits, dict):
        limits = {}
    limits = limits.get("channels", limits)   # tolerate the pre-2026-11-03 flat shape
    waiting: dict[str, int] = {}
    capped: dict[str, bool] = {}
    for slug, man_rel, pool_rel, cid in channels:
        man = load(man_rel, {"shorts": {}})
        pool = load(pool_rel, [])
        waiting[slug] = len([s for s in pool if s["id"] not in man["shorts"]])
        rec = limits.get(cid, {}) if isinstance(limits, dict) else {}
        capped[slug] = bool(rec.get("reset_at")) and parse(rec["reset_at"]) > now()
        if capped[slug]:
            print(f"  {slug}: upload slots exhausted until {rec['reset_at']}")
    # Only dispatch when a channel both has material and can actually upload it;
    # while every channel is capped the job would short-circuit on the same note,
    # so dispatching it just spends a runner for nothing.
    if any(waiting[s] and not capped[s] for s in waiting):
        plan.append(("publish-shorts", {"per_run": "2"}))

    # 4. Refill a pool before it empties: ask Gemini when fewer than 8 remain.
    if any(n < 8 for n in waiting.values()):
        g_age = last_success_min("grow-shorts-pool", ids)
        if g_age is None or g_age > 20 * 60:
            plan.append(("grow-shorts-pool", {"count": "8"}))

    # 4b. Keep the funnel wired. A Short is only worth the reach it forwards, and
    #     every new Short that the drip posts needs the playlist link. GitHub's
    #     scheduler never fires here, so the daily link-shorts cron cannot be
    #     relied on -- dispatch it from the chain, at most once every 6 h.
    l_age = last_success_min("link-shorts", ids)
    if l_age is None or l_age > 6 * 60:
        plan.append(("link-shorts", {}))

    # 5. Keep the long rail fed: a weekly 2-hour build if the newest one is over
    #    6 days old. night-compilation fingerprints its own content, so a repeat
    #    on unchanged material is a cheap skip, not a 40-minute render.
    n_age = last_success_min("night-compilation", ids)
    if n_age is None or n_age > 6 * 24 * 60:
        plan.append(("night-compilation", {}))

    # 6. Self-heal the timer. If the watchdog chain has gone quiet, revive it --
    #    any push runs the foreman, so a broken chain repairs itself on the next
    #    commit instead of staying dead until someone notices.
    w_age = last_success_min("watchdog", ids)
    if w_age is None or w_age > 3 * 60:
        plan.append(("watchdog", {"cycles": "2", "interval": "7200", "chain": "true"}))

    # Drop anything already running, so a slow job is not double-started.
    plan = [(n, i) for n, i in plan if not busy(n, ids)]

    print(f"foreman: {len(plan)} dispatch(es)")
    for name, inputs in plan:
        print(f"  {name} {inputs or ''}")

    if args.dry_run:
        return 0
    rc = 0
    for name, inputs in plan:
        if name not in ids:
            print(f"  {name}: no such workflow", file=sys.stderr)
            rc = 1
            continue
        try:
            gh(f"/repos/{REPO}/actions/workflows/{ids[name]}/dispatches", "POST",
               {"ref": "main", "inputs": inputs})
            print(f"  dispatched {name}")
        except urllib.error.HTTPError as exc:
            print(f"  dispatch {name} failed: {exc.code} {exc.read().decode()[:160]}",
                  file=sys.stderr)
            rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
