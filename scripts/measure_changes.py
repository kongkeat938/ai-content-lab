#!/usr/bin/env python3
"""Measure the long-form metadata changes honestly, against a real baseline.

The first naive read (a raw % on the ledger baseline) was wrong and was thrown
away: the ledger's "changed" set mixed Shorts (feed-driven, hundreds of views an
hour) with long-form, and the baseline was captured at posting time. A raw delta
therefore measured the Shorts feed, not the metadata.

The honest design, used here:
  * long-form only (duration > 180s) -- Shorts are excluded on purpose, their
    traffic is 93-97% the Shorts feed and a title cannot move it.
  * a fixed PRE window (analytics days before the change) vs a POST window
    (analytics days after), per video, summed per channel. Analytics lags about
    3 days, so the POST window only fills in as days pass -- that is why the
    result must be read at the 14-day mark, not now.

    python3 scripts/measure_changes.py --channel genx
    python3 scripts/measure_changes.py --channel genx --control
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analytics import CHANNELS, access_token  # noqa: E402
from channel_admin import _get  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHANGE_DAY = date(2026, 11, 6)  # the day titles + thumbnails + SEO were applied


def secs(iso: str) -> int:
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not m:
        return 0
    h, mi, s = (int(x) if x else 0 for x in m.groups())
    return h * 3600 + mi * 60 + s


def uploads(token: str) -> list[str]:
    it = _get("channels", {"part": "contentDetails", "mine": "true"}, token)["items"][0]
    up = it["contentDetails"]["relatedPlaylists"]["uploads"]
    ids, page = [], None
    while True:
        p = {"part": "contentDetails", "playlistId": up, "maxResults": "50"}
        if page:
            p["pageToken"] = page
        r = _get("playlistItems", p, token)
        ids += [x["contentDetails"]["videoId"] for x in r.get("items", [])]
        page = r.get("nextPageToken")
        if not page:
            break
    return ids


def longform(ids: list[str], token: str) -> dict[str, int]:
    out = {}
    for i in range(0, len(ids), 50):
        for v in _get("videos", {"part": "contentDetails",
                                 "id": ",".join(ids[i:i + 50])}, token).get("items", []):
            d = secs(v["contentDetails"]["duration"])
            if d > 180:
                out[v["id"]] = d
    return out


def views_window(token: str, start: date, end: date, ids: set[str]) -> dict[str, int]:
    """Views per video in [start, end] from the Analytics API (lags ~3 days)."""
    if end < start:
        return {}
    params = {"ids": "channel==MINE", "startDate": start.isoformat(),
              "endDate": end.isoformat(), "metrics": "views", "dimensions": "video",
              "sort": "-views", "maxResults": "200"}
    url = "https://youtubeanalytics.googleapis.com/v2/reports?" + urllib.parse.urlencode(params)
    try:
        rows = json.load(urllib.request.urlopen(
            urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"}),
            timeout=60)).get("rows", [])
    except urllib.error.HTTPError:
        return {}
    return {r[0]: r[1] for r in rows if r[0] in ids}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", default="genx", choices=list(CHANNELS))
    ap.add_argument("--pre-days", type=int, default=14)
    ap.add_argument("--control", action="store_true",
                    help="also report long-form videos NOT in the change ledger")
    args = ap.parse_args()

    token = access_token(CHANNELS[args.channel][0])
    with open(os.path.join(ROOT, "docs", "title_changes.json"), encoding="utf-8") as fh:
        changed = {c["id"] for c in json.load(fh)["changes"]}

    lf = longform(uploads(token), token)
    treat = {i for i in lf if i in changed}
    ctrl = {i for i in lf if i not in changed}

    pre_end = CHANGE_DAY - timedelta(days=1)
    pre_start = pre_end - timedelta(days=args.pre_days - 1)
    today = date.today()
    post_start = CHANGE_DAY
    post_end = today - timedelta(days=3)  # analytics lag

    print(f"=== {args.channel}: long-form {len(lf)} "
          f"(treated {len(treat)}, control {len(ctrl)})")
    print(f"PRE  {pre_start}..{pre_end}   POST {post_start}..{post_end}"
          f"{'  (POST not open yet -- read at +14d)' if post_end < post_start else ''}")

    pre = views_window(token, pre_start, pre_end, set(lf))
    for label, group in (("treated", treat), ("control", ctrl)):
        if not group or (label == "control" and not args.control):
            continue
        v = sum(pre.get(i, 0) for i in group)
        print(f"  {label:8s} n={len(group):2d}  PRE {v:5d} views ({v / args.pre_days:.1f}/day)")
    if post_end >= post_start:
        post_days = (post_end - post_start).days + 1
        post = views_window(token, post_start, post_end, set(lf))
        for label, group in (("treated", treat), ("control", ctrl)):
            if not group or (label == "control" and not args.control):
                continue
            v = sum(post.get(i, 0) for i in group)
            print(f"  {label:8s} n={len(group):2d}  POST {v:5d} views ({v / post_days:.1f}/day)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
