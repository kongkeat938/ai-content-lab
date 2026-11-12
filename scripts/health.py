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
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
REPO = os.environ.get("GITHUB_REPOSITORY", "kongkeat938/ai-content-lab")
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or os.environ.get("KONGKEAT_GH_TOKEN")

# workflow name -> (how often it should succeed, in minutes)
# Intervals are set against the rail's REAL driver, not its nominal cron. GitHub's
# cron is unreliable here (measured 2026-11-07), so most rails are actually driven
# by the watchdog chain, which ticks the foreman every 2 h -- a threshold below
# that fires on a perfectly healthy chain. A weekly rail gets 8 days. Silence is
# the bug: a rail that has never succeeded is stale, not fine.
EXPECTED = {
    "foreman": 240,              # the driver; the chain ticks it every 2 h, so allow one dropped tick
    "set-thumbnails": 360,       # foreman gate 180 + one 120-min chain tick
    "publish-shorts": 420,       # 01:30 + 13:30 + the chain
    "publish-batch": 400,        # */3h, but only counts when a long video is due
    "link-shorts": 540,          # foreman gate 360 + one 120-min chain tick
    "grow-shorts-pool": 1700,    # daily 22:00 + the chain
    "ch4-realign": 1700,         # daily 08:05 + the chain
    "polish-all": 1700,          # daily 08-11 + the chain
    "progress": 1700,            # daily 07:12
    "account-watch": 1700,       # daily 08:42
    "publish-ch1": 1700,
    "publish-ch4": 1700,
    "watch-hours": 11520,        # weekly
    "check-duplicates": 11520,   # weekly Monday
    "night-compilation": 11520,  # weekly Monday
    "genx-longform": 11520,      # weekly Tuesday
    "ch4-longform": 11520,       # weekly Thursday
    # Driven only by the chain (no reliable cron). They were invisible to this
    # report until 2026-11-09, which is how "fetch music" failed for a day with
    # nobody told: an unwatched rail looks exactly like a working one. The
    # thresholds are the foreman's own gate plus ~1.5x, since the chain can drop
    # a tick. "remake shorts" is deliberately absent: it is condition-gated (it
    # runs only while a Short still needs remaking), so a fixed age would be a
    # false alarm once every Short is remade.
    "studio-ai": 2880,           # foreman gate 20 h (the learning brain)
    "selftest": 2880,            # foreman gate 20 h
    "counter-ledger": 2880,      # foreman gate 20 h
    "ch2-playlists": 2880,       # foreman gate 24 h
    "channel-branding": 2880,    # foreman gate 24 h (branding is a standing invariant)
    "fetch music": 11520,        # foreman gate 6 d
    "short doors": 11520,        # foreman gate 6 d
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

    The endpoint is addressed by numeric workflow id, resolved from the workflow
    list. Addressing by file name breaks on any rail whose display name differs
    from its file name ("fetch music" vs fetch-music.yml) -- the 404 used to blank
    the whole report via the `_error` path (fixed 2026-11-09).
    """
    try:
        wfs = gh(f"/repos/{REPO}/actions/workflows?per_page=100").get("workflows", [])
    except Exception as exc:  # network, auth, rate limit
        return {"_error": str(exc)[:120]}
    by_name = {w["name"]: w["id"] for w in wfs}
    out: dict = {}
    for name in EXPECTED:
        wid = by_name.get(name)
        if wid is None:
            continue
        try:
            runs = gh(f"/repos/{REPO}/actions/workflows/{wid}/runs?per_page=30")
        except Exception:  # one unreadable rail must not blank the whole report
            continue
        items = runs.get("workflow_runs", [])
        if not items:
            # A workflow that has runs cannot return an empty list; a transient
            # empty page (proxy blip, rate limit) does. Retry once, and if it is
            # still empty mark it UNREADABLE -- never "never succeeded", which
            # would cry wolf on a rail that is fine (measured 2026-11-12:
            # set-thumbnails read as "never succeeded" while it had 29 successes).
            for _ in range(2):
                time.sleep(1.0)
                try:
                    items = gh(f"/repos/{REPO}/actions/workflows/{wid}/runs?per_page=30"
                               ).get("workflow_runs", [])
                except Exception:
                    items = []
                if items:
                    break
            if not items:
                out[name] = {"unreadable": True}
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


ALERT_TITLE = "rail health: an automation has gone quiet"


def upsert_alert(stale: list, generated: str) -> None:
    """Open an issue when a rail goes quiet, and close it when all are fresh.

    Writing docs/HEALTH.md is not enough: the foreman runs health with `|| true`,
    so a STALE section sat in a file nobody opened. The alert has to arrive where
    it will be seen -- a GitHub issue -- and it must clear itself, or the channel
    is trained to ignore it.
    """
    repo = os.environ.get("GITHUB_REPOSITORY", REPO)
    try:
        listed = subprocess.run(["gh", "issue", "list", "--repo", repo, "--state", "open",
                                 "--search", ALERT_TITLE, "--json", "number,title"],
                                capture_output=True, text=True, check=True)
        existing = next((i for i in json.loads(listed.stdout or "[]")
                         if i["title"] == ALERT_TITLE), None)
        if stale:
            body = "\n".join(
                [f"Measured {generated}. These automations are not behaving:", ""]
                + [f"- {s}" for s in stale] + ["",
                   "_Opened/updated by scripts/health.py; it closes itself when every rail is fresh._"])
            if existing:
                subprocess.run(["gh", "issue", "comment", str(existing["number"]),
                                "--repo", repo, "--body", body], check=True)
                print(f"alert updated on issue #{existing['number']}")
            else:
                subprocess.run(["gh", "issue", "create", "--repo", repo,
                                "--title", ALERT_TITLE, "--body", body], check=True)
                print("alert issue opened")
        elif existing:
            subprocess.run(["gh", "issue", "comment", str(existing["number"]), "--repo", repo,
                            "--body", f"All rails fresh again as of {generated}. Closing."], check=True)
            subprocess.run(["gh", "issue", "close", str(existing["number"]),
                            "--repo", repo], check=True)
            print(f"alert cleared; closed issue #{existing['number']}")
    except Exception as exc:  # a report must never fail the rail
        print(f"alert step skipped: {exc}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--alert", action="store_true",
                    help="open/update (or clear) the health issue from the stale list")
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
    unreadable = []
    blind = "_error" in runs
    if not blind:
        for name, every in EXPECTED.items():
            e = runs.get(name)
            if e and e.get("unreadable"):
                # A transient empty read is not a dead rail; flag it as a gap,
                # not a fault, so the alert does not cry wolf.
                unreadable.append(name)
                continue
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
        "unreadable": unreadable,
        "blind": blind,
    }

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1 if (stale or blind) else 0

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
            if e.get("unreadable"):
                lines.append(f"- {name}: run history unreadable this pass (transient; "
                             "not counted as stale)")
                continue
            a = age_min(e.get("last_success"))
            last = age_min(e["last"])
            lines.append(f"- {name}: last {e['last_status']} {last:.0f} min ago; "
                         f"last success {'never' if a is None else f'{a/60:.1f} h ago'}")
    lines.append("")
    if blind:
        lines.append("## rails UNKNOWN — could not read run history")
        lines.append("- this is a blind report, not a fresh one: the run history could not "
                     "be read, so no rail's freshness is known")
    elif stale:
        lines.append("## STALE")
        lines += [f"- {s}" for s in stale]
    elif unreadable:
        lines.append("## all rails fresh (some run history unreadable this pass)")
        lines += [f"- {n}: transient read gap, not stale" for n in unreadable]
    else:
        lines.append("## all rails fresh")

    text = "\n".join(lines) + "\n"
    print(text)
    if args.write:
        with open(os.path.join(ROOT, "docs", "HEALTH.md"), "w", encoding="utf-8") as fh:
            fh.write(text)
    if args.alert and not blind:
        # Never clear an alert on a blind read: "could not read" is not "all fresh",
        # and closing the issue here would silence a real alert during an outage.
        upsert_alert(stale, report["generated"])
    return 1 if (stale or blind) else 0


if __name__ == "__main__":
    sys.exit(main())
