#!/usr/bin/env python3
"""Upload ready videos to a channel from a manifest -- no browser, no human.

This is the rail that turns a finished, verified render into a live video. It is
built to run on a CI runner, where the pod's problems (a recycled login, a
10,000-unit daily quota shared with every other call) do not apply to a fresh
day's upload quota.

    python3 scripts/publish_batch.py --dry-run       # show what it would post
    python3 scripts/publish_batch.py                 # upload every 'ready' entry
    python3 scripts/publish_batch.py --only night_120
    python3 scripts/publish_batch.py --privacy private   # override for a test

Double-post safety: an entry with a `video_id` is never uploaded again, and the
manifest is written back the moment an upload returns an id. `videos.insert` has
its own daily quota (100/day) separate from the read endpoints, so a spent
read-quota does not block publishing -- but it does block the thumbnail step,
which is best-effort and never fatal.

Credentials: YT_CLIENT_ID, YT_CLIENT_SECRET and YT_<SLUG>_REFRESH_TOKEN, exactly
like scripts/set_thumbnails.py and publish_youtube.py.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

MANIFEST = os.path.join(ROOT, "content", "ch2_publish.json")
TOKEN_ENV = {
    "dharma": "YT_CH2_REFRESH_TOKEN",
    "genx": "YT_CH1_REFRESH_TOKEN",
    "aeris-music": "YT_CH3_REFRESH_TOKEN",
    "kongkeat-story": "YT_CH4_REFRESH_TOKEN",
}
SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
          "https://www.googleapis.com/auth/youtube"]


def access_token(slug: str) -> str:
    cid = os.environ.get("YT_CLIENT_ID")
    sec = os.environ.get("YT_CLIENT_SECRET")
    var = TOKEN_ENV.get(slug, f"YT_{slug.upper().replace('-', '_')}_REFRESH_TOKEN")
    rt = os.environ.get(var)
    if not (cid and sec and rt):
        sys.exit(f"Missing credentials: need YT_CLIENT_ID, YT_CLIENT_SECRET and {var}")
    data = urllib.parse.urlencode({
        "client_id": cid, "client_secret": sec,
        "refresh_token": rt, "grant_type": "refresh_token"}).encode()
    try:
        return json.load(urllib.request.urlopen(
            "https://oauth2.googleapis.com/token", data=data, timeout=30))["access_token"]
    except urllib.error.HTTPError as exc:
        sys.exit(f"Token refresh failed for {slug} ({var}): {exc.code} {exc.read().decode()[:200]}")


def save(man: dict, path: str) -> None:
    tmp = path + ".part"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(man, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    os.replace(tmp, path)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default=MANIFEST)
    ap.add_argument("--only", action="append")
    ap.add_argument("--privacy", choices=["private", "unlisted", "public"])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--cache", default=os.path.join(ROOT, "work", "publish_cache"))
    args = ap.parse_args()

    with open(args.manifest, encoding="utf-8") as fh:
        man = json.load(fh)
    slug = man["channel_slug"]
    vids = man["videos"]
    if args.only:
        vids = [v for v in vids if v["key"] in args.only]

    todo = [v for v in vids if not v.get("video_id")]
    done = [v for v in vids if v.get("video_id")]
    print(f"channel {slug} ({man['channel_id']}): {len(todo)} to publish, "
          f"{len(done)} already live")
    for v in done:
        print(f"  {v['key']}: already live {v['video_id']} — skipping")

    if args.dry_run:
        for v in todo:
            print(f"  {v['key']}: would upload {v['video_url']}")
            print(f"      title   {v['title']}")
            print(f"      privacy {args.privacy or v.get('privacy','public')}")
            print(f"      thumb   {v.get('thumbnail','-')}")
        return 0
    if not todo:
        print("nothing to do")
        return 0

    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from googleapiclient.errors import HttpError

    # load_credentials picks the token file; the env refresh token materialises it.
    os.environ["YT_TOKEN_PATH"] = os.path.expanduser(f"~/.config/content-lab/yt_token_{slug}.json")
    from yt_auth import load_credentials
    creds = load_credentials(man["channel_id"])
    yt = build("youtube", "v3", credentials=creds, cache_discovery=False)

    # Refuse to post to the wrong channel before a single byte moves.
    res = yt.channels().list(part="snippet", mine=True).execute()
    got = res["items"][0]["id"] if res.get("items") else None
    if got != man["channel_id"]:
        sys.exit(f"WRONG CHANNEL: token is {got}, manifest says {man['channel_id']}")
    print(f"  authorised as {res['items'][0]['snippet']['title']} ({got})")

    os.makedirs(args.cache, exist_ok=True)
    rc = 0
    for v in todo:
        key = v["key"]
        local = os.path.join(args.cache, f"{key}.mp4")
        if not (os.path.exists(local) and os.path.getsize(local) > 0):
            print(f"downloading {v['video_url']} -> {local}")
            req = urllib.request.Request(v["video_url"],
                                         headers={"User-Agent": "content-lab-publish/1.0"})
            with urllib.request.urlopen(req, timeout=1800) as src, open(local, "wb") as out:
                while True:
                    chunk = src.read(1 << 18)
                    if not chunk:
                        break
                    out.write(chunk)
        privacy = args.privacy or v.get("privacy", "public")
        body = {
            "snippet": {
                "title": v["title"][:100],
                "description": v.get("description", "")[:5000],
                "tags": v.get("tags", [])[:500],
                "categoryId": str(v.get("category_id", "22")),
                "defaultLanguage": "th",
                "defaultAudioLanguage": "th",
            },
            "status": {
                "privacyStatus": privacy,
                "selfDeclaredMadeForKids": False,
                "license": "youtube",
                "embeddable": True,
            },
        }
        print(f"\nuploading {key} ({os.path.getsize(local)/1e6:.0f} MB) as {privacy} ...")
        try:
            request = yt.videos().insert(
                part="snippet,status", body=body,
                media_body=MediaFileUpload(local, chunksize=16 * 1024 * 1024,
                                           resumable=True))
            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    print(f"  {int(status.progress() * 100)}%", flush=True)
        except HttpError as exc:
            print(f"  UPLOAD FAILED: {exc}", file=sys.stderr)
            rc = 1
            continue

        vid = response["id"]
        url = f"https://youtu.be/{vid}"
        v["video_id"] = vid
        v["url"] = url
        v["state"] = "published"
        save(man, args.manifest)   # record BEFORE anything else can fail
        print(f"  live: {url} ({response['status']['privacyStatus']}) — recorded")

        thumb = v.get("thumbnail")
        if thumb:
            path = thumb if os.path.isabs(thumb) else os.path.join(ROOT, thumb)
            try:
                yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(path)).execute()
                print("  thumbnail set")
            except HttpError as exc:
                print(f"  thumbnail deferred ({exc.status_code}); "
                      f"set_thumbnails.py will finish it", file=sys.stderr)

    live = [v for v in man["videos"] if v.get("video_id")]
    print(f"\n{len(live)}/{len(man['videos'])} live: " +
          ", ".join(f"{v['key']}={v['url']}" for v in live))
    return rc


if __name__ == "__main__":
    sys.exit(main())
