#!/usr/bin/env python3
"""Detect the rogue upload stream with NO YouTube Data API quota.

The Data API pool is spent most days long before UTC midnight (measured
2026-11-15: `restore_metadata` alone spent 9,750 of the 10,000 units), so the
quota-based guard (`audit_channels --hide-live-rogue`) is blind from roughly
13:00 UTC until the 08:00 UTC reset. In that window a rogue clip can sit public
for hours -- which is exactly when it hurts a channel that already carries a
community-guidelines warning.

A channel's public RSS feed needs no key, no OAuth and no quota, and it lists the
newest uploads with their ids and publish times. That is enough to see the rogue
stream the moment it appears. This rail reads the feed, compares each id against
the ids this repo has recorded, and exits non-zero when a fresh unrecorded upload
is found -- so CI can fail and a human/agent is told at once.

    python3 scripts/rogue_watch_rss.py            # scan, exit 1 on a live rogue
    python3 scripts/rogue_watch_rss.py --json     # machine-readable

It cannot pause a clip (that needs the quota'd API); its job is to *see* and to
*shout* when the pausing rail is blind. Pair the two.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from audit_channels import recorded_ids  # noqa: E402  (one source of truth)

FEED = "https://www.youtube.com/feeds/videos.xml?channel_id={cid}"
NS = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015"}
RECENT_DAYS = 3
UA = "ai-content-lab rogue-watch (+https://github.com/kongkeat938/ai-content-lab)"


def channels() -> list[dict]:
    d = json.load(open(os.path.join(ROOT, "channels.json"), encoding="utf-8"))
    rows = d.get("channels", d) if isinstance(d, dict) else d
    return [c for c in (rows if isinstance(rows, list) else rows.values())
            if c.get("channel_id") and c.get("slug") != "aeris-music"]


def fetch_feed(channel_id: str) -> str:
    req = urllib.request.Request(FEED.format(cid=channel_id), headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def feed_entries(xml: str) -> list[dict]:
    root = ET.fromstring(xml)
    out = []
    for e in root.findall("a:entry", NS):
        vid = e.findtext("yt:videoId", default="", namespaces=NS)
        title = e.findtext("a:title", default="", namespaces=NS)
        published = e.findtext("a:published", default="", namespaces=NS)
        out.append({"video_id": vid, "title": title, "published": published})
    return out


def find_rogue(entries: list[dict], recorded: set, recent_days: float = RECENT_DAYS,
               now: datetime | None = None) -> list[dict]:
    """Fresh feed entries whose id no manifest records -- the rogue signature.

    Pure (no network) so a test can prove it FAILS on a rogue id and stays quiet
    on a recorded one. The age split matters: an unrecorded id older than the
    window is the pre-manifest backlog, not the live stream, so it is left for
    the quota'd audit's "historical" path rather than reported here.
    """
    now = now or datetime.now(timezone.utc)
    out = []
    for e in entries:
        if not e.get("video_id") or e["video_id"] in recorded:
            continue
        try:
            t = datetime.fromisoformat(e["published"].replace("Z", "+00:00"))
        except (ValueError, KeyError):
            continue
        age = (now - t).total_seconds() / 86400
        if age <= recent_days:
            out.append({**e, "age_days": round(age, 2)})
    return out


def hidden_ids() -> set:
    """Ids the pausing rail already set to `private` (its ledger).

    The RSS feed does NOT drop a clip the instant it turns private -- measured
    2026-11-15: a clip hidden at 10:44 UTC was still the newest feed entry at
    10:50, the feed's own `updated` still reading 08:21. Without this the watcher
    would report an already-paused clip on every run (cry wolf) until the feed
    caught up. The ledger is the record of what is handled, so trust it.
    """
    try:
        d = json.load(open(os.path.join(ROOT, "content", "rogue_hidden.json"),
                           encoding="utf-8"))
        return {h["video_id"] for h in d.get("hidden", []) if h.get("video_id")}
    except (OSError, ValueError, KeyError, TypeError):
        return set()


def scan() -> list[dict]:
    handled = hidden_ids()
    rogue = []
    for c in channels():
        cid = c["channel_id"]
        try:
            entries = feed_entries(fetch_feed(cid))
        except Exception as exc:  # noqa: BLE001 -- a feed hiccup is not a rogue
            print(f"  {c['slug']}: feed unreachable ({exc})", file=sys.stderr)
            continue
        for r in find_rogue(entries, recorded_ids(cid) | handled):
            rogue.append({**r, "channel": c["slug"], "channel_id": cid})
    return rogue


def alert(rogue: list[dict]) -> None:
    """Say on the alert issue that the stream was SEEN, even when it can't be paused.

    The pausing step needs quota; this one does not. So when quota is spent the
    issue still gets a fresh, dated line naming the live clips -- the channel is
    never silently exposed. Mirrors `audit_channels._comment_hidden`; the audit
    owns opening/closing the issue, this only appends.
    """
    repo = os.environ.get("GITHUB_REPOSITORY", "kongkeat938/ai-content-lab")
    title = "Channel audit: a live upload stream outside the rails"
    try:
        listed = subprocess.run(
            ["gh", "issue", "list", "--repo", repo, "--state", "open",
             "--search", title, "--json", "number,title"],
            capture_output=True, text=True, check=True)
        existing = next((i for i in json.loads(listed.stdout or "[]")
                         if i["title"] == title), None)
        if not existing:
            return
        body = "\n".join(
            [f"Seen without quota (RSS feed) at "
             f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC: "
             f"{len(rogue)} live rogue clip(s). The pausing rail is quota-blind "
             "until the 08:00 UTC reset; these will be set `private` at the first "
             "quota-backed run.", ""]
            + [f"- {r['channel']}: {r['video_id']} ({r['age_days']}d) -- {r['title'][:60]}"
               for r in rogue])
        subprocess.run(["gh", "issue", "comment", str(existing["number"]),
                        "--repo", repo, "--body", body], check=True)
        print(f"  commented the RSS sighting on issue #{existing['number']}")
    except Exception as exc:  # noqa: BLE001 -- alerting must never break the scan
        print(f"  alert step skipped: {exc}", file=sys.stderr)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="print the findings as JSON")
    ap.add_argument("--alert", action="store_true",
                    help="comment the sighting on the rogue alert issue")
    a = ap.parse_args()
    rogue = scan()
    if a.json:
        print(json.dumps(rogue, ensure_ascii=False, indent=2))
    elif rogue:
        for r in rogue:
            print(f"ROGUE {r['channel']} {r['video_id']} ({r['age_days']}d) "
                  f"{r['title'][:60]}")
    else:
        print("no live rogue upload on any channel feed")
    if rogue and a.alert:
        alert(rogue)
    return 1 if rogue else 0


if __name__ == "__main__":
    sys.exit(main())
