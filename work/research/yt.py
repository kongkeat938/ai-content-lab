#!/usr/bin/env python3
"""Read-only YouTube Data API helper for competitor research.

Uses the per-channel refresh tokens in the environment. Quota discipline:
search.list costs 100 units, everything else here costs 1 unit per call.
"""
from __future__ import annotations
import json, os, sys, urllib.parse, urllib.request, urllib.error

TOKENS = {
    "ch1": "YT_CH1_REFRESH_TOKEN",
    "ch2": "YT_CH2_REFRESH_TOKEN",
    "ch4": "YT_CH4_REFRESH_TOKEN",
}
_cache: dict[str, str] = {}


def access_token(channel: str) -> str:
    if channel in _cache:
        return _cache[channel]
    rt = os.environ.get(TOKENS[channel])
    if not rt:
        sys.exit(f"no refresh token for {channel}")
    data = urllib.parse.urlencode({
        "client_id": os.environ["YT_CLIENT_ID"],
        "client_secret": os.environ["YT_CLIENT_SECRET"],
        "refresh_token": rt,
        "grant_type": "refresh_token",
    }).encode()
    req = urllib.request.Request("https://oauth2.googleapis.com/token", data=data)
    with urllib.request.urlopen(req, timeout=20) as r:
        tok = json.load(r)["access_token"]
    _cache[channel] = tok
    return tok


def get(channel: str, path: str, params: dict) -> dict:
    url = "https://www.googleapis.com/youtube/v3/" + path + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + access_token(channel)})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        raise SystemExit(f"HTTP {e.code} on {path}: {body[:500]}")


if __name__ == "__main__":
    # smoke test: my own channel
    for slug, envk in TOKENS.items():
        d = get(slug, "channels", {"part": "snippet,statistics,contentDetails", "mine": "true"})
        for it in d.get("items", []):
            s = it["statistics"]
            print(f"{slug}: {it['snippet']['title']}  id={it['id']}  "
                  f"subs={s.get('subscriberCount','?')} videos={s.get('videoCount','?')} "
                  f"views={s.get('viewCount','?')}")
