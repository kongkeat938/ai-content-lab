#!/usr/bin/env python3
"""Measure our own channels against the targets in COMPETITOR-STRATEGY.md §6.

Read-only. Prints median views of our latest uploads (the number that matters),
views-per-subscriber, and the target it is being judged against.

    python3 work/research/measure.py
"""
from __future__ import annotations

import json
import re
import statistics
import sys

sys.path.insert(0, "work/research")
from yt import get  # noqa: E402

# Targets from the strategy doc §6. week -> (min median views per long-form).
TARGETS = {1: 0, 2: 0, 4: 100, 8: 500, 12: 1000}
REFERENCE_VPS = 0.054  # hiphoplanla: 30,558 median / 562,000 subs


def iso_sec(s: str) -> int:
    m = re.match(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", s or "")
    if not m:
        return 0
    d, h, mi, se = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + se


def channel(slug: str) -> dict:
    ch = get(slug, "channels",
             {"part": "snippet,statistics,contentDetails", "mine": "true"})["items"][0]
    uploads = ch["contentDetails"]["relatedPlaylists"]["uploads"]
    ids, token = [], None
    while True:
        params = {"part": "contentDetails", "playlistId": uploads, "maxResults": 50}
        if token:
            params["pageToken"] = token
        r = get(slug, "playlistItems", params)
        ids += [x["contentDetails"]["videoId"] for x in r.get("items", [])]
        token = r.get("nextPageToken")
        if not token or len(ids) >= 50:
            break
    vids = []
    if ids:
        vd = get(slug, "videos",
                 {"part": "statistics,contentDetails,snippet", "id": ",".join(ids[:50])})
        for x in vd.get("items", []):
            st = x["statistics"]
            vids.append({"views": int(st.get("viewCount", 0)),
                         "sec": iso_sec(x["contentDetails"]["duration"]),
                         "title": x["snippet"]["title"]})
    return {"title": ch["snippet"]["title"], "subs": int(ch["statistics"]["subscriberCount"]),
            "views": int(ch["statistics"]["viewCount"]), "videos": vids}


def med(xs):
    return int(statistics.median(xs)) if xs else 0


def main() -> int:
    print("measuring our channels (latest uploads)…\n")
    for slug in ("ch1", "ch2", "ch4"):
        c = channel(slug)
        longs = [v for v in c["videos"] if v["sec"] >= 600]
        shorts = [v for v in c["videos"] if v["sec"] < 600]
        mv = med([v["views"] for v in longs])
        # views-per-subscriber is meaningless while subs is a handful: 1 sub and
        # 1 view is "100%". Only report it once there are enough subs to divide by.
        vps = (f"{mv / c['subs'] * 100:.1f}%" if c["subs"] >= 30
               else f"n/a ({c['subs']} subs)")
        best_short = max((v["views"] for v in shorts), default=0)
        print(f"{slug}  {c['title']}   [token's own channel]")
        print(f"   subs={c['subs']:,}  uploads={len(c['videos'])}  "
              f"total views={c['views']:,}")
        print(f"   long-form: n={len(longs):>2}  median views={mv:,}  "
              f"views/sub={vps}  (reference {REFERENCE_VPS*100:.1f}%)")
        print(f"   shorts:    n={len(shorts):>2}  best={best_short:,}")
        for wk in sorted(TARGETS):
            if TARGETS[wk]:
                verdict = "on track" if mv >= TARGETS[wk] else "below"
                print(f"      week {wk:>2} target {TARGETS[wk]:>6,} median  -> {verdict}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
