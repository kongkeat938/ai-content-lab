#!/usr/bin/env python3
"""Channel admin — the thing that actually runs the three channels.

Aider is a *code* tool; it cannot log in to YouTube. The channel admin is this
script plus the tokens already in the environment. It reads each channel's live
numbers, lists comments, drafts replies with a free advisor, and posts a reply
once approved.

    python3 scripts/channel_admin.py status                 # all channels, live
    python3 scripts/channel_admin.py comments genx          # comment threads
    python3 scripts/channel_admin.py draft genx <threadId>  # draft a Thai reply
    python3 scripts/channel_admin.py reply <commentId> "text"  # post a reply

Comment read/reply needs the `youtube.force-ssl` scope. The current tokens were
granted `youtube.upload` + `youtube.readonly` only, so comment calls return 403
until the owner re-consents once with `yt_auth.py --scopes force-ssl`. `status`
works today with no new consent.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analytics import CHANNELS, access_token, analytics  # noqa: E402

API = "https://www.googleapis.com/youtube/v3/"


def _get(path: str, params: dict, token: str) -> dict:
    req = urllib.request.Request(
        API + path + "?" + urllib.parse.urlencode(params),
        headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=40) as fh:
        return json.load(fh)


def _post(path: str, params: dict, body: dict, token: str) -> dict:
    req = urllib.request.Request(
        API + path + "?" + urllib.parse.urlencode(params),
        data=json.dumps(body).encode(), method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=40) as fh:
        return json.load(fh)


def status(name: str, token: str) -> dict:
    it = _get("channels", {"part": "snippet,statistics,contentDetails", "mine": "true"}, token)["items"][0]
    st = it["statistics"]
    print(f"\n=== {name}: {it['snippet']['title']}")
    print(f"  subs={st.get('subscriberCount')}  videos={st.get('videoCount')}  "
          f"total-views={int(st.get('viewCount', 0)):,}")
    up = it["contentDetails"]["relatedPlaylists"]["uploads"]
    pl = _get("playlistItems", {"part": "contentDetails", "playlistId": up,
                                "maxResults": "1"}, token)
    if pl.get("items"):
        vid = pl["items"][0]["contentDetails"]["videoId"]
        v = _get("videos", {"part": "snippet,statistics", "id": vid}, token)["items"][0]
        print(f"  latest: {v['snippet']['publishedAt'][:10]}  {v['snippet']['title'][:44]}"
              f"  views={v['statistics'].get('viewCount')}")
    return {"title": it["snippet"]["title"], "subs": st.get("subscriberCount"),
            "videos": st.get("videoCount"), "views": st.get("viewCount")}


def latest(name: str, limit: int, token: str) -> list:
    it = _get("channels", {"part": "snippet,contentDetails", "mine": "true"}, token)["items"][0]
    up = it["contentDetails"]["relatedPlaylists"]["uploads"]
    pl = _get("playlistItems", {"part": "contentDetails", "playlistId": up,
                                "maxResults": str(limit)}, token)
    ids = [x["contentDetails"]["videoId"] for x in pl.get("items", [])]
    if not ids:
        print(f"\n=== {name}: no uploads")
        return []
    vids = _get("videos", {"part": "snippet,statistics", "id": ",".join(ids)}, token)["items"]
    print(f"\n=== {name}: newest {len(vids)} uploads")
    out = []
    for v in vids:
        s = v["snippet"]
        out.append({"id": v["id"], "date": s["publishedAt"][:10],
                    "views": int(v["statistics"].get("viewCount", 0)), "title": s["title"]})
        print(f"  {out[-1]['date']}  {out[-1]['views']:>7,}  {s['title'][:52]}")
    return out


def comments(name: str, token: str) -> list:
    it = _get("channels", {"part": "id", "mine": "true"}, token)["items"][0]
    try:
        r = _get("commentThreads", {"part": "snippet", "allThreadsRelatedToChannelId": it["id"],
                                    "maxResults": "25", "order": "time"}, token)
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        if e.code == 403 and "scope" in body:
            print(f"[{name}] comments need the youtube.force-ssl scope — "
                  "re-run yt_auth.py with --scopes force-ssl (owner, once).")
            return []
        raise
    rows = []
    for t in r.get("items", []):
        s = t["snippet"]["topLevelComment"]["snippet"]
        rows.append({"threadId": t["id"], "commentId": t["snippet"]["topLevelComment"]["id"],
                     "author": s["authorDisplayName"], "text": s["textDisplay"],
                     "likes": s.get("likeCount", 0)})
    for row in rows:
        print(f"  [{row['threadId']}] {row['author']}: {row['text'][:70]}  (likes {row['likes']})")
    return rows


def draft(text: str) -> str:
    """Draft a short Thai reply with the free advisor (Pollinations, keyless)."""
    prompt = ("เขียนตอบคอมเมนต์ YouTube ภาษาไทย สั้น สุภาพ เป็นมิตร ไม่ขายของ "
              "ไม่เกิน 2 ประโยค ตอบคอมเมนต์นี้: " + text)
    body = {"model": "openai-fast", "messages": [{"role": "user", "content": prompt}]}
    req = urllib.request.Request("https://text.pollinations.ai/openai",
                                 data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as fh:
        return json.load(fh)["choices"][0]["message"]["content"].strip()


def reply(comment_id: str, text: str, token: str) -> dict:
    return _post("comments", {"part": "snippet"},
                 {"snippet": {"parentId": comment_id, "textOriginal": text}}, token)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["status", "latest", "comments", "draft", "reply"])
    ap.add_argument("arg1", nargs="?")
    ap.add_argument("arg2", nargs="?")
    ap.add_argument("--channel", choices=list(CHANNELS))
    ap.add_argument("--limit", type=int, default=10, help="rows for the latest command")
    args = ap.parse_args()

    names = [args.channel] if args.channel else list(CHANNELS)
    if args.cmd == "status":
        for n in names:
            status(n, access_token(CHANNELS[n][0]))
        return 0
    if args.cmd == "latest":
        for n in names:
            latest(n, args.limit, access_token(CHANNELS[n][0]))
        return 0
    if args.cmd == "comments":
        for n in names:
            comments(n, access_token(CHANNELS[n][0]))
        return 0
    if args.cmd == "draft":
        print(draft(args.arg2 or ""))
        return 0
    if args.cmd == "reply":
        n = args.channel or "genx"
        out = reply(args.arg1, args.arg2 or "", access_token(CHANNELS[n][0]))
        print("posted:", out.get("id"))
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
