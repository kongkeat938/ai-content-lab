#!/usr/bin/env python3
"""Point every Short at the channel's long-form playlist -- the funnel repair.

Measured 2026-11-05: the only reach these channels have is the Shorts Feed, and
Shorts-Feed watch time does not count toward the 4,000-hour YPP threshold. So a
Short is only worth its reach if it sends that reach to a long-form video, where
the watch time *does* count. `publish_shorts.py` writes that link for new Shorts,
but clips uploaded before it did -- or on a channel whose tail was never wired --
carry no destination at all.

This walks a channel's uploads, finds the Shorts whose description lacks the
playlist id, and appends the one tail block. It is idempotent (a Short already
carrying the id is skipped) and additive (it never rewrites existing text).

    python3 scripts/link_shorts.py --channel kongkeat --dry-run
    python3 scripts/link_shorts.py --channel kongkeat --apply

videos.update costs 50 quota units; the 10,000-unit day allows 200 updates.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yt_duration

import argparse
import json
import re
import urllib.error
import urllib.parse
import urllib.request

CHANNELS = {
    "genx": ("YT_CH1_REFRESH_TOKEN", "UCI6EfsgM1HNjrYarvigxyrQ"),
    "dharma": ("YT_CH2_REFRESH_TOKEN", "UCM3QO5L_pmj34n1JVlbhh-w"),
    "kongkeat": ("YT_CH4_REFRESH_TOKEN", "UC7gCIu4G_7QCEJ8hJ-34zoQ"),
}

# The long-form destination per channel, and the sentence that sells it. The
# playlist, not a single video: it survives a deletion and autoplays on.
PLAYLIST = {
    "genx": ("PLXEV3B3DcgsU", "รวมข้อคิดปรัชญาชีวิตไว้ให้แล้ว → "),
    "dharma": ("PLBpZCGnd7Q5Y", "ฟังยาว ๆ ทั้งคืน (รวมทุกตอน) → "),
    "kongkeat": ("PLU4aztRNvt28", "รวมเกร็ดความรู้ทุกตอน → "),
}
TAGS = {
    "genx": "#ปรัชญาชีวิต #ข้อคิด #แง่คิด",
    "dharma": "#ธรรมะก่อนนอน #นอนไม่หลับ #ปล่อยวาง",
    "kongkeat": "#เกร็ดความรู้ #ความรู้รอบตัว #วิทยาศาสตร์",
}


def access_token(token_env: str) -> str:
    data = urllib.parse.urlencode({
        "client_id": os.environ["YT_CLIENT_ID"],
        "client_secret": os.environ["YT_CLIENT_SECRET"],
        "refresh_token": os.environ[token_env],
        "grant_type": "refresh_token"}).encode()
    with urllib.request.urlopen("https://oauth2.googleapis.com/token", data=data, timeout=30) as fh:
        return json.load(fh)["access_token"]


def api(path: str, token: str, method: str = "GET", body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"https://www.googleapis.com/youtube/v3/{path}", data=data, method=method,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as fh:
        return json.load(fh)


def _reason(exc: urllib.error.HTTPError) -> str:
    body = exc.read().decode(errors="replace")
    try:
        return json.loads(body)["error"]["errors"][0]["reason"]
    except Exception:
        return body[:160]


def classify_reason(reason: str, code: int) -> str:
    """'deferred' for a spent shared quota or a burst rate limit, else 'failed'.

    The 10,000-unit Data-API pool is one project shared by all three channels, and
    the upload rails usually spend it before this one runs. A spent pool is a
    *deferral* -- the next tick after the 08:00 UTC reset finishes the work -- and
    must be reported as such, never swallowed into a green run. Any other error is
    a real defect and must exit non-zero.
    """
    if "quotaExceeded" in reason or code == 429 or "RateLimit" in reason:
        return "deferred"
    return "failed"


def shorts_missing_link(token: str, channel_id: str, marker: str,
                        only: list | None) -> list:
    """The Shorts whose description lacks the playlist marker (the read pass)."""
    up = api(f"channels?part=contentDetails&id={channel_id}", token)["items"][0]
    up = up["contentDetails"]["relatedPlaylists"]["uploads"]
    ids, page = [], None
    while True:
        q = f"playlistItems?part=contentDetails&playlistId={up}&maxResults=50"
        if page:
            q += f"&pageToken={page}"
        r = api(q, token)
        ids += [i["contentDetails"]["videoId"] for i in r["items"]]
        page = r.get("nextPageToken")
        if not page:
            break
    todo = []
    for i in range(0, len(ids), 50):
        v = api("videos?part=snippet,contentDetails&id=" + ",".join(ids[i:i + 50]), token)
        for x in v["items"]:
            if seconds(x["contentDetails"]["duration"]) > 180:
                continue                      # long-form is the destination, not a Short
            sn = x["snippet"]
            if marker in (sn.get("description") or ""):
                continue                      # already funnels -- idempotent
            if only and x["id"] not in only:
                continue
            todo.append(x)
    return todo


def seconds(iso: str) -> int:
    return yt_duration.seconds(iso)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", required=True, choices=sorted(CHANNELS))
    ap.add_argument("--apply", action="store_true", help="write the links (default: dry run)")
    ap.add_argument("--only", action="append", help="video id to link (repeatable)")
    args = ap.parse_args()

    paused = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "content", "PAUSED")
    try:
        with open(paused, encoding="utf-8") as fh:
            names = {ln.strip() for ln in fh if ln.strip() and not ln.startswith("#")}
    except OSError:
        names = set()
    if args.channel in names:
        print(f"{args.channel} is paused (content/PAUSED); nothing to link")
        return 0

    token_env, channel_id = CHANNELS[args.channel]
    playlist_id, lead = PLAYLIST[args.channel]
    url = f"https://www.youtube.com/playlist?list={playlist_id}"
    marker = f"list={playlist_id}"
    token = access_token(token_env)

    try:
        todo = shorts_missing_link(token, channel_id, marker, args.only)
    except urllib.error.HTTPError as exc:
        reason = _reason(exc)          # reads the body once
        kind = classify_reason(reason, exc.code)
        print(f"{args.channel}: read pass {kind} ({exc.code} {reason})")
        # A spent pool is not a green run: the funnel is unwired and no one is told.
        return 2 if kind == "deferred" else 1

    print(f"{args.channel}: {len(todo)} Short(s) missing {marker}")
    for x in todo:
        print(f"  {x['id']}: {x['snippet']['title'][:55]}")
    if not args.apply:
        print("(dry run -- pass --apply to write)")
        return 0

    block = f"\n\n{lead}{url}\n\n{TAGS[args.channel]}"
    ok = failed = deferred = 0
    for x in todo:
        sn = x["snippet"]
        body = {"id": x["id"], "snippet": {
            "title": sn["title"],
            "description": ((sn.get("description") or "") + block)[:5000],
            "categoryId": sn.get("categoryId", "22"),
            "tags": sn.get("tags", []),
            "defaultLanguage": sn.get("defaultLanguage", "th"),
            "defaultAudioLanguage": sn.get("defaultAudioLanguage", "th"),
        }}
        try:
            api("videos?part=snippet", token, method="PUT", body=body)
            print(f"  {x['id']}: linked")
            ok += 1
        except urllib.error.HTTPError as exc:
            reason = _reason(exc)
            if classify_reason(reason, exc.code) == "deferred":
                print(f"  {x['id']}: deferred ({exc.code} {reason})")
                deferred += 1
            else:
                print(f"  {x['id']}: FAIL {exc.code} {reason}")
                failed += 1
    print(f"done: {ok} linked, {deferred} deferred, {failed} failed")
    if failed:
        return 1
    # A deferral (spent pool / burst limit) is not green: exit 2 so the run is
    # visibly incomplete and the next tick after the reset retries, rather than
    # a "success" that hides an unwired funnel.
    return 2 if deferred and not ok else 0


if __name__ == "__main__":
    sys.exit(main())
