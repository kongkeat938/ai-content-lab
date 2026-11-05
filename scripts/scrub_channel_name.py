#!/usr/bin/env python3
"""Strip a channel's old personal name/handle from the descriptions of its live videos.

The channel title is เรื่องเล่าการ์ตูน, but every clip published before 2026-11-05
carried `@kongkeatpratumma` (a personal name) in its description tail. This
replaces that handle with the name-free channel URL, idempotently -- a video that
already reads the new URL is skipped. Only the description changes; title and
tags are untouched.

    python3 scripts/scrub_channel_name.py --channel ch4          # show changes
    python3 scripts/scrub_channel_name.py --channel ch4 --apply

videos.update costs 50 quota units, so the 10,000-unit day covers 200 clips and
this only touches clips that actually carry the old string.
"""
from __future__ import annotations

import argparse
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

OLD_HANDLE = "@kongkeatpratumma"
NEW_URL = "https://www.youtube.com/channel/UC7gCIu4G_7QCEJ8hJ-34zoQ"
OLD_NAME = "kongkeat pratumma"

CHANNELS = {
    "ch1": ("YT_CH1_REFRESH_TOKEN", "UCI6EfsgM1HNjrYarvigxyrQ"),
    "ch2": ("YT_CH2_REFRESH_TOKEN", "UCM3QO5L_pmj34n1JVlbhh-w"),
    "ch4": ("YT_CH4_REFRESH_TOKEN", "UC7gCIu4G_7QCEJ8hJ-34zoQ"),
}


def token(var: str) -> str:
    d = urllib.parse.urlencode({
        "client_id": os.environ["YT_CLIENT_ID"], "client_secret": os.environ["YT_CLIENT_SECRET"],
        "refresh_token": os.environ[var], "grant_type": "refresh_token"}).encode()
    return json_load("https://oauth2.googleapis.com/token", data=d)["access_token"]


def json_load(url: str, data=None, headers=None, method=None):
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    return json_load_raw(req)


def json_load_raw(req):
    import json
    with urllib.request.urlopen(req, timeout=60) as fh:
        return json.load(fh)


def uploads(head: dict) -> list:
    import json
    ch = json_load("https://www.googleapis.com/youtube/v3/channels?part=contentDetails&mine=true",
                   headers=head)["items"][0]
    up = ch["contentDetails"]["relatedPlaylists"]["uploads"]
    ids, tok = [], None
    while True:
        u = (f"https://www.googleapis.com/youtube/v3/playlistItems?part=contentDetails"
             f"&maxResults=50&playlistId={up}" + (f"&pageToken={tok}" if tok else ""))
        r = json_load(u, headers=head)
        ids += [x["contentDetails"]["videoId"] for x in r["items"]]
        tok = r.get("nextPageToken")
        if not tok:
            break
    return ids


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--channel", choices=sorted(CHANNELS), required=True)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    import json
    var, cid = CHANNELS[args.channel]
    head = {"Authorization": f"Bearer {token(var)}", "Content-Type": "application/json"}
    ids = uploads(head)
    changed = 0
    for vid in ids:
        r = json_load(f"https://www.googleapis.com/youtube/v3/videos?part=snippet&id={vid}",
                      headers=head)
        if not r.get("items"):
            continue   # deleted or private upload still listed in the playlist
        sn = r["items"][0]["snippet"]
        desc = sn.get("description", "")
        doubled = "https://www.youtube.com/" + NEW_URL
        if OLD_HANDLE not in desc and OLD_NAME not in desc and doubled not in desc:
            continue
        # Drop the whole old URL (not just the handle), then repair any doubling
        # a previous pass may have left behind.
        new = (desc.replace("https://www.youtube.com/" + OLD_HANDLE, NEW_URL)
                   .replace(OLD_HANDLE, NEW_URL)
                   .replace(OLD_NAME, "เรื่องเล่าการ์ตูน")
                   .replace("https://www.youtube.com/" + NEW_URL, NEW_URL))
        print(f"  {vid}: {sn['title'][:48]}")
        if args.apply:
            body = json.dumps({"id": vid, "snippet": {
                "title": sn["title"], "description": new,
                "categoryId": sn.get("categoryId", "22"),
                "tags": sn.get("tags", [])}}).encode()
            try:
                urllib.request.urlopen(urllib.request.Request(
                    "https://www.googleapis.com/youtube/v3/videos?part=snippet",
                    data=body, headers=head, method="PUT"), timeout=60)
                print("     -> updated")
            except urllib.error.HTTPError as exc:
                print(f"     -> FAILED {exc.code} {exc.read()[:120].decode(errors='replace')}")
        changed += 1
    verb = "updated" if args.apply else "would update"
    print(f"{args.channel}: {len(ids)} uploads, {verb} {changed}")
    if not args.apply:
        print("(dry run -- nothing was changed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
