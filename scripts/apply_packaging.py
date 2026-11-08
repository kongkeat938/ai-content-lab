#!/usr/bin/env python3
"""Apply the ch2 packaging plan: new cover, new title, new tags, per video.

The competitor research (2026-11-08) found the blocker is packaging, not reach:
a "ธรรมะก่อนนอน" search returns no Farmmer video while 4k-subscriber channels
hold 600k views. This turns content/ch2_packaging.json into the three changes
that lift click-through -- a glowing gold-Buddha cover, a keyword-first title
with an emotional hook, and the tags the channel was missing.

It never invents work: covers come from make_cover_youtube.py, and both the
title and the thumbnail are written through the Data API with the token the
other jobs already use, so no browser and no new consent are needed.

    python3 scripts/apply_packaging.py                 # plan only
    python3 scripts/apply_packaging.py --apply         # write covers + titles
    python3 scripts/apply_packaging.py --apply --only night_money_01

Quota: videos.update and thumbnails.set both draw the daily pool, which resets
at 08:00 UTC. A 403 quotaExceeded is reported as `deferred` and does not fail
the run -- the scheduled job retries after the reset. A ledger records what was
applied so a retry never redoes a finished video.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from make_cover_youtube import build as build_cover, pick_art  # noqa: E402

MANIFEST = os.path.join(ROOT, "content", "ch2_publish.json")
PACKAGING = os.path.join(ROOT, "content", "ch2_packaging.json")
THUMB_MANIFEST = os.path.join(ROOT, "content", "ch2_thumbnails.json")
LEDGER = os.path.join(ROOT, "content", "packaging_changes.json")
THUMB_DIR = os.path.join(ROOT, "assets", "branding", "farmmer", "thumbs")
TOKEN_ENV = {"dharma": "YT_CH2_REFRESH_TOKEN", "genx": "YT_CH1_REFRESH_TOKEN",
             "aeris-music": "YT_CH3_REFRESH_TOKEN", "kongkeat-story": "YT_CH4_REFRESH_TOKEN"}
API = "https://www.googleapis.com/youtube/v3/videos"
SET_URL = "https://www.googleapis.com/upload/youtube/v3/thumbnails/set"
TOKEN_URL = "https://oauth2.googleapis.com/token"

# Every ch2 video carries these, so a search for any one of them can surface it.
BASE_TAGS = ["ธรรมะก่อนนอน", "ฟังธรรมะก่อนนอน", "ธรรมะกล่อมหลับ", "นอนไม่หลับ",
             "หลับลึก", "ปล่อยวาง", "ใจสงบ", "สมาธิก่อนนอน", "ธรรมะผ่อนคลาย",
             "นอนหลับสบาย", "คลายเครียด", "เสียงธรรมะ", "ธรรมะสอนใจ"]


def access_token(slug: str) -> str:
    cid = os.environ.get("YT_CLIENT_ID")
    sec = os.environ.get("YT_CLIENT_SECRET")
    var = TOKEN_ENV.get(slug, f"YT_{slug.upper().replace('-', '_')}_REFRESH_TOKEN")
    rt = os.environ.get(var)
    if not (cid and sec and rt):
        sys.exit(f"missing credentials: YT_CLIENT_ID, YT_CLIENT_SECRET, {var}")
    data = urllib.parse.urlencode({"client_id": cid, "client_secret": sec,
                                   "refresh_token": rt, "grant_type": "refresh_token"}).encode()
    try:
        return json.load(urllib.request.urlopen(TOKEN_URL, data=data, timeout=30))["access_token"]
    except urllib.error.HTTPError as exc:
        sys.exit(f"token refresh failed ({var}): {exc.code}")


def reason(exc: urllib.error.HTTPError) -> str:
    body = exc.read().decode(errors="replace")
    try:
        return json.loads(body)["error"]["errors"][0]["reason"]
    except Exception:
        return body[:160]


def key_to_video() -> dict:
    """Map every packaging key to a live video id.

    The long-form rail keys by episode name (night_120); the older uploads key by
    video id. ch2_publish.json resolves the first; an 11-char key is the second.
    """
    with open(MANIFEST, encoding="utf-8") as fh:
        man = json.load(fh)
    out = {}
    for v in man.get("videos", []):
        if v.get("video_id"):
            out[v["key"]] = v["video_id"]
    return out


def snippet(vid: str, token: str) -> dict:
    req = urllib.request.Request(
        f"{API}?part=snippet&id={vid}&fields=items/snippet(title,categoryId,tags)",
        headers={"Authorization": f"Bearer {token}"})
    items = json.load(urllib.request.urlopen(req, timeout=30)).get("items", [])
    return items[0]["snippet"] if items else {}


def set_title_tags(vid: str, title: str, tags: list, category: str, token: str) -> None:
    body = {"id": vid, "snippet": {"title": title, "categoryId": category, "tags": tags}}
    req = urllib.request.Request(f"{API}?part=snippet", data=json.dumps(body).encode(),
                                 method="PUT",
                                 headers={"Authorization": f"Bearer {token}",
                                          "Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=40)


def set_thumb(vid: str, path: str, token: str) -> None:
    with open(path, "rb") as fh:
        img = fh.read()
    req = urllib.request.Request(f"{SET_URL}?videoId={vid}&uploadType=media",
                                 data=img, method="POST",
                                 headers={"Authorization": f"Bearer {token}",
                                          "Content-Type": "image/jpeg"})
    urllib.request.urlopen(req, timeout=90)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write to YouTube (default: plan)")
    ap.add_argument("--only", action="append", help="packaging key (repeatable)")
    ap.add_argument("--skip-thumb", action="store_true", help="titles only")
    ap.add_argument("--skip-title", action="store_true", help="covers only")
    args = ap.parse_args()

    with open(PACKAGING, encoding="utf-8") as fh:
        plan = json.load(fh)["videos"]
    k2v = key_to_video()
    done = set()
    if os.path.exists(LEDGER):
        with open(LEDGER, encoding="utf-8") as fh:
            done = {c["video_id"] for c in json.load(fh).get("changes", [])}

    items = []
    for key, spec in plan.items():
        vid = k2v.get(key) or (key if re.fullmatch(r"[A-Za-z0-9_-]{11}", key) else None)
        if not vid:
            print(f"  {key}: no video id -- skipped"); continue
        if args.only and key not in args.only:
            continue
        items.append((key, vid, spec))
    print(f"packaging plan: {len(items)} video(s)\n")

    os.makedirs(THUMB_DIR, exist_ok=True)
    # Covers are generated locally and committed; that costs no quota.
    covers = {}
    for key, vid, spec in items:
        out = os.path.join(THUMB_DIR, f"{vid}.jpg")
        build_cover(pick_art(key), out, "ธรรมะก่อนนอน",
                    spec["line1"], spec["line2"], spec["sub"], key=key)
        covers[key] = out

    if not args.apply:
        for key, vid, spec in items:
            print(f"  {key} -> {vid}")
            print(f"     title: {spec['title']}")
            print(f"     cover: {covers[key]}")
        print("\n(plan only -- pass --apply to write)")
        return 0

    token = access_token("dharma")
    changes, deferred, failed = [], 0, 0
    for key, vid, spec in items:
        if vid in done:
            print(f"  {key}: already applied, skipped"); continue
        cur = {}
        try:
            cur = snippet(vid, token)
        except urllib.error.HTTPError as exc:
            r = reason(exc)
            if "quotaExceeded" in r:
                print("  quota exhausted -- re-run after the 08:00 UTC reset"); break
            print(f"  {key}: read FAILED {exc.code} {r}"); failed += 1; continue
        tags = list(dict.fromkeys(BASE_TAGS + (cur.get("tags") or [])))
        try:
            if not args.skip_title:
                set_title_tags(vid, spec["title"], tags, cur.get("categoryId", "22"), token)
            if not args.skip_thumb:
                set_thumb(vid, covers[key], token)
            changes.append({"video_id": vid, "key": key, "title": spec["title"],
                            "cover": os.path.relpath(covers[key], ROOT),
                            "at": datetime.now(timezone.utc).isoformat()})
            print(f"  {key} ({vid}): OK")
        except urllib.error.HTTPError as exc:
            r = reason(exc)
            if "quotaExceeded" in r:
                print(f"  {key}: deferred (quota resets 08:00 UTC)"); deferred += 1
            elif "429" in str(exc.code) or "RateLimit" in r:
                print(f"  {key}: deferred (rate limited)"); deferred += 1
            else:
                print(f"  {key}: FAILED {exc.code} {r}"); failed += 1
        time.sleep(1.5)

    # keep the thumbnail manifest pointing at the covers we just made
    with open(THUMB_MANIFEST, encoding="utf-8") as fh:
        tm = json.load(fh)
    for key, vid, spec in items:
        tm["thumbnails"][vid] = os.path.relpath(covers[key], ROOT)
    with open(THUMB_MANIFEST, "w", encoding="utf-8") as fh:
        json.dump(tm, fh, ensure_ascii=False, indent=2)

    if changes:
        doc = {"changes": []}
        if os.path.exists(LEDGER):
            with open(LEDGER, encoding="utf-8") as fh:
                doc = json.load(fh)
        doc.setdefault("changes", []).extend(changes)
        with open(LEDGER, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, ensure_ascii=False, indent=2)
    print(f"\ndone: {len(changes)} applied, {deferred} deferred, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
