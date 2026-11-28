#!/usr/bin/env python3
"""Report videos that are already on a channel more than once.

A duplicate is a video whose title exactly matches another on the same channel.
That is the signal that caught the real one: night_120 went live twice on
2026-11-03 because two publish runs raced on a stale checkout and the loser's
push was rejected, so the manifest never learned the second id.

Two same-length Shorts are *not* flagged -- the generator makes many clips of a
similar duration, and a duration match alone is not evidence. Only a repeated
title is, because publish_batch.py sets the title verbatim from the manifest.

    python3 scripts/check_duplicates.py            # all channels
    python3 scripts/check_duplicates.py --slug dharma
    python3 scripts/check_duplicates.py --apply     # unlist the redundant copies

`--apply` keeps the copy with the most views and sets the others **unlisted** (not
deleted, so it can be undone), and appends every change to
`content/privacy_ledger.json`. Run it twice: the first run with --apply resolves the
groups, the second exits 0 -- that is how the gate proves the fix.

Needs YT_CLIENT_ID, YT_CLIENT_SECRET and each YT_*_REFRESH_TOKEN.
Exit code is 1 when a duplicate is still live after the run, so a workflow can gate.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yt_duration

import argparse
import json
import re
import time
import urllib.parse
import urllib.request
from collections import defaultdict

CHANNELS = {
    "genx": ("YT_CH1_REFRESH_TOKEN", "UCI6EfsgM1HNjrYarvigxyrQ"),
    "dharma": ("YT_CH2_REFRESH_TOKEN", "UCM3QO5L_pmj34n1JVlbhh-w"),
    "kongkeat": ("YT_CH4_REFRESH_TOKEN", "UC7gCIu4G_7QCEJ8hJ-34zoQ"),
}


def access_token(env: str) -> str:
    data = urllib.parse.urlencode({
        "client_id": os.environ["YT_CLIENT_ID"],
        "client_secret": os.environ["YT_CLIENT_SECRET"],
        "refresh_token": os.environ[env],
        "grant_type": "refresh_token"}).encode()
    with urllib.request.urlopen("https://oauth2.googleapis.com/token", data=data, timeout=30) as fh:
        return json.load(fh)["access_token"]


def api(path: str, token: str) -> dict:
    req = urllib.request.Request(f"https://www.googleapis.com/youtube/v3/{path}",
                                 headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=30) as fh:
        return json.load(fh)


def seconds(iso: str) -> int:
    return yt_duration.seconds(iso)


def scan(slug: str) -> list[dict]:
    env, cid = CHANNELS[slug]
    token = access_token(env)
    up = api(f"channels?part=contentDetails&id={cid}", token)["items"][0]
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
    # Measured 2026-11-28: the uploads playlist returned E1gxiblSUo0 three times, so the
    # report showed a "duplicate" whose redundant copies were the keeper itself -- and
    # --apply would have unlisted the video it had just decided to keep.
    ids = list(dict.fromkeys(ids))
    rows = []
    for i in range(0, len(ids), 50):
        v = api("videos?part=snippet,contentDetails,statistics,status&id="
                + ",".join(ids[i:i + 50]), token)
        for x in v["items"]:
            rows.append({"id": x["id"], "title": x["snippet"]["title"],
                         "dur": seconds(x["contentDetails"]["duration"]),
                         "pub": x["snippet"]["publishedAt"],
                         "priv": x["status"]["privacyStatus"],
                         "views": int(x["statistics"].get("viewCount", 0)),
                         "status": x["status"]})
    return rows


LEDGER = "content/privacy_ledger.json"


def public_groups(rows: list[dict]) -> dict[str, list[dict]]:
    """Groups that are a real duplicate: two or more copies still public.

    A public copy next to an unlisted one is not a duplicate -- `remake_shorts.py`
    parks the old clip exactly that way, so counting it would report a problem that
    is already solved."""
    by_title = defaultdict(dict)
    for r in rows:
        if r["priv"] == "public":
            by_title[r["title"]][r["id"]] = r
    return {t: list(rs.values()) for t, rs in by_title.items() if len(rs) > 1}


def choose_keeper(rows: list[dict]) -> tuple[dict, list[dict]]:
    """Keep the copy the audience chose: most views, then the newer upload."""
    order = sorted(rows, key=lambda r: (r["views"], r["pub"]), reverse=True)
    return order[0], order[1:]


def unlisted_status(status: dict) -> dict:
    """The whole status object with only privacyStatus changed.

    `videos.update` REPLACES the parts it is given, so sending a bare
    {"privacyStatus": "unlisted"} would drop selfDeclaredMadeForKids and the rest."""
    out = dict(status)
    out["privacyStatus"] = "unlisted"
    return out


def put_status(token: str, video_id: str, status: dict,
               send=None) -> tuple[int, str]:
    send = send or (lambda path, body, tok: _put(path, body, tok))
    return send(f"videos?part=status", {"id": video_id, "status": status}, token)


def _put(path: str, body: dict, token: str) -> tuple[int, str]:
    req = urllib.request.Request(
        f"https://www.googleapis.com/youtube/v3/{path}",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="PUT")
    try:
        with urllib.request.urlopen(req, timeout=60) as fh:
            return fh.status, fh.read().decode(errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode(errors="replace")


def record(entries: list[dict]) -> None:
    """Append to the privacy ledger, skipping a video that already has this entry."""
    if not entries:
        return
    try:
        data = json.load(open(LEDGER, encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        data = {"changes": []}
    seen = {(c["video_id"], c["to"]) for c in data["changes"]}
    for e in entries:
        if (e["video_id"], e["to"]) not in seen:
            data["changes"].append(e)
            seen.add((e["video_id"], e["to"]))
    os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
    with open(LEDGER, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
        fh.write("\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", choices=list(CHANNELS), help="one channel (default: all)")
    ap.add_argument("--apply", action="store_true",
                    help="unlist the redundant copies (keeps the one with the most views)")
    ap.add_argument("--set-public", metavar="VIDEO_ID",
                    help="put one clip back to public (reversible) and record why")
    ap.add_argument("--reason", default="back in the feed: our own clip, no duplicate title")
    args = ap.parse_args()

    if args.set_public:
        slug = args.slug or "dharma"
        env, _cid = CHANNELS[slug]
        token = access_token(env)
        rows = {r["id"]: r for r in scan(slug)}
        row = rows.get(args.set_public)
        if not row:
            print(f"{args.set_public}: not on {slug}")
            return 1
        before = row["priv"]
        status = dict(row["status"])
        status["privacyStatus"] = "public"
        code, body = put_status(token, args.set_public, status)
        print(f"{args.set_public}: {before} -> public  HTTP {code}")
        if code != 200:
            print(body[:300])
            return 1
        record([{"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                 "channel": slug, "video_id": args.set_public, "title": row["title"],
                 "from": before, "to": "public", "views_at_change": row["views"],
                 "reason": args.reason}])
        return 0

    slugs = [args.slug] if args.slug else list(CHANNELS)
    found = 0
    changes = []
    for slug in slugs:
        rows = scan(slug)
        dups = public_groups(rows)
        print(f"\n===== {slug}: {len(rows)} videos, {len(dups)} duplicated title(s) =====")
        for title, group in sorted(dups.items()):
            found += 1
            keep, redundant = choose_keeper(group)
            print(f"\n  DUPLICATE: {title}")
            for r in [keep] + redundant:
                tag = "KEEP" if r is keep else "redundant"
                print(f"    [{tag:9s}] {r['pub'][:16]}  {r['dur']:5d}s  "
                      f"{r['priv']:8s} views={r['views']:>5}  {r['id']}")
            if args.apply:
                token = access_token(CHANNELS[slug][0])
                for r in redundant:
                    if r["id"] == keep["id"]:
                        continue
                    code, body = put_status(token, r["id"], unlisted_status(r["status"]))
                    print(f"      unlist {r['id']} -> HTTP {code}")
                    if code == 200:
                        found -= 1
                        changes.append({"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                        "channel": slug, "video_id": r["id"], "title": title,
                                        "from": r["priv"], "to": "unlisted",
                                        "views_at_change": r["views"],
                                        "reason": f"duplicate of {keep['id']} "
                                                  f"({keep['views']} views); one live title = one video"})
                if changes:
                    record(changes)
    print(f"\n{found} duplicate group(s) still live")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
