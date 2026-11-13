#!/usr/bin/env python3
"""Measure reach per video, so the next hook is chosen from evidence.

The channels are small, so the only honest signal is views against the time a
video has been up: a Short that pulled 900 views in two days and one that pulled
900 in two weeks are different results. This prints, per channel, every video
with its views, age, and views-per-day, newest Shorts first.

Retention *is* available. This docstring used to say the refresh tokens carry the
`youtube` scope only and the Analytics API refuses them -- that was wrong, and it
is the exact failure this project's "evidence, not claims" rule is about: a
committed note was treated as the answer. Re-measured 2026-11-08, all three tokens
answer `youtubeanalytics.googleapis.com/v2/reports` (views, estimatedMinutesWatched,
averageViewPercentage, and the `audienceWatchRatio` retention curve). Use
`scripts/verify_claims.py` to re-check, and `scripts/analytics.py` for the numbers.

What the API genuinely will not give: `impressions` and `clickThroughRate` are not
Analytics API metrics (HTTP 400 "Unknown identifier"), and revenue needs a scope
these tokens do not hold ("Insufficient permission"). Those two still need the
Studio UI. Views-per-day and the retention curve are what we can read here.

    python3 scripts/report_reach.py
    python3 scripts/report_reach.py --channel dharma --shorts-only
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yt_duration

import argparse
import json
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

CHANNELS = {
    "genx": ("YT_CH1_REFRESH_TOKEN", "UCI6EfsgM1HNjrYarvigxyrQ", "ตาต้า GenX"),
    "dharma": ("YT_CH2_REFRESH_TOKEN", "UCM3QO5L_pmj34n1JVlbhh-w", "Farmmer"),
    "kongkeat": ("YT_CH4_REFRESH_TOKEN", "UC7gCIu4G_7QCEJ8hJ-34zoQ", "เรื่องเล่าอบอุ่นใจ"),
}


def access_token(env: str) -> str:
    data = urllib.parse.urlencode({
        "client_id": os.environ["YT_CLIENT_ID"],
        "client_secret": os.environ["YT_CLIENT_SECRET"],
        "refresh_token": os.environ[env],
        "grant_type": "refresh_token"}).encode()
    with urllib.request.urlopen("https://oauth2.googleapis.com/token", data=data, timeout=30) as fh:
        return json.load(fh)["access_token"]


def api(path: str, token: str) -> dict:
    req = urllib.request.Request(f"https://www.googleapis.com/youtube/v3/{path}",
                                 headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=30) as fh:
        return json.load(fh)


def seconds(iso: str) -> int:
    return yt_duration.seconds(iso)


def uploads(channel_id: str, token: str) -> list[str]:
    up = api(f"channels?part=contentDetails&id={channel_id}", token)["items"][0]
    up = up["contentDetails"]["relatedPlaylists"]["uploads"]
    ids, page = [], None
    while True:
        q = f"playlistItems?part=contentDetails&playlistId={up}&maxResults=50"
        if page:
            q += f"&pageToken={page}"
        r = api(q, token)
        ids += [i["contentDetails"]["videoId"] for i in r["items"]]
        page = r.get("nextPageToken")
        if not page:
            return ids


def report(slug: str, shorts_only: bool) -> None:
    env, cid, label = CHANNELS[slug]
    try:
        token = access_token(env)
    except Exception as exc:                       # noqa: BLE001 -- report, do not crash the run
        print(f"{slug}: token failed ({exc})")
        return
    ids = uploads(cid, token)
    rows = []
    now = datetime.now(timezone.utc)
    for i in range(0, len(ids), 50):
        v = api("videos?part=statistics,contentDetails,snippet&id=" + ",".join(ids[i:i + 50]), token)
        for x in v["items"]:
            dur = seconds(x["contentDetails"]["duration"])
            if shorts_only and dur > 180:
                continue
            pub = datetime.fromisoformat(x["snippet"]["publishedAt"].replace("Z", "+00:00"))
            days = max((now - pub).total_seconds() / 86400, 0.01)
            views = int(x["statistics"].get("viewCount", 0))
            rows.append({"views": views, "days": days, "per_day": views / days,
                         "dur": dur, "id": x["id"], "title": x["snippet"]["title"][:52]})
    rows.sort(key=lambda r: r["per_day"], reverse=True)
    print(f"\n===== {slug} ({label}) — {len(rows)} videos, best views/day first =====")
    print(f"{'views':>6} {'days':>5} {'per_day':>8} {'dur':>5}  title")
    for r in rows[:15]:
        print(f"{r['views']:6} {r['days']:5.1f} {r['per_day']:8.1f} {r['dur']:5}s  {r['title']}  {r['id']}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", choices=list(CHANNELS))
    ap.add_argument("--shorts-only", action="store_true")
    args = ap.parse_args()
    for slug in ([args.channel] if args.channel else list(CHANNELS)):
        report(slug, args.shorts_only)
    return 0


if __name__ == "__main__":
    sys.exit(main())
