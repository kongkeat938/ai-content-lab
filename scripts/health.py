#!/usr/bin/env python3
"""Health of the channel rails -- what is live, what is due, what has gone stale.

Answers one question at a time, with numbers: *is the machine still working?*
A rail that silently stops is the failure this exists to catch. GitHub's own
scheduler never fired for this repo (measured 2026-11-03: `event=schedule` total
0 while every push triggered), so "the cron will run it" is not evidence that
anything ran. Only the last successful run time is.

    python3 scripts/health.py              # print a report, exit 1 if stale
    python3 scripts/health.py --write      # also write docs/HEALTH.md
    python3 scripts/health.py --json       # machine-readable

Stale means: a rail whose last successful run is older than its own interval by a
margin. A rail that has never run is stale, not fine -- silence is the bug.
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

# workflow name -> (how often it should succeed, in minutes)
EXPECTED = {
    "set-thumbnails": 180,
    "publish-shorts": 300,
    "publish-batch": 400,
    "grow-shorts-pool": 1600,
    "foreman": 400,          # the driver itself must not die
}


def gh(path: str) -> dict:
    req = urllib.request.Request(f"https://api.github.com{path}",
                                 headers={"Authorization": f"token {TOKEN}",
                                          "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=30) as fh:
        return json.load(fh)


def load(rel: str, default):
    p = os.path.join(ROOT, rel)
    if not os.path.exists(p):
        return default
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def last_runs() -> dict:
    """The newest run of each watched workflow, and its newest *successful* run.

    Read per workflow, not from one repo-wide page. A single
    `/actions/runs?per_page=60` page holds only the most recent ~60 runs across
    every workflow; on a busy day `pages build and deployment` alone fills it, so
    a slow rail's last success slides out of the window and is reported STALE
    although it ran (measured 2026-11-04: grow-shorts-pool succeeded 01:59Z but
    the 60-run page only reached back to 04:30Z). Querying the workflow's own
    endpoint makes the window the workflow's, not the repo's.
    """
    out: dict = {}
    for name in EXPECTED:
        try:
            runs = gh(f"/repos/{REPO}/actions/workflows/{name}.yml/runs?per_page=30")
        except Exception as exc:  # network, auth, rate limit
            return {"_error": str(exc)[:120]}
        items = runs.get("workflow_runs", [])
        if not items:
            continue
        last = items[0]
        success = next((r for r in items if r["conclusion"] == "success"), None)
        out[name] = {"last": last["created_at"], "last_status": last["conclusion"],
                     "last_success": success["created_at"] if success else None}
    return out


def age_min(iso: str | None) -> float | None:
    if not iso:
        return None
    when = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return (datetime.now(timezone.utc) - when).total_seconds() / 60


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    runs = last_runs()
    pub = load("content/ch2_publish.json", {"videos": []})
    thumbs = load("content/ch2_thumbnails.json", {"thumbnails": {}})
    limits = load("content/upload_limit.json", {}).get("channels", {})

    # Shorts now run on more than one channel; report each, not just ch2.
    SHORTS = {
        "dharma": ("content/ch2_shorts.json", "content/ch2_shorts/scripts.json",
                   "UCM3QO5L_pmj34n1JVlbhh-w"),
        "genx": ("content/ch1_shorts.json", "content/ch1_shorts/scripts.json",
                 "UCI6EfsgM1HNjrYarvigxyrQ"),
    }

    due_long = [v["key"] for v in pub["videos"]
                if not v.get("video_id") and (not v.get("not_before")
                or datetime.fromisoformat(v["not_before"].replace("Z", "+00:00")) <= datetime.now(timezone.utc))]
    held_long = [v["key"] for v in pub["videos"]
                 if not v.get("video_id") and v.get("not_before")
                 and datetime.fromisoformat(v["not_before"].replace("Z", "+00:00")) > datetime.now(timezone.utc)]
    live_long = [v["key"] for v in pub["videos"] if v.get("video_id")]

    shorts: dict = {}
    for slug, (man_rel, pool_rel, cid) in SHORTS.items():
        man = load(man_rel, {"shorts": {}})
        pool = load(pool_rel, [])
        rec = limits.get(cid, {})
        capped = bool(rec.get("reset_at")) and datetime.fromisoformat(
            rec["reset_at"].replace("Z", "+00:00")) > datetime.now(timezone.utc)
        shorts[slug] = {"live": len(man["shorts"]), "pool": len(pool),
                        "waiting": len([s for s in pool if s["id"] not in man["shorts"]]),
                        "capped_until": rec.get("reset_at") if capped else None}

    stale = []
    if "_error" not in runs:
        for name, every in EXPECTED.items():
            e = runs.get(name)
            # publish-batch only has work when a long video is due; a long quiet
            # gap between long videos is the plan, not a fault.
            if name == "publish-batch" and not due_long:
                continue
            if not e or not e.get("last_success"):
                stale.append(f"{name}: never succeeded")
                continue
            a = age_min(e["last_success"])
            if a is not None and a > every:
                stale.append(f"{name}: last success {a/60:.1f} h ago (expected <= {every/60:.1f} h)")
        for slug, s in shorts.items():
            if s["waiting"] == 0 and not s["capped_until"]:
                stale.append(f"{slug}: pool empty and not capped -- the rail has nothing to ship")

    report = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "runs": runs,
        "live_long": live_long,
        "due_long": due_long,
        "held_long": held_long,
        "shorts": shorts,
        "thumbnails_queued": len(thumbs["thumbnails"]),
        "stale": stale,
    }

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1 if stale else 0

    lines = [f"# Channel health — {report['generated']}", ""]
    lines.append(f"- long videos live: **{len(live_long)}** {live_long}")
    if due_long:
        lines.append(f"- long videos DUE now: {due_long}")
    if held_long:
        lines.append(f"- long videos held for cadence: {held_long}")
    lines.append(f"- thumbnails queued: {len(thumbs['thumbnails'])}")
    lines.append("")
    lines.append("## shorts")
    for slug, s in shorts.items():
        cap = f", capped until {s['capped_until']}" if s["capped_until"] else ""
        lines.append(f"- {slug}: {s['live']} live of {s['pool']} in the pool "
                     f"({s['waiting']} waiting{cap})")
    lines.append("")
    lines.append("## rails")
    if "_error" in runs:
        lines.append(f"- could not read runs: {runs['_error']}")
    else:
        for name in sorted(EXPECTED):
            e = runs.get(name)
            if not e:
                lines.append(f"- {name}: **never ran**")
                continue
            a = age_min(e.get("last_success"))
            last = age_min(e["last"])
            lines.append(f"- {name}: last {e['last_status']} {last:.0f} min ago; "
                         f"last success {'never' if a is None else f'{a/60:.1f} h ago'}")
    lines.append("")
    if stale:
        lines.append("## STALE")
        lines += [f"- {s}" for s in stale]
    else:
        lines.append("## all rails fresh")

    text = "\n".join(lines) + "\n"
    print(text)
    if args.write:
        with open(os.path.join(ROOT, "docs", "HEALTH.md"), "w", encoding="utf-8") as fh:
            fh.write(text)
    return 1 if stale else 0


if __name__ == "__main__":
    sys.exit(main())
