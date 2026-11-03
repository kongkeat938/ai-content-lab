#!/usr/bin/env python3
"""Give each channel the two things a viewer needs to go deeper.

The measurement on 2026-11-03 was blunt: every channel's Shorts earn views from
the feed, but the long-form videos earn almost none (72 views over 10 clips on
ch2, 15 over 6 on ch4), and no channel has a trailer or an organised home page.
A Short can carry a viewer to the channel, but once they are there nothing asks
them to stay: the home page is a raw grid and there is no welcome clip.

So this does the two structural fixes the Data API allows:

  * set `unsubscribedTrailer` -- the clip a non-subscriber sees first, which is
    the only chance to turn a feed visitor into a subscriber;
  * group the uploads into playlists -- so "press deeper and search the channel"
    is a shelf to browse, not a wall of unrelated clips.

    python3 scripts/channel_overhaul.py --dry-run
    python3 scripts/channel_overhaul.py --channel ch4
    python3 scripts/channel_overhaul.py --only trailer

`--dry-run` prints every call it would make and changes nothing.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

CHANNELS = {
    "ch1": {"token": "YT_CH1_REFRESH_TOKEN", "name": "ตาต้า GenX"},
    "ch2": {"token": "YT_CH2_REFRESH_TOKEN", "name": "Farmmer"},
    "ch4": {"token": "YT_CH4_REFRESH_TOKEN", "name": "เรื่องเล่าการ์ตูน"},
}

# How each channel should be shelved. A rule is either `by` (shorts/long, i.e.
# the clip's own length decides) or `match` (a case-insensitive regex over the
# title). `keep` playlists already exist under these titles and are only topped
# up, not recreated.
PLAN = {
    "ch1": {
        "playlists": [
            {"title": "ปรัชญาชีวิต — ข้อคิดสั้น", "match": r"ปรัชญา|ข้อคิด|แง่คิด|กำลังใจ|มุมมอง|ความสุข|ความสงบ|ชีวิต",
             "desc": "ข้อคิดและปรัชญาชีวิตสั้น ๆ ที่ทำให้วันธรรมดาเบาสบายขึ้น"},
            {"title": "1 นาทีภาษาอังกฤษ", "match": r"english|อังกฤษ|1minute|1 minute",
             "desc": "ภาษาอังกฤษวันละนิด ใช้ได้จริงในชีวิตประจำวัน"},
            {"title": "เรื่องสั้น หนังสั้น", "match": r"หนังสั้น|เรื่องสั้น|ประตูแห่งความเงียบ",
             "desc": "เรื่องสั้นที่จบในตอน สนุกและได้ข้อคิด"},
        ],
    },
    "ch2": {
        "playlists": [
            {"title": "ธรรมะก่อนนอน — Shorts", "by": "shorts", "keep": True,
             "desc": "คำสอนสั้น ๆ ก่อนนอน ฟังแล้วใจสงบ หลับสบาย"},
            {"title": "หลับลึกทั้งคืน — ฟังยาว", "by": "long",
             "desc": "ฟังต่อเนื่องก่อนนอน ให้ใจค่อย ๆ สงบลง"},
            {"title": "ธรรมะก่อนนอน — ตอน", "by": "long", "keep": True,
             "desc": "ธรรมะก่อนนอนฉบับเต็มตอน"},
        ],
    },
    "ch4": {
        "playlists": [
            {"title": "เรื่องเล่าการ์ตูน — Shorts", "by": "shorts", "keep": True,
             "desc": "เรื่องเล่าการ์ตูนสั้น ๆ ได้ข้อคิดทุกตอน"},
            {"title": "เรื่องเล่าการ์ตูน — ตอน", "by": "long", "keep": True,
             "desc": "เรื่องเล่าการ์ตูนฉบับเต็มตอน"},
        ],
    },
}


def token(var: str) -> str:
    data = urllib.parse.urlencode({
        "client_id": os.environ["YT_CLIENT_ID"], "client_secret": os.environ["YT_CLIENT_SECRET"],
        "refresh_token": os.environ[var], "grant_type": "refresh_token"}).encode()
    return json.load(urllib.request.urlopen("https://oauth2.googleapis.com/token", data=data, timeout=30))["access_token"]


def api(url: str, tok: str, method: str = "GET", body: dict | None = None, tries: int = 4) -> dict:
    req = urllib.request.Request(url, method=method,
                                 headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"},
                                 data=json.dumps(body).encode() if body else None)
    for attempt in range(tries):
        try:
            return json.load(urllib.request.urlopen(req, timeout=60))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode()[:300]
            # 409 SERVICE_UNAVAILABLE and 403 quota are transient bursts; back off.
            if exc.code in (409, 403, 500, 503) and attempt < tries - 1:
                time.sleep(3 * (attempt + 1))
                continue
            return {"error": exc.code, "detail": detail}
    return {"error": "exhausted"}


def secs(iso: str) -> int:
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    h, mn, s = (int(x or 0) for x in m.groups())
    return h * 3600 + mn * 60 + s


def uploads(tok: str, ch_id: str) -> list[dict]:
    """Every video on the channel: id, title, seconds, views."""
    ch = api(f"https://www.googleapis.com/youtube/v3/channels?part=contentDetails&mine=true", tok)["items"][0]
    pid = ch["contentDetails"]["relatedPlaylists"]["uploads"]
    ids, page = [], None
    while True:
        u = (f"https://www.googleapis.com/youtube/v3/playlistItems?part=contentDetails&playlistId={pid}"
             f"&maxResults=50" + (f"&pageToken={page}" if page else ""))
        r = api(u, tok)
        ids += [i["contentDetails"]["videoId"] for i in r["items"]]
        page = r.get("nextPageToken")
        if not page:
            break
    out = []
    for i in range(0, len(ids), 50):
        v = api("https://www.googleapis.com/youtube/v3/videos?part=statistics,snippet,contentDetails&id="
                + ",".join(ids[i:i + 50]), tok)
        for x in v["items"]:
            out.append({"id": x["id"], "title": x["snippet"]["title"], "secs": secs(x["contentDetails"]["duration"]),
                        "views": int(x["statistics"].get("viewCount", 0))})
    return out


def set_trailer(tok: str, ch_id: str, video_id: str, title: str, dry: bool) -> None:
    print(f"  trailer  -> {video_id}  \"{title}\"")
    if dry:
        return
    r = api("https://www.googleapis.com/youtube/v3/channels?part=brandingSettings", tok, "PUT",
            {"id": ch_id, "brandingSettings": {"channel": {"unsubscribedTrailer": video_id, "defaultTab": "featured"}}})
    print(f"           {'ok' if 'error' not in r else 'FAILED ' + str(r)}")


def existing_playlists(tok: str, ch_id: str) -> dict[str, str]:
    r = api(f"https://www.googleapis.com/youtube/v3/playlists?part=snippet&channelId={ch_id}&maxResults=50", tok)
    return {p["snippet"]["title"]: p["id"] for p in r.get("items", [])}


def playlist_items(tok: str, pl_id: str) -> set[str]:
    ids, page = set(), None
    while True:
        u = (f"https://www.googleapis.com/youtube/v3/playlistItems?part=contentDetails&playlistId={pl_id}"
             f"&maxResults=50" + (f"&pageToken={page}" if page else ""))
        r = api(u, tok)
        ids |= {i["contentDetails"]["videoId"] for i in r.get("items", [])}
        page = r.get("nextPageToken")
        if not page:
            break
    return ids


def organise(tok: str, ch_id: str, vids: list[dict], plan: list[dict], dry: bool) -> None:
    have = existing_playlists(tok, ch_id)
    for spec in plan:
        if spec.get("by") == "shorts":
            members = [v for v in vids if v["secs"] <= 60]
        elif spec.get("by") == "long":
            members = [v for v in vids if v["secs"] > 60]
        else:
            rx = re.compile(spec["match"], re.I)
            members = [v for v in vids if rx.search(v["title"])]
        pl_id = have.get(spec["title"])
        print(f"  playlist \"{spec['title']}\": {len(members)} video(s)"
              f"{' [exists]' if pl_id else ' [new]'}")
        if dry or not members:
            continue
        if not pl_id:
            r = api("https://www.googleapis.com/youtube/v3/playlists?part=snippet,status", tok, "POST",
                    {"snippet": {"title": spec["title"], "description": spec["desc"]},
                     "status": {"privacyStatus": "public"}})
            if "error" in r:
                print(f"           create FAILED {r}")
                continue
            pl_id = r["id"]
        already = playlist_items(tok, pl_id)
        for v in members:
            if v["id"] in already:
                continue
            r = api("https://www.googleapis.com/youtube/v3/playlistItems?part=snippet", tok, "POST",
                    {"snippet": {"playlistId": pl_id,
                                 "resourceId": {"kind": "youtube#video", "videoId": v["id"]}}})
            if "error" in r:
                print(f"           add {v['id']} FAILED {r}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", choices=list(CHANNELS), help="only this channel")
    ap.add_argument("--only", choices=["trailer", "playlists"], help="only this step")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    slugs = [args.channel] if args.channel else list(CHANNELS)
    for slug in slugs:
        spec = CHANNELS[slug]
        tok = token(spec["token"])
        ch = api("https://www.googleapis.com/youtube/v3/channels?part=snippet,statistics&mine=true", tok)["items"][0]
        vids = uploads(tok, ch["id"])
        shorts = [v for v in vids if v["secs"] <= 60]
        best = max(shorts, key=lambda v: v["views"]) if shorts else None
        print(f"\n=== {slug} {spec['name']} — {len(vids)} videos ({len(shorts)} Shorts) "
              f"subs={ch['statistics'].get('subscriberCount')} ===")
        if not args.only or args.only == "trailer":
            if best:
                set_trailer(tok, ch["id"], best["id"], f"{best['title'][:44]} ({best['views']}v)", args.dry_run)
            else:
                print("  trailer  -> no Short to use")
        if not args.only or args.only == "playlists":
            organise(tok, ch["id"], vids, PLAN[slug]["playlists"], args.dry_run)
    if args.dry_run:
        print("\n(dry run — nothing was changed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
