#!/usr/bin/env python3
"""Give every Short a door to the next thing.

Measured 2026-11-03: ch2 sent 9 of 14 Shorts to another video, but ch1 sent only
2 of 16 and ch4 only 3 of 11. Those two channels earn views from the Shorts feed
and then drop the viewer -- the best-liked clip on ch4 (1,079 views, 2.32% likes)
had no link at all. So the leak is not content, it is a missing next step.

This appends ONE block to a Short's description when it has no video link: the
playlist that matches the clip, plus the channel home. It is idempotent (a marker
skips clips already done), additive (existing text is never rewritten) and
dry-run by default.

    python3 scripts/short_doors.py                 # show what it would do
    python3 scripts/short_doors.py --apply
    python3 scripts/short_doors.py --channel ch4 --apply

Quota: videos.update costs 50 units, so the 10,000-unit day covers 200 clips and
this only touches clips that are actually missing a door.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

MARKER = "▶ ดูต่อในช่อง"

# Which channel, which token, which home page, and how a Short finds its shelf.
# `routes` are tried in order; the first title match wins.
CHANNELS = {
    "ch1": {
        "token": "YT_CH1_REFRESH_TOKEN", "channel_id": "UCI6EfsgM1HNjrYarvigxyrQ",
        "home": "https://www.youtube.com/@tatagenxgeny",
        "routes": [
            ("ปรัชญาชีวิต — ข้อคิดสั้น", r"ปรัชญา|ข้อคิด|แง่คิด|กำลังใจ|มุมมอง|ความสุข|ความสงบ|ชีวิต|ตัวเอง|ฝากชีวิต|เติบโต"),
            ("1 นาทีภาษาอังกฤษ", r"english|อังกฤษ|1minute|1 minute"),
            ("เรื่องสั้น หนังสั้น", r"หนังสั้น|เรื่องสั้น|ประตูแห่งความเงียบ|ย้อนกลับไป|ขนม|ของเล่น"),
            ("ปรัชญาชีวิต — ข้อคิดสั้น", r"."),
        ],
    },
    "ch2": {
        "token": "YT_CH2_REFRESH_TOKEN", "channel_id": "UCM3QO5L_pmj34n1JVlbhh-w",
        "home": "https://www.youtube.com/@farmmer-n9t",
        # Point the door at the LONG-FORM playlist, not the Shorts playlist: only
        # long-form watch time counts toward the 4,000-hour YPP threshold (measured
        # 2026-11-06 -- dharma had 9.0 countable long-form hours vs 12.6 Shorts hours
        # that do not count). The door exists to move reach into countable hours.
        "routes": [("หลับลึกทั้งคืน — ฟังยาว", r".")],
    },
    "ch4": {
        "token": "YT_CH4_REFRESH_TOKEN", "channel_id": "UC7gCIu4G_7QCEJ8hJ-34zoQ",
        "home": "https://www.youtube.com/channel/UC7gCIu4G_7QCEJ8hJ-34zoQ",
        "routes": [("เรื่องเล่าอบอุ่นใจ — Shorts", r".")],
    },
}


def yt_for(slug: str):
    import yt_auth
    from googleapiclient.discovery import build
    creds = yt_auth.load_credentials(expected_channel=CHANNELS[slug]["channel_id"])
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def secs(iso: str) -> int:
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    h, mn, s = (int(x or 0) for x in m.groups())
    return h * 3600 + mn * 60 + s


def uploads(yt) -> list[dict]:
    up = (yt.channels().list(part="contentDetails", mine=True).execute()
          ["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"])
    ids, token = [], None
    while True:
        r = yt.playlistItems().list(part="contentDetails", playlistId=up,
                                    maxResults=50, pageToken=token).execute()
        ids += [i["contentDetails"]["videoId"] for i in r.get("items", [])]
        token = r.get("nextPageToken")
        if not token:
            break
    out = []
    for i in range(0, len(ids), 50):
        out += yt.videos().list(part="snippet,contentDetails", id=",".join(ids[i:i + 50])).execute()["items"]
    return out


def playlists(yt) -> dict[str, str]:
    r = yt.playlists().list(part="snippet", mine=True, maxResults=50).execute()
    return {p["snippet"]["title"]: p["id"] for p in r.get("items", [])}


def route(title: str, routes: list[tuple[str, str]]) -> str | None:
    for name, rx in routes:
        if re.search(rx, title, re.I):
            return name
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", choices=list(CHANNELS))
    ap.add_argument("--apply", action="store_true", help="write the blocks (default: dry run)")
    args = ap.parse_args()

    slugs = [args.channel] if args.channel else list(CHANNELS)
    for slug in slugs:
        spec = CHANNELS[slug]
        yt = yt_for(slug)
        got = (yt.channels().list(part="id", mine=True).execute().get("items") or [{}])[0].get("id")
        if got != spec["channel_id"]:
            print(f"  !! {slug}: token answered as {got}; skipped")
            continue
        vids = uploads(yt)
        shorts = [v for v in vids if secs(v["contentDetails"]["duration"]) <= 60]
        pls = playlists(yt)
        # A Short already has a door if its description points anywhere inside the
        # channel -- the marker block, a youtu.be link, or a playlist link.
        def has_door(v):
            d = v["snippet"].get("description") or ""
            return MARKER in d or bool(re.search(r"youtu\.be/|watch\?v=|playlist\?list=", d))
        missing = [v for v in shorts if not has_door(v)]
        print(f"== {slug}: {len(shorts)} Shorts, {len(missing)} without a door")
        if not args.apply:
            for v in missing[:4]:
                shelf = route(v["snippet"]["title"], spec["routes"])
                print(f"     {v['id']} -> {shelf or '(no shelf)':28} {v['snippet']['title'][:40]}")
            if len(missing) > 4:
                print(f"     ... and {len(missing) - 4} more")
            continue
        from googleapiclient.errors import HttpError
        wrote = skipped = failed = 0
        for v in missing:
            sn = v["snippet"]
            desc = sn.get("description") or ""
            shelf = route(sn["title"], spec["routes"])
            pl_id = pls.get(shelf) if shelf else None
            lines = [f"\n\n{MARKER}"]
            if pl_id:
                lines.append(f"รวมเรื่องแนวนี้ไว้ให้แล้ว → https://www.youtube.com/playlist?list={pl_id}")
            lines.append(f"ทุกตอนอยู่ในช่องเดียว → {spec['home']}")
            block = "\n".join(lines)
            if len(desc) + len(block) > 4900:
                skipped += 1
                continue
            body = {"id": v["id"], "snippet": {
                "title": sn["title"], "description": desc + block,
                "categoryId": sn.get("categoryId", "27"), "tags": sn.get("tags", []),
                "defaultLanguage": sn.get("defaultLanguage", "th"),
                "defaultAudioLanguage": sn.get("defaultAudioLanguage", "th")}}
            try:
                yt.videos().update(part="snippet", body=body).execute()
                wrote += 1
            except HttpError as e:
                failed += 1
                print(f"       FAIL {v['id']}: {str(e)[:110]}")
                if "quota" in str(e).lower():
                    break
                time.sleep(1)
        print(f"     wrote {wrote}, skipped {skipped} (too long), failed {failed}")
    if not args.apply:
        print("\n(dry run — nothing was changed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
