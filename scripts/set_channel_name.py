#!/usr/bin/env python3
"""Change the channel name a Thai viewer sees -- the part the Data API allows.

`channels.update` refuses `snippet.title`, so the channel's primary title cannot
be renamed from here (that is a YouTube Studio action). It *does* accept
`localizations.th.title`, and for a channel whose audience is Thai that is the
name every viewer actually reads. So this is the API-side half of a rename: it
sets the Thai localized title/description (and the channel description), while
the primary title is left for Studio.

Measured 2026-11-07: the channel "เรื่องเล่าการ์ตูน" (cartoon) publishes warm
family-memory narration with no animation at all, and its reach is the weakest of
the three channels (4,136 views / 16.1 watch-hours / +8 subs over 28 days). The
mismatch is the diagnosis the advisor panel agreed on; see
docs/PANEL-2026-11-07-ch4-CONSENSUS.md.

    python3 scripts/set_channel_name.py --channel kongkeat-story --dry-run
    python3 scripts/set_channel_name.py --channel kongkeat-story --apply

channels.update replaces the whole part it is given, so this reads the current
resource first and writes it back with only the localization/description changed.
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

# slug -> (refresh-token env, localized name, channel description). The name is
# the promise the content can keep: family memory, warm, adult listener.
TARGET = {
    "kongkeat-story": (
        "YT_CH4_REFRESH_TOKEN",
        "เรื่องเล่าอบอุ่นใจ",
        "เรื่องเล่าความทรงจำครอบครัวไทย — พ่อ แม่ พี่ ยาย ตา — เล่าด้วยเสียงนุ่ม ๆ "
        "ฟังเพลินทั้งคืน เหมาะเปิดฟังตอนพักผ่อน ทำงานบ้าน หรือก่อนนอน"),
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


def run(slug: str, dry: bool) -> None:
    env, name, desc = TARGET[slug]
    tok = access_token(env)
    item = api(tok, "GET", f"{CH_URL}?part=snippet,brandingSettings,localizations&mine=true")["items"][0]
    cid = item["id"]
    cur = item.get("localizations", {}).get("th", {})
    print(f"== {slug} ({item['snippet']['title']})  id={cid}")
    print(f"   primary title (Studio only): {item['snippet']['title']}")
    print(f"   th title: {cur.get('title') or '(unset)'}  ->  {name}")
    print(f"   th desc : {(cur.get('description') or '(unset)')[:60]}...")
    if cur.get("title") == name:
        print("   already set -- skip")
        return
    if dry:
        print("   dry-run: not writing")
        return
    body = {"id": cid,
            "localizations": {"th": {"title": name, "description": desc}},
            "brandingSettings": {"channel": {"description": desc}}}
    res = api(tok, "PUT", f"{CH_URL}?part=localizations,brandingSettings", body)
    got = res.get("localizations", {}).get("th", {})
    print(f"   wrote th title -> {got.get('title')}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--channel", choices=sorted(TARGET), default="kongkeat-story")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    try:
        run(args.channel, dry=not args.apply)
    except urllib.error.HTTPError as exc:
        print(f"HTTP {exc.code}: {exc.read()[:300].decode('utf-8', 'replace')}")
        return 1
    if not args.apply:
        print("(dry run -- nothing was changed; add --apply)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
