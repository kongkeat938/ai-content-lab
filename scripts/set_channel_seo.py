#!/usr/bin/env python3
"""Set each channel's search keywords via the Data API -- no browser, no Studio.

Every channel had an empty `brandingSettings.channel.keywords`, which is free
discovery surface: the keywords feed YouTube search and the "channels like this"
rail. Studio's own editor is behind the phone-verification gate, but the API is
not, so this runs unattended like set_thumbnails.py.

    python3 scripts/set_channel_seo.py --dry-run
    python3 scripts/set_channel_seo.py

`channels.update` replaces the whole `brandingSettings` part, so the script reads
the current settings first and writes them back with only `channel.keywords`
changed -- a blind partial write would wipe the banner.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

TOKEN_URL = "https://oauth2.googleapis.com/token"
CH_URL = "https://www.googleapis.com/youtube/v3/channels"

# slug -> (refresh-token env var, Thai search keywords). Keep each under 500 chars.
CHANNELS = {
    "dharma": ("YT_CH2_REFRESH_TOKEN",
               "ธรรมะก่อนนอน ฟังธรรมะ นอนหลับสบาย ปล่อยวาง สมาธิ เรื่องเล่าธรรมะ หลับลึก "
               "dharma sleep meditation"),
    "genx": ("YT_CH1_REFRESH_TOKEN",
             "ปรัชญาชีวิต กำลังใจ คิดบวก เติมพลังใจ พัฒนาตัวเอง ข้อคิดชีวิต เติบโต "
             "self growth motivation thai"),
    "kongkeat-story": ("YT_CH4_REFRESH_TOKEN",
                       "เรื่องเล่า นิทาน การ์ตูน เรื่องสั้น ธรรมะสอนใจ นิทานก่อนนอน "
                       "thai story cartoon"),
}


def _client():
    cid = (os.environ.get("YT_CLIENT_ID") or "").strip()
    sec = (os.environ.get("YT_CLIENT_SECRET") or "").strip()
    if cid and sec:
        return cid, sec
    raw = (os.environ.get("CLIENT_SECRET") or "").strip()
    if raw:
        doc = json.loads(raw)
        for k in ("web", "installed"):
            s = doc.get(k)
            if isinstance(s, dict) and s.get("client_id"):
                return s["client_id"], s["client_secret"]
    sys.exit("Need YT_CLIENT_ID + YT_CLIENT_SECRET, or CLIENT_SECRET.")


def access_token(env: str) -> str:
    cid, sec = _client()
    data = urllib.parse.urlencode({
        "client_id": cid, "client_secret": sec,
        "refresh_token": os.environ[env], "grant_type": "refresh_token"}).encode()
    with urllib.request.urlopen(TOKEN_URL, data=data, timeout=30) as fh:
        return json.load(fh)["access_token"]


def api(token: str, method: str, url: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(
        url, method=method,
        data=json.dumps(body).encode() if body else None,
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as fh:
        return json.load(fh)


def run(slug: str, env: str, keywords: str, dry: bool) -> None:
    token = access_token(env)
    cur = api(token, "GET", f"{CH_URL}?part=snippet,brandingSettings&mine=true")
    item = cur["items"][0]
    cid = item["id"]
    have = (item.get("brandingSettings", {}).get("channel", {}).get("keywords") or "")
    print(f"== {slug} ({item['snippet']['title']})  id={cid}")
    print(f"   current keywords: {have or '(empty)'}")
    print(f"   new keywords:     {keywords}")
    if have == keywords:
        print("   already set -- skip")
        return
    if dry:
        print("   dry-run: not writing")
        return
    branding = item.get("brandingSettings", {})
    branding.setdefault("channel", {})
    branding["channel"]["keywords"] = keywords
    res = api(token, "PUT", f"{CH_URL}?part=brandingSettings",
              {"id": cid, "brandingSettings": branding})
    got = res["brandingSettings"]["channel"].get("keywords", "")
    print(f"   wrote -> {got[:60]}{'...' if len(got) > 60 else ''}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only", choices=sorted(CHANNELS))
    a = ap.parse_args()
    for slug, (env, kw) in CHANNELS.items():
        if a.only and slug != a.only:
            continue
        try:
            run(slug, env, kw, a.dry_run)
        except urllib.error.HTTPError as e:
            print(f"   HTTP {e.code}: {e.read()[:200].decode('utf-8', 'replace')}")
        except Exception as e:  # noqa: BLE001
            print(f"   {type(e).__name__}: {e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
