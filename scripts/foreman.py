#!/usr/bin/env python3
"""The foreman: one job that drives every rail, so the channel runs without a person.

The old note here claimed GitHub's scheduler never fires for this repo. Measured
2026-11-07, that is wrong: `event=schedule` has 42 runs and the latest is the same
morning, all green. The real gap was that the foreman itself had no schedule, so the
driver was idle between pushes. It now carries a `*/30` cron and still runs on push.

It looks at what is due and dispatches the workflow that does it. It decides nothing
about content; the rails own their own ledgers and their own double-post guards.

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
sys.path.insert(0, HERE)

import publish_shorts as ps  # noqa: E402 -- read the rail's own cap ledger
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


def utc_hour() -> int:
    return now().hour


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

    # 1b. ch4 realign (rename + playlists + description scrub): the API quota
    #     resets 08:00 UTC, so a tick before that only defers. Every step is
    #     idempotent, so retrying is cheap when the work is already done.
    #
    #     The guard used to be 20 h, which was a bug: a pre-reset tick that
    #     deferred still exits 0, so it counted as a success and blocked the next
    #     real attempt for 20 h -- the rename waited a full day for nothing.
    #     A 5 h window lets the post-reset tick actually try, and a no-op tick
    #     afterwards costs a few seconds.
    if ids.get("ch4-realign") and utc_hour() >= 8:
        n_age = last_success_min("ch4-realign", ids)
        if n_age is None or n_age > 5 * 60:
            plan.append(("ch4-realign", {}))

    # 1c. Account watch: K's ask (2026-11-03) -- a mail nobody reads can quietly
    #     hurt the business (a copyright claim, a payment problem). It was
    #     manual-only and the foreman never dispatched it, so in practice it
    #     never ran. Daily, after the 08:00 UTC Data API reset so layer 1 (channel
    #     health) can actually read the channels.
    if ids.get("account-watch") and utc_hour() >= 8:
        a_age = last_success_min("account-watch", ids)
        if a_age is None or a_age > 20 * 60:
            plan.append(("account-watch", {}))

    # 2. Long videos: due whenever an entry has no id and its hold has passed.
    pub = load("content/ch2_publish.json", {"videos": []})
    due_long = [v for v in pub["videos"] if not v.get("video_id")
                and (not v.get("not_before") or parse(v["not_before"]) <= now())]
    if due_long:
        plan.append(("publish-batch", {}))

    # 2b. The same for ch4's long-form, whose own manifest drives publish-ch4.
    #     Its cap clears at 08:00 UTC, so the rail is due as soon as the pod's
    #     limit note has passed; a still-capped tick just re-records and defers.
    pub4 = load("content/ch4_publish.json", {"videos": []})
    due4 = [v for v in pub4["videos"] if not v.get("video_id")
            and (not v.get("not_before") or parse(v["not_before"]) <= now())]
    lim4 = load("content/upload_limit.json", {}).get("channels", {}).get(pub4.get("channel_id"), {})
    capped4 = bool(lim4.get("reset_at")) and parse(lim4["reset_at"]) > now()
    if due4 and not capped4:
        plan.append(("publish-ch4", {}))
    elif due4:
        print(f"  ch4: long-form due but upload-capped until {lim4['reset_at']}")

    # 2c. genx long-form: due when an entry has no id, or is live but still
    #     missing its playlist insert (the repair pass). publish-ch1 is
    #     idempotent -- a video_id is never re-uploaded and a set playlist_added
    #     is never re-added -- so a tick with nothing to do is cheap.
    pub1 = load("content/ch1_publish.json", {"videos": []})
    due1 = [v for v in pub1["videos"]
            if (not v.get("video_id")
                and (not v.get("not_before") or parse(v["not_before"]) <= now()))
            or (v.get("video_id") and v.get("playlist") and not v.get("playlist_added"))]
    lim1 = load("content/upload_limit.json", {}).get("channels", {}).get(pub1.get("channel_id"), {})
    capped1 = bool(lim1.get("reset_at")) and parse(lim1["reset_at"]) > now()
    if due1 and not capped1:
        plan.append(("publish-ch1", {}))
    elif due1:
        print(f"  genx: long-form due but upload-capped until {lim1['reset_at']}")

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

    # 5. Keep the long rail fed: a weekly build if the newest one is over 6 days
    #    old. generate=true so the scheduled path mints a fresh content set --
    #    without it the dispatch rebuilds an existing set and the fingerprint
    #    guard turns the whole run into a no-op. night-compilation fingerprints
    #    its own content, so a repeat on unchanged material is a cheap skip.
    n_age = last_success_min("night-compilation", ids)
    if n_age is None or n_age > 6 * 24 * 60:
        plan.append(("night-compilation", {"generate": "true"}))

    # 5b. Keep the ch4 family rail fed too: a weekly build if the newest is over
    #     6 days old. generate=true so the scheduled path mints a fresh set.
    c4_age = last_success_min("ch4-longform", ids)
    if c4_age is None or c4_age > 6 * 24 * 60:
        plan.append(("ch4-longform", {"generate": "true"}))

    # 5b-ii. Keep the genx rail fed: genx had the most Shorts and no long-form at
    #        all (measured 2026-11-07), so its funnel pointed at an empty playlist.
    #        A weekly build if the newest is over 6 days old.
    gx_age = last_success_min("genx-longform", ids)
    if gx_age is None or gx_age > 6 * 24 * 60:
        plan.append(("genx-longform", {"generate": "true"}))

    # 5c. Titles and thumbnails: the pass that changes every title and every ugly
    #     thumbnail. It spends the shared Data API quota, so it is due once a day
    #     in the window right after the 08:00 UTC reset, before the day's uploads
    #     need the budget. A pass that stops on quota simply resumes the next day;
    #     the ledgers make it incremental.
    p_age = last_success_min("polish-all", ids)
    if 8 <= now().hour < 12 and (p_age is None or p_age > 12 * 60):
        plan.append(("polish-all", {}))

    # 5d. Watch-hours: the weekly measurement of the one number the business runs
    #     on. Reads the Analytics API, which has its own quota.
    wh_age = last_success_min("watch-hours", ids)
    if wh_age is None or wh_age > 6 * 24 * 60:
        plan.append(("watch-hours", {}))

    # 5d-ii. The learning brain. studio-ai reads each channel's real Analytics and
    #       asks the panel what to make next; grow-shorts-pool then builds scripts
    #       from those subjects, so without this tick the pool follows a fixed list
    #       instead of what actually worked. It had only a schedule, and GitHub's
    #       cron is unreliable here, so drive it from the chain. Daily.
    sa_age = last_success_min("studio-ai", ids)
    if sa_age is None or sa_age > 20 * 60:
        plan.append(("studio-ai", {}))

    # 5d-iii. Top up the Shorts music bed. It had only a weekly schedule, so on a
    #        quiet cron week the pool of real instrumentals could run dry and new
    #        Shorts would fall back to silence. Cheap and idempotent -- an existing
    #        pack is kept. Weekly.
    fm_age = last_success_min("fetch music", ids)
    if fm_age is None or fm_age > 6 * 24 * 60:
        plan.append(("fetch music", {}))

    # 5d-iv. Run the guard tests. Each rail runs its own test inline, but five
    #        guards (channel identity, chapter renderer, music beds, remake, Short
    #        art/music) had no CI caller, so a regression there would go unnoticed.
    #        The whole suite is a few seconds. Daily.
    st_age = last_success_min("selftest", ids)
    if st_age is None or st_age > 20 * 60:
        plan.append(("selftest", {}))

    # 5e. The three rails that were only reachable through GitHub's cron. That cron
    #     is unreliable here (measured 2026-11-07: the */30 foreman cron fired once
    #     in 30 runs), so a rail that only has a `schedule` can be missed for days.
    #     Driving them from the chain -- which runs reliably -- is what makes them
    #     actually happen. Each keeps its own cadence and is idempotent.
    d_age = last_success_min("check-duplicates", ids)
    if d_age is None or d_age > 6 * 24 * 60:
        plan.append(("check-duplicates", {}))
    pr_age = last_success_min("progress", ids)
    if pr_age is None or pr_age > 20 * 60:
        plan.append(("progress", {}))
    sd_age = last_success_min("short doors", ids)
    if sd_age is None or sd_age > 6 * 24 * 60:
        plan.append(("short doors", {}))

    # 5f. Remake the live Shorts in the current format. The owner asked for this on
    #     2026-11-07 and the remake rail carries only a schedule, which GitHub's
    #     cron fires unreliably here (measured 2026-11-07: 2 schedule runs against
    #     155 dispatches). Drive it from the chain instead. A channel is due when it
    #     still has a live Short with no remake AND the rail's own cap has a free
    #     slot AND the 2-hour spacing has passed -- the same numbers the rail checks,
    #     so a tick with no room dispatches nothing and no separate age gate is
    #     needed (an age gate here would throttle the whole batch to one remake a
    #     day, which is the slow drip the cap already prevents). One channel per
    #     tick; the next tick takes the next one.
    if ids.get("remake shorts"):
        for slug, man_rel, pool_rel, cid in channels:
            man = load(man_rel, {"shorts": {}})
            rem = load(man_rel.replace("_shorts.json", "_shorts_remakes.json"), {"shorts": {}})
            left = [s["id"] for s in load(pool_rel, [])
                    if man["shorts"].get(s["id"], {}).get("video_id")
                    and not rem["shorts"].get(s["id"], {}).get("video_id")]
            if not left:
                continue
            man_path = os.path.join(ROOT, man_rel)
            if ps.uploads_in_last_24h(cid, man_path) >= ps.DAILY_CAP:
                print(f"  {slug}: {len(left)} remake(s) queued but the daily cap is full")
                continue
            since = ps.hours_since_last_upload(cid, man_path)
            if since is not None and since < ps.MIN_GAP_HOURS:
                print(f"  {slug}: {len(left)} remake(s) queued but last upload {since:.1f}h ago")
                continue
            plan.append(("remake shorts", {"channel": slug, "per_run": "1"}))
            break

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
