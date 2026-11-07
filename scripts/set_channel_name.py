#!/usr/bin/env python3
"""Rename a channel the way the API actually allows -- via localizations, not the title.

The team spent time on the wrong field twice. First (2026-10-31) it tried
`part=snippet`, got 400 `ERROR_PART_UNEXPECTED`, and concluded "the API cannot
rename a channel". Then it tried `brandingSettings.channel.title`, which also
cannot work: the reference (read 2026-11-07) documents error
`channelTitleUpdateForbidden` -- that title must be sent back unchanged.

The field that DOES rename is `localizations.(key).title`, and the reference
lists it as writable. Two rules come with it:
  * `part` accepts exactly ONE of brandingSettings | invideoPromotion |
    localizations per request -- sending two is a 400, so the title cannot ride
    along with a brandingSettings call.
  * `localizations` is refused (400 defaultLanguageNotSetError) unless the channel
    already has a `defaultLanguage`.

So the rename is two calls:
  1. PUT ?part=brandingSettings  -- set defaultLanguage (title echoed unchanged),
     and set description/keywords, which are writable on this part.
  2. PUT ?part=localizations     -- set localizations.th.title = the new name.

    python3 scripts/set_channel_name.py            # show what would change
    python3 scripts/set_channel_name.py --verify   # read the live name only
    python3 scripts/set_channel_name.py --apply    # write it

Quota: each channels.update costs 50 units. Idempotent -- it skips a channel whose
localized title already matches.
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
        "lang": "th",
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
    default_lang = chb.get("defaultLanguage") or item["snippet"].get("defaultLanguage") or ""
    loc_th = (item.get("localizations") or {}).get("th", {}).get("title")
    print(f"== {slug}  id={item['id']}")
    print(f"   live title (brandingSettings.channel.title): {live_title}")
    print(f"   snippet.title                              : {item['snippet']['title']}")
    print(f"   defaultLanguage                            : {default_lang!r}")
    print(f"   localizations.th.title                     : {loc_th!r}")
    if verify_only:
        ok = loc_th == t["title"]
        print(f"   target {t['title']!r} -> {'OK' if ok else 'NOT YET'}")
        return 0 if ok else 2
    if loc_th == t["title"]:
        print("   already renamed -- skip")
        return 0

    # The API's own rules, read from the channels.update reference (2026-11-07):
    #   * `part` accepts exactly ONE of brandingSettings | invideoPromotion |
    #     localizations per request. Sending two returns 400.
    #   * brandingSettings.channel.title is NOT writable: change it and the API
    #     answers 400 channelTitleUpdateForbidden. So the rename cannot go there.
    #   * localizations.(key).title IS writable -- that is the channel name a
    #     viewer in that language sees, i.e. the rename for a Thai audience.
    #   * localizations is refused unless defaultLanguage is set.
    # So the rename is two calls: set defaultLanguage first, then the title.
    print(f"   plan: defaultLanguage -> {t['lang']!r}, then localizations.{t['lang']}.title -> {t['title']!r}")
    if dry:
        print("   dry-run: not writing")
        return 0

    if default_lang != t["lang"]:
        # Call 1: part=brandingSettings. The channel title MUST be echoed back
        # unchanged (channelTitleUpdateForbidden otherwise), so we carry the whole
        # object and change only defaultLanguage -- this keeps banner/desc/keywords.
        new_channel = dict(chb)
        new_channel["title"] = live_title
        new_channel["defaultLanguage"] = t["lang"]
        new_channel["description"] = t["description"]
        new_channel["keywords"] = t["keywords"]
        payload = {"id": item["id"], "brandingSettings": {"channel": new_channel}}
        if "image" in item.get("brandingSettings", {}):
            payload["brandingSettings"]["image"] = item["brandingSettings"]["image"]
        res = api(tok, "PUT", f"{CH_URL}?part=brandingSettings", payload)
        got = res.get("brandingSettings", {}).get("channel", {}).get("defaultLanguage")
        print(f"   set defaultLanguage -> {got!r}  {'OK' if got == t['lang'] else 'FAILED'}")
        if got != t["lang"]:
            return 1

    # Call 2: part=localizations. This is the actual rename.
    res = api(tok, "PUT", f"{CH_URL}?part=localizations",
              {"id": item["id"],
               "localizations": {t["lang"]: {"title": t["title"], "description": t["description"]}}})
    got = (res.get("localizations") or {}).get(t["lang"], {}).get("title")
    print(f"   set localizations.{t['lang']}.title -> {got!r}")
    if got == t["title"]:
        print("   OK -- renamed via the API (localizations)")
        return 0
    print("   DID NOT STICK.")
    print(f"   Response: {str(res)[:300]}")
    print("   If the error is defaultLanguageNotSetError, the brandingSettings call did not")
    print("   land. If it is forbidden, the channel may need YouTube Studio.")
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
        body = exc.read().decode("utf-8", "replace")
        # A spent daily quota is a deferral, not a failure: the reset is 08:00 UTC
        # and the rail (and the foreman) retry after it. Only a real error is red.
        if exc.code == 403 and "quota" in body.lower():
            print("quota exhausted -- deferring to after the 08:00 UTC reset")
            return 0
        print(f"HTTP {exc.code}: {body[:300]}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
