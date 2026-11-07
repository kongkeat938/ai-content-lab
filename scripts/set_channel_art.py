#!/usr/bin/env python3
"""Install a channel banner through the API, and report the avatar's real limit.

Measured 2026-11-07 on ch4:
  * `channelBanners.insert` (uploadType=media) works with the channel's own
    refresh token and returns a hosted URL.
  * `channels.update?part=brandingSettings` attaches it via
    `brandingSettings.image.bannerExternalUrl`. The whole `channel` object must be
    echoed back unchanged -- the API overrides every mutable property in the part,
    so a partial write would wipe the description and keywords.
  * There is NO API for the channel avatar (profile picture). It is not a writable
    field of `brandingSettings` and there is no upload method for it, so the avatar
    is a Studio step.

    python3 scripts/set_channel_art.py --channel ch4 --dry-run
    python3 scripts/set_channel_art.py --channel ch4            # upload + attach

Quota: channelBanners.insert is 50 units, channels.update is 50. A spent quota
returns 403 quotaExceeded, which is a deferral (reset 08:00 UTC), not a failure.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

CH = "https://www.googleapis.com/youtube/v3/channels"
UP = "https://www.googleapis.com/upload/youtube/v3/channelBanners/insert"
TOKEN_URL = "https://oauth2.googleapis.com/token"

CHANNELS = {
    "ch1": ("YT_CH1_REFRESH_TOKEN", "assets/branding/genx"),
    "ch2": ("YT_CH2_REFRESH_TOKEN", "assets/branding/farmmer"),
    "ch4": ("YT_CH4_REFRESH_TOKEN", "assets/branding/ch4"),
}


def access_token(env: str) -> str:
    data = urllib.parse.urlencode({
        "client_id": os.environ["YT_CLIENT_ID"], "client_secret": os.environ["YT_CLIENT_SECRET"],
        "refresh_token": os.environ[env], "grant_type": "refresh_token"}).encode()
    with urllib.request.urlopen(urllib.request.Request(TOKEN_URL, data=data), timeout=30) as fh:
        return json.load(fh)["access_token"]


def api(tok: str, method: str, url: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(
        url, method=method, data=json.dumps(body).encode() if body else None,
        headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as fh:
        return json.load(fh)


def upload_banner(tok: str, path: str) -> str:
    with open(path, "rb") as fh:
        img = fh.read()
    if len(img) > 6 * 1024 * 1024:
        raise SystemExit(f"{path} is {len(img)/1e6:.1f} MB; the banner limit is 6 MB")
    req = urllib.request.Request(UP + "?uploadType=media", data=img, method="POST",
                                 headers={"Authorization": f"Bearer {tok}",
                                          "Content-Type": "image/jpeg"})
    with urllib.request.urlopen(req, timeout=90) as fh:
        return json.load(fh)["url"]


def run(slug: str, dry: bool) -> int:
    env, art_dir = CHANNELS[slug]
    banner = os.path.join(art_dir, "banner_2560x1440.jpg")
    if not os.path.exists(banner):
        raise SystemExit(f"no banner at {banner} -- run make_branding.py first")
    tok = access_token(env)
    item = api(tok, "GET", CH + "?part=brandingSettings&mine=true")["items"][0]
    bs = item["brandingSettings"]
    ch = dict(bs.get("channel", {}))
    live = (bs.get("image") or {}).get("bannerExternalUrl")
    print(f"== {slug}  id={item['id']}")
    print(f"   live banner : {live[:64] if live else None}")
    print(f"   new banner  : {banner} ({os.path.getsize(banner)//1024} KB)")
    print(f"   channel obj : title={ch.get('title')!r} desc={(ch.get('description') or '')[:32]!r}...")
    if dry:
        print("   dry-run: not uploading")
        return 0
    url = upload_banner(tok, banner)
    print(f"   uploaded    : {url[:64]}")
    payload = {"id": item["id"], "brandingSettings": {"channel": ch}}
    payload["brandingSettings"]["image"] = dict(bs.get("image") or {})
    payload["brandingSettings"]["image"]["bannerExternalUrl"] = url
    res = api(tok, "PUT", CH + "?part=brandingSettings", payload)
    got = (res.get("brandingSettings", {}).get("image") or {}).get("bannerExternalUrl")
    print(f"   attached    : {'OK' if got == url else 'FAILED'}")
    print(f"   title kept  : {res.get('brandingSettings',{}).get('channel',{}).get('title')!r}")
    print("   avatar: no API exists for the profile picture -- change it in")
    print("           YouTube Studio > Customization > Branding > Picture.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--channel", choices=sorted(CHANNELS), default="ch4")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    try:
        return run(a.channel, a.dry_run)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        if exc.code == 403 and "quota" in body.lower():
            print("quota exhausted -- deferring to after the 08:00 UTC reset")
            return 0
        print(f"HTTP {exc.code}: {body[:300]}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
