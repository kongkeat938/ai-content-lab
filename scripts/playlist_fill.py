#!/usr/bin/env python3
"""Put every long-form of a channel into the playlist the Shorts link points at.

Measured 2026-11-26 on dharma: the playlist *is* the best-retaining surface
(PLAYLIST traffic: 7 views / 68 min = 9.7 min per view; 3 views / 127 min on
another video), far better than SUBSCRIBER traffic (272 views / 302 min = 1.1
min per view). But the playlist every Short links to (`PLBpZCGnd7Q5Y`) was
missing 5 of the channel's 18 long-forms, so a viewer who followed the funnel
ran out of content and stopped.

    python3 scripts/playlist_fill.py --channel dharma --playlist PLBpZCGnd7Q5Y
    python3 scripts/playlist_fill.py --channel dharma --playlist PLBpZCGnd7Q5Y --apply

Without `--apply` it only reports. Idempotent: a video already in the playlist
is skipped, so a re-run costs one list call. It refuses a playlist that does not
belong to the channel before writing anything.

videos: insert into a playlist costs 50 quota units per video.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import yt_auth  # noqa: E402


def manifest_ids(path: str) -> list[str]:
    data = json.load(open(path, encoding="utf-8"))
    return [v["video_id"] for v in data.get("videos", []) if v.get("video_id")]


def manifest_for(channel: str) -> str | None:
    """The publish manifest whose channel_slug is this channel.

    The files are named ch1/ch2/ch4, so the slug cannot be guessed from them --
    the manifest itself carries `channel_slug`.
    """
    for name in sorted(os.listdir(os.path.join(ROOT, "content"))):
        if not name.endswith("_publish.json"):
            continue
        path = os.path.join(ROOT, "content", name)
        try:
            slug = json.load(open(path, encoding="utf-8")).get("channel_slug")
        except (json.JSONDecodeError, OSError):
            continue
        if slug == channel:
            return path
    return None


def channel_id_of(slug: str) -> str | None:
    data = json.load(open(os.path.join(ROOT, "channels.json"), encoding="utf-8"))
    for ch in data.get("channels", []):
        if ch.get("slug") == slug:
            return ch.get("channel_id")
    return None


def playlist_ids(yt, playlist_id: str) -> list[str]:
    ids: list[str] = []
    token = None
    while True:
        req = yt.playlistItems().list(part="contentDetails", playlistId=playlist_id,
                                      maxResults=50, pageToken=token)
        res = req.execute()
        ids += [i["contentDetails"]["videoId"] for i in res.get("items", [])]
        token = res.get("nextPageToken")
        if not token:
            return ids


def missing(owned: list[str], playlist: str, present: list[str]) -> list[str]:
    """Long-forms of the channel that the playlist still lacks, oldest first."""
    seen = set(present)
    return [v for v in owned if v not in seen]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", required=True)
    ap.add_argument("--playlist", required=True)
    ap.add_argument("--manifest", help="default: content/<ch>_publish.json")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    manifest = a.manifest or manifest_for(a.channel)
    if not manifest:
        print(f"no publish manifest for {a.channel}", file=sys.stderr)
        return 2
    owned = manifest_ids(manifest)
    cid = channel_id_of(a.channel)
    if not cid:
        print(f"channel {a.channel} is not in channels.json", file=sys.stderr)
        return 2
    creds = yt_auth.load_credentials(cid)
    from googleapiclient.discovery import build
    yt = build("youtube", "v3", credentials=creds)

    pl = yt.playlists().list(part="snippet", id=a.playlist).execute()
    items = pl.get("items", [])
    if not items:
        print(f"no playlist {a.playlist} visible to this channel", file=sys.stderr)
        return 2
    channel = yt.channels().list(part="id", mine=True).execute()["items"][0]["id"]
    owner = yt.videos().list(part="snippet", id=owned[0]).execute()["items"][0]["snippet"]["channelId"]
    if owner != channel or channel != cid:
        print(f"manifest {manifest} is not this channel's (owner {owner})", file=sys.stderr)
        return 2

    present = playlist_ids(yt, a.playlist)
    add = missing(owned, a.playlist, present)
    print(f"{items[0]['snippet']['title']}: {len(present)} items, {len(owned)} long-forms,"
          f" {len(add)} missing")
    for vid in add:
        if not a.apply:
            print(f"  would add {vid}")
            continue
        yt.playlistItems().insert(part="snippet", body={"snippet": {
            "playlistId": a.playlist,
            "resourceId": {"kind": "youtube#video", "videoId": vid}}}).execute()
        print(f"  added {vid}")
    if not a.apply:
        print("(dry run -- pass --apply to write)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
