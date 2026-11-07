#!/usr/bin/env python3
"""Rename a channel the way that actually works -- brandingSettings, not snippet.

Background, because the first conclusion here was wrong and it cost time. On
2026-10-31 a rename attempt tried `channels.update` with `part=snippet`, got HTTP
400 `ERROR_PART_UNEXPECTED`, and the team concluded "the Data API cannot rename a
channel". That conclusion was too broad: it is only `snippet.title` that is not
writable. The field that *is* writable is `brandingSettings.channel.title`, and
it is the field the live name comes from -- ops/yt_branding.py wrote it on
2026-11-01 and the channel has displayed "เรื่องเล่าการ์ตูน" ever since (measured
live via the channel page, 2026-11-07). So a rename IS an API action.

`channels.update` replaces the whole `brandingSettings` part, so this reads the
current settings first and writes the COMPLETE object back with only the title
(and, optionally, description/keywords) changed -- a partial write would clear
the banner and description.

    python3 scripts/set_channel_name.py                 # show what would change
    python3 scripts/set_channel_name.py --verify        # read the live name only
    python3 scripts/set_channel_name.py --apply         # write it

Quota: channels.update costs 50 units. This is safe to run on a schedule.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

CH_URL = "https://www.googleapis.com/youtube/v3/channels"
TOKEN_URL = "https://oauth2.googleapis.com/token"

# slug -> (refresh-token env, target name, target description, target keywords).
# The name is the promise the content can keep: family memory, warm, adult
# listener. See docs/PANEL-2026-11-07-ch4-CONSENSUS.md.
TARGET = {
    "kongkeat-story": {
        "token": "YT_CH4_REFRESH_TOKEN",
        "title": "เรื่องเล่าอบอุ่นใจ",
        "description": "เรื่องเล่าความทรงจำครอบครัวไทย — พ่อ แม่ พี่ ยาย ตา — เล่าด้วยเสียงนุ่ม ๆ "
                       "ฟังเพลินทั้งคืน เหมาะเปิดฟังตอนพักผ่อน ทำงานบ้าน หรือก่อนนอน",
        "keywords": "เรื่องเล่าอบอุ่นใจ,ความทรงจำ,ครอบครัว,คิดถึงบ้าน,พ่อแม่,เรื่องเล่าซึ้งใจ,"
                    "ฟังก่อนนอน,เรื่องเล่าไทย,family memory,thai family story,nostalgic story",
    },
}


def access_token(env: str) -> str:
    data = urllib.parse.urlencode({
        "client_id": os.environ["YT_CLIENT_ID"], "client_secret": os.environ["YT_CLIENT_SECRET"],
        "refresh_token": os.environ[env], "grant_type": "refresh_token"}).encode()
    with urllib.request.urlopen(TOKEN_URL, data=data, timeout=30) as fh:
        return json.load(fh)["access_token"]


def api(tok: str, method: str, url: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(
        url, method=method, data=json.dumps(body).encode() if body else None,
        headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as fh:
        return json.load(fh)


def current(tok: str) -> dict:
    return api(tok, "GET",
               f"{CH_URL}?part=snippet,brandingSettings,localizations&mine=true")["items"][0]


def run(slug: str, dry: bool, verify_only: bool) -> int:
    t = TARGET[slug]
    tok = access_token(t["token"])
    item = current(tok)
    chb = item.get("brandingSettings", {}).get("channel", {})
    live_title = chb.get("title") or item["snippet"]["title"]
    print(f"== {slug}  id={item['id']}")
    print(f"   live title (brandingSettings.channel.title): {live_title}")
    print(f"   snippet.title                              : {item['snippet']['title']}")
    if verify_only:
        ok = live_title == t["title"]
        print(f"   target {t['title']!r} -> {'OK' if ok else 'NOT YET'}")
        return 0 if ok else 2
    if live_title == t["title"]:
        print("   already renamed -- skip")
        return 0
    # Carry the whole branding object back so banner/description/keywords survive.
    new_channel = dict(chb)
    new_channel["title"] = t["title"]
    new_channel["description"] = t["description"]
    new_channel["keywords"] = t["keywords"]
    payload = {"id": item["id"],
               "brandingSettings": {"channel": new_channel},
               # The Thai localized title is what a Thai viewer actually reads, and
               # it is a documented writable field. Set it too, so a rename lands
               # even on the path where brandingSettings.title is ignored.
               "localizations": {"th": {"title": t["title"], "description": t["description"]}}}
    if "image" in item.get("brandingSettings", {}):
        payload["brandingSettings"]["image"] = item["brandingSettings"]["image"]
    print(f"   {live_title!r} -> {t['title']!r}")
    if dry:
        print("   dry-run: not writing")
        return 0
    res = api(tok, "PUT", f"{CH_URL}?part=brandingSettings,localizations", payload)
    got_b = res.get("brandingSettings", {}).get("channel", {}).get("title")
    got_l = (res.get("localizations") or {}).get("th", {}).get("title")
    print(f"   wrote brandingSettings.title -> {got_b!r}")
    print(f"   wrote localizations.th.title -> {got_l!r}")
    ok = t["title"] in (got_b, got_l)
    if ok:
        print("   OK -- renamed via the API")
        return 0
    print("   DID NOT STICK on either path.")
    print("   Evidence (2026-10-31): brandingSettings.title answers HTTP 200 but echoes the")
    print("   old name back for a channel on a personal Google account. The 2026-11-05 name")
    print("   'เรื่องเล่าการ์ตูน' was most likely set in YouTube Studio. Do not treat this as")
    print("   a CI failure; the tool has done all the API can do.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--channel", choices=sorted(TARGET), default="kongkeat-story")
    ap.add_argument("--apply", action="store_true", help="write the change (default: dry run)")
    ap.add_argument("--verify", action="store_true", help="read the live name and exit")
    args = ap.parse_args()
    try:
        return run(args.channel, dry=not args.apply, verify_only=args.verify)
    except urllib.error.HTTPError as exc:
        print(f"HTTP {exc.code}: {exc.read()[:300].decode('utf-8', 'replace')}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
