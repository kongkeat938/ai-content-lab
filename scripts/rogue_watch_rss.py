#!/usr/bin/env python3
"""Detect the rogue upload stream with NO YouTube Data API quota.

The Data API pool is spent most days long before UTC midnight (measured
2026-11-15: `restore_metadata` alone spent 9,750 of the 10,000 units), so the
quota-based guard (`audit_channels --hide-live-rogue`) is blind from roughly
13:00 UTC until the 08:00 UTC reset. In that window a rogue clip can sit public
for hours -- which is exactly when it hurts a channel that already carries a
community-guidelines warning.

Two public, key-less, quota-free sources list a channel's newest uploads with
their ids and publish times: the RSS feed (`/feeds/videos.xml`) and the uploads
playlist page (`/playlist?list=UU...`). This rail reads whichever answers,
compares each id against the ids this repo has recorded, and exits non-zero when
a fresh unrecorded upload is found -- so CI can fail and a human/agent is told at
once. It FAILS rather than reporting "clean" when a channel's source cannot be
read at all: a scan that measured nothing is blind, not clean.

    python3 scripts/rogue_watch_rss.py            # scan; 1=rogue, 2=blind, 0=clean
    python3 scripts/rogue_watch_rss.py --json     # machine-readable

It cannot pause a clip (that needs the quota'd API); its job is to *see* and to
*shout* when the pausing rail is blind. Pair the two.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from audit_channels import recorded_ids  # noqa: E402  (one source of truth)

FEED = "https://www.youtube.com/feeds/videos.xml?channel_id={cid}&hl=en"
NS = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015"}
RECENT_DAYS = 3
# Force English: the age labels ("2d ago") are localized by IP/locale, so without
# this a Thai-locale response would make every age unparseable -- and an unparseable
# age drops a fresh rogue silently.
UA = "ai-content-lab rogue-watch (+https://github.com/kongkeat938/ai-content-lab)"
HEADERS = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"}


def channels() -> list[dict]:
    d = json.load(open(os.path.join(ROOT, "channels.json"), encoding="utf-8"))
    rows = d.get("channels", d) if isinstance(d, dict) else d
    return [c for c in (rows if isinstance(rows, list) else rows.values())
            if c.get("channel_id") and c.get("slug") != "aeris-music"]


def fetch_feed(channel_id: str) -> str:
    req = urllib.request.Request(FEED.format(cid=channel_id), headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def fetch_uploads_page(channel_id: str) -> str:
    """The uploads playlist page: a no-quota fallback when the RSS feed is down.

    Measured 2026-11-16: `/feeds/videos.xml` returned 404 for EVERY channel from
    the pod, from CI and from a residential IP -- the endpoint is dead, so the
    feed alone is no longer a source. The uploads playlist (`UU<id>`, i.e. `UC`
    with the second letter swapped) is still served and carries up to 100
    uploads with their ids, titles and ages in `ytInitialData`.
    """
    cid = "UU" + channel_id[2:]
    url = f"https://www.youtube.com/playlist?list={cid}&hl=en"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


_REL_AGE = re.compile(
    r"(\d+)\s*(minutes|minute|min|months|month|mo|hours|hour|hr|days|day|"
    r"weeks|week|years|year|h|d|w|m|y)\b", re.I)


def parse_relative_age_days(text: str) -> float | None:
    """Turn a YouTube age label ("2d ago", "16h ago", "1 week ago") into days.

    Returns None when nothing parses, so the caller can treat the entry as
    un-measurable rather than silently dropping it (a wrong age decides whether a
    clip is the LIVE rogue stream or the old pre-manifest backlog).
    """
    if not text:
        return None
    m = _REL_AGE.search(text)
    if not m:
        return None
    n = int(m.group(1))
    unit = m.group(2).lower()
    if unit.startswith("min") or unit == "m":
        return n / 1440
    if unit.startswith("h"):
        return n / 24
    if unit.startswith("d"):
        return float(n)
    if unit.startswith("w"):
        return n * 7
    if unit.startswith("mo"):
        return n * 30
    if unit.startswith("y"):
        return n * 365
    return None


def parse_uploads_page(html: str) -> list[dict]:
    """Entries from an uploads-playlist page's `ytInitialData` (pure, testable).

    Reads only the structured payload, so it does not depend on the page's
    volatile HTML markup.
    """
    m = re.search(r"ytInitialData\s*=\s*(\{.*?\});</script>", html, re.S)
    if not m:
        raise ValueError("ytInitialData not found on the uploads page")
    data = json.loads(m.group(1))
    now = datetime.now(timezone.utc)
    out: list[dict] = []

    def walk(o) -> None:
        if isinstance(o, dict):
            lv = o.get("lockupViewModel")
            if lv:
                vid = lv.get("contentId")
                md = lv.get("metadata", {}).get("lockupMetadataViewModel", {})
                title = (md.get("title") or {}).get("content", "")
                rows = (md.get("metadata", {})
                        .get("contentMetadataViewModel", {}).get("metadataRows", []))
                parts = [p.get("text", {}).get("content", "")
                         for r in rows for p in r.get("metadataParts", [])]
                rel = next((p for p in parts if p and "ago" in p.lower()), "")
                age = parse_relative_age_days(rel)
                published = (now - timedelta(days=age)).strftime("%Y-%m-%dT%H:%M:%SZ") \
                    if age is not None else ""
                out.append({"video_id": vid, "title": title, "published": published,
                            "age_days": age})
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(data)
    return out


def uploads_entries(channel_id: str) -> list[dict]:
    """Fetch + parse a channel's uploads playlist page."""
    return parse_uploads_page(fetch_uploads_page(channel_id))


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
        age = e.get("age_days")
        if age is None:
            try:
                t = datetime.fromisoformat(e["published"].replace("Z", "+00:00"))
            except (ValueError, KeyError, AttributeError):
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


