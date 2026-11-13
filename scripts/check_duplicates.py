#!/usr/bin/env python3
"""Report videos that are already on a channel more than once.

A duplicate is a video whose title exactly matches another on the same channel.
That is the signal that caught the real one: night_120 went live twice on
2026-11-03 because two publish runs raced on a stale checkout and the loser's
push was rejected, so the manifest never learned the second id.

Two same-length Shorts are *not* flagged -- the generator makes many clips of a
similar duration, and a duration match alone is not evidence. Only a repeated
title is, because publish_batch.py sets the title verbatim from the manifest.

    python3 scripts/check_duplicates.py            # all channels
    python3 scripts/check_duplicates.py --slug dharma

Read-only. Needs YT_CLIENT_ID, YT_CLIENT_SECRET and each YT_*_REFRESH_TOKEN.
Exit code is 1 when a duplicate is found, so a workflow can gate on it.
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
from collections import defaultdict

CHANNELS = {
    "genx": ("YT_CH1_REFRESH_TOKEN", "UCI6EfsgM1HNjrYarvigxyrQ"),
    "dharma": ("YT_CH2_REFRESH_TOKEN", "UCM3QO5L_pmj34n1JVlbhh-w"),
    "kongkeat": ("YT_CH4_REFRESH_TOKEN", "UC7gCIu4G_7QCEJ8hJ-34zoQ"),
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


def scan(slug: str) -> list[dict]:
    env, cid = CHANNELS[slug]
    token = access_token(env)
    up = api(f"channels?part=contentDetails&id={cid}", token)["items"][0]
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
            break
    rows = []
    for i in range(0, len(ids), 50):
        v = api("videos?part=snippet,contentDetails,status&id=" + ",".join(ids[i:i + 50]), token)
        for x in v["items"]:
            rows.append({"id": x["id"], "title": x["snippet"]["title"],
                         "dur": seconds(x["contentDetails"]["duration"]),
                         "pub": x["snippet"]["publishedAt"],
                         "priv": x["status"]["privacyStatus"]})
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", choices=list(CHANNELS), help="one channel (default: all)")
    args = ap.parse_args()

    slugs = [args.slug] if args.slug else list(CHANNELS)
    found = 0
    for slug in slugs:
        rows = scan(slug)
        by_title = defaultdict(list)
        for r in rows:
            by_title[r["title"]].append(r)
        dups = {t: rs for t, rs in by_title.items() if len(rs) > 1}
        print(f"\n===== {slug}: {len(rows)} videos, {len(dups)} duplicated title(s) =====")
        for title, rs in sorted(dups.items()):
            found += 1
            # Keep the public copy; an unlisted/private twin is the redundant one.
            rs = sorted(rs, key=lambda r: (r["priv"] != "public", r["pub"]))
            print(f"\n  DUPLICATE: {title}")
            for i, r in enumerate(rs):
                tag = "KEEP" if i == 0 else "redundant"
                print(f"    [{tag:9s}] {r['pub'][:16]}  {r['dur']:5d}s  {r['priv']:8s}  {r['id']}")
    print(f"\n{found} duplicate group(s) total")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
