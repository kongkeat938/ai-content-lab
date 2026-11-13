#!/usr/bin/env python3
"""Add the long-video link to Shorts that are missing it -- the funnel repair.

Measured 2026-11-04: the first 10 dharma Shorts shipped with no link to the
120-minute video, so the viewers they reached had no next step. `publish_shorts.py`
adds the link now, but the early clips were uploaded before it did. This repairs
the ones already live, idempotently and additively -- it never rewrites existing
text, only appends the one block, and skips a Short that already carries the link.

    python3 scripts/backfill_short_links.py --dry-run
    python3 scripts/backfill_short_links.py --apply

videos.update costs 50 quota units; the 10,000-unit day allows 200 updates and
this touches only Shorts whose description lacks the link.
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

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

LONG_URL = "https://youtu.be/F4qFHoVpEyI"
MARKER = "ฟังเวอร์ชันเต็ม"
BLOCK = f"\n\n{MARKER} 120 นาทีได้ที่นี่ → {LONG_URL}\n\n#ธรรมะก่อนนอน #นอนไม่หลับ #ปล่อยวาง"
TOKEN_ENV = "YT_CH2_REFRESH_TOKEN"
CHANNEL_ID = "UCM3QO5L_pmj34n1JVlbhh-w"


def access_token() -> str:
    data = urllib.parse.urlencode({
        "client_id": os.environ["YT_CLIENT_ID"],
        "client_secret": os.environ["YT_CLIENT_SECRET"],
        "refresh_token": os.environ[TOKEN_ENV],
        "grant_type": "refresh_token"}).encode()
    with urllib.request.urlopen("https://oauth2.googleapis.com/token", data=data, timeout=30) as fh:
        return json.load(fh)["access_token"]


def api(path: str, token: str, method: str = "GET", body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"https://www.googleapis.com/youtube/v3/{path}", data=data, method=method,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as fh:
        return json.load(fh)


def seconds(iso: str) -> int:
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso)
    h, mn, s = (int(x or 0) for x in m.groups())
    return h * 3600 + mn * 60 + s


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write the links (default: dry run)")
    ap.add_argument("--only", action="append",
                    help="video id to link (repeatable); default = every on-niche Short")
    args = ap.parse_args()

    token = access_token()
    up = api(f"channels?part=contentDetails&id={CHANNEL_ID}", token)["items"][0]
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

    todo = []
    for i in range(0, len(ids), 50):
        v = api("videos?part=snippet,contentDetails&id=" + ",".join(ids[i:i + 50]), token)
        for x in v["items"]:
            if seconds(x["contentDetails"]["duration"]) > 180:
                continue                      # long-form is the destination, not a Short
            sn = x["snippet"]
            desc = sn.get("description") or ""
            if LONG_URL in desc or MARKER in desc:
                continue                      # already funnels -- idempotent
            if args.only and x["id"] not in args.only:
                continue
            todo.append(x)

    print(f"dharma: {len(todo)} Short(s) missing the long-video link")
    for x in todo:
        print(f"  {x['id']}: {x['snippet']['title'][:55]}")
    if not args.apply:
        print("(dry run -- pass --apply to write)")
        return 0

    ok = failed = 0
    for x in todo:
        sn = x["snippet"]
        desc = sn.get("description") or ""
        body = {"id": x["id"], "snippet": {
            "title": sn["title"],
            "description": (desc + BLOCK)[:5000],
            "categoryId": sn.get("categoryId", "22"),
            "tags": sn.get("tags", []),
            "defaultLanguage": sn.get("defaultLanguage", "th"),
            "defaultAudioLanguage": sn.get("defaultAudioLanguage", "th"),
        }}
        try:
            api("videos?part=snippet", token, method="PUT", body=body)
            print(f"  {x['id']}: linked")
            ok += 1
        except urllib.error.HTTPError as exc:
            print(f"  {x['id']}: FAIL {exc.code} {exc.read().decode()[:120]}")
            failed += 1
    print(f"done: {ok} linked, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