def scan() -> tuple[list[dict], list[str]]:
    """Return (rogue clips, channels whose uploads could not be read at all).

    Each channel is read from the public RSS feed, falling back to the uploads
    playlist page. A channel neither source can answer for is BLIND -- reported
    as such, never as clean: "measured nothing" is the exact false pass this rail
    exists to prevent. A source that answers but yields ZERO entries is treated as
    blind too: a live channel with recent uploads cannot legitimately have none,
    so an empty read is a broken selector, not a clean bill of health.
    """
    handled = hidden_ids()
    rogue: list[dict] = []
    blind: list[str] = []
    for c in channels():
        cid = c["channel_id"]
        entries = None
        errors = []
        for source in (lambda: feed_entries(fetch_feed(cid)),
                       lambda: uploads_entries(cid)):
            try:
                got = source()
            except Exception as exc:  # noqa: BLE001 -- fall through to the next source
                errors.append(str(exc))
                continue
            if got:
                entries = got
                break
            errors.append("source returned no entries")
        if not entries:
            print(f"  {c['slug']}: BLIND, no source answered ({'; '.join(errors)})",
                  file=sys.stderr)
            blind.append(c["slug"])
            continue
        for r in find_rogue(entries, recorded_ids(cid) | handled):
            rogue.append({**r, "channel": c["slug"], "channel_id": cid})
    return rogue, blind


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
            [f"Seen without quota (RSS feed / uploads page) at "
             f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC: "
             f"{len(rogue)} live rogue clip(s). The pausing rail is quota-blind "
             "until the 08:00 UTC reset; these will be set `private` at the first "
             "quota-backed run.", ""]
            + [f"- {r['channel']}: {r['video_id']} ({r['age_days']}d) -- {r['title'][:60]}"
               for r in rogue])
        subprocess.run(["gh", "issue", "comment", str(existing["number"]),
                        "--repo", repo, "--body", body], check=True)
        print(f"  commented the sighting on issue #{existing['number']}")
    except Exception as exc:  # noqa: BLE001 -- alerting must never break the scan
        print(f"  alert step skipped: {exc}", file=sys.stderr)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="print the findings as JSON")
    ap.add_argument("--alert", action="store_true",
                    help="comment the sighting on the rogue alert issue")
    a = ap.parse_args()
    rogue, blind = scan()
    if a.json:
        print(json.dumps(rogue, ensure_ascii=False, indent=2))
    elif rogue:
        for r in rogue:
            print(f"ROGUE {r['channel']} {r['video_id']} ({r['age_days']}d) "
                  f"{r['title'][:60]}")
    elif blind:
        print(f"BLIND: no source answered for {len(blind)} channel(s) "
              f"({', '.join(blind)}) -- nothing measured, NOT a clean scan")
    else:
        print("no live rogue upload on any channel feed")
    if rogue and a.alert:
        alert(rogue)
    if rogue:
        return 1
    if blind:
        return 2   # measured nothing: distinct from clean, so CI can shout
    return 0


if __name__ == "__main__":
    sys.exit(main())
