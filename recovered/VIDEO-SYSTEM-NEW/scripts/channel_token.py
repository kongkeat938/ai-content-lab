#!/usr/bin/env python3
"""One place to turn a channel slug into a live access token.

`delete_video.py` and `private_videos.py` used to borrow `publish_batch.access_token`
-- the upload rail -- just to reach the Data API. When the build/upload system was
removed (K, 2026-11-20) that borrow would have taken the two maintenance tools with
it, so the token exchange lives here instead. The slug -> env mapping stays in
`yt_auth.CHANNEL_ENV` (by channel id), so a new channel is named once.

    from channel_token import access_token
    tok = access_token("dharma")
"""
from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import yt_auth  # noqa: E402

# slug -> channel id, the same ids yt_auth.CHANNEL_ENV is keyed by.
SLUG_CHANNEL = {
    "dharma": "UCM3QO5L_pmj34n1JVlbhh-w",
    "genx": "UCI6EfsgM1HNjrYarvigxyrQ",
    "aeris-music": "UCm44BjAn03ruOF-WaA3ZRww",
    "kongkeat-story": "UC7gCIu4G_7QCEJ8hJ-34zoQ",
}


def token_env(slug: str) -> str:
    cid = SLUG_CHANNEL.get(slug)
    if not cid or cid not in yt_auth.CHANNEL_ENV:
        sys.exit(f"unknown channel slug {slug!r}; known: {sorted(SLUG_CHANNEL)}")
    return yt_auth.CHANNEL_ENV[cid]


def access_token(slug: str) -> str:
    """Exchange the channel's refresh token for an access token, or exit loudly."""
    var = token_env(slug)
    cid = os.environ.get("YT_CLIENT_ID")
    sec = os.environ.get("YT_CLIENT_SECRET")
    rt = os.environ.get(var)
    if not (cid and sec and rt):
        sys.exit(f"Missing credentials: need YT_CLIENT_ID, YT_CLIENT_SECRET and {var}")
    data = urllib.parse.urlencode({
        "client_id": cid, "client_secret": sec,
        "refresh_token": rt, "grant_type": "refresh_token"}).encode()
    with urllib.request.urlopen("https://oauth2.googleapis.com/token", data=data,
                                timeout=30) as fh:
        return json.load(fh)["access_token"]
