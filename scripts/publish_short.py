#!/usr/bin/env python3
"""Publish a vertical Short — the discovery funnel for a long-form episode.

The strategy (COMPETITOR-STRATEGY.md §5.3) is long-form + Shorts: the long clip
is the product, the Short is the pipe that brings strangers to it. This uploads
one Short and links it back to the episode, reusing the channel guard and the
receipt store from publish_youtube.py, so a Short can never land on the wrong
channel.

    python3 scripts/publish_short.py ep02 \
        --file site/media/ep02_short_hook.mp4 \
        --channel ch4-story --privacy public --dry-run

The clip comes from work/research/make_short.py. #Shorts in the title is what
tells YouTube to treat it as a Short.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from publish_youtube import (  # noqa: E402  (same-dir sibling)
    assert_channel, find_channel, record_receipt, token_path_for,
)

REPO = os.path.dirname(_HERE)


def read_receipts() -> list[dict]:
    path = os.path.join(REPO, "receipts", "receipts.jsonl")
    if not os.path.exists(path):
        return []
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return out


def long_form_url(ep_slug: str) -> str | None:
    """The episode's already-published long-form URL, if one was recorded."""
    for r in reversed(read_receipts()):
        if r.get("slug") == ep_slug and r.get("platform") == "youtube":
            return r.get("url")
    return None


def load_meta(ep_slug: str) -> dict:
    path = os.path.join(REPO, "episodes", ep_slug, "meta.json")
    if not os.path.exists(path):
        sys.exit(f"no meta.json for episode {ep_slug!r} (expected {path})")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def build_body(meta: dict, title: str, privacy: str, long_url: str | None) -> dict:
    hook = meta.get("hook", "").strip()
    desc = [hook]
    if long_url:
        desc += ["", f"ดูฉบับเต็ม: {long_url}"]
    if meta.get("attribution"):
        desc += ["", meta["attribution"]]
    tags = list(meta.get("tags", []))
    for extra in ("Shorts", "shorts", "เรื่องสั้น", "ข้อคิดชีวิต"):
        if extra not in tags:
            tags.append(extra)
    return {
        "snippet": {
            "title": title[:100],
            "description": "\n".join(desc)[:5000],
            "tags": tags[:15],
            "categoryId": meta.get("youtube_category_id", "27"),
            "defaultLanguage": "th",
        },
        "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False},
    }


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("episode", help="episode slug, e.g. ep02_manthana_phatha")
    ap.add_argument("--file", required=True, help="the vertical .mp4 to upload")
    ap.add_argument("--channel", required=True,
                    help="channel slug from channels.json (picks token + guard)")
    ap.add_argument("--title", help="Short title (default: the episode hook)")
    ap.add_argument("--long-url", help="link to the long-form episode "
                                       "(default: read from receipts)")
    ap.add_argument("--privacy", default="private",
                    choices=["private", "unlisted", "public"])
    ap.add_argument("--base", default=None, help="channel base URL for the receipt")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not os.path.exists(args.file):
        sys.exit(f"no such file: {args.file}")

    ch_cfg = find_channel(args.channel)
    if not ch_cfg:
        sys.exit(f"'{args.channel}' is not in channels.json. Add it first.")
    expected = ch_cfg.get("channel_id")

    meta = load_meta(args.episode)
    long_url = args.long_url or long_form_url(args.episode)
    title = args.title or f"{meta.get('hook', meta.get('title', 'Short'))}"
    if "#Shorts" not in title and "#shorts" not in title:
        title = f"{title} #Shorts"
    body = build_body(meta, title, args.privacy, long_url)

    os.environ["YT_TOKEN_PATH"] = token_path_for(args.channel)

    print(f"short   : {args.file}")
    print(f"channel : {args.channel}  ({ch_cfg.get('name')})"
          + (f"  expect {expected}" if expected else ""))
    print(f"token   : {os.environ['YT_TOKEN_PATH']}")
    print(f"privacy : {args.privacy}")
    print(f"title   : {body['snippet']['title']}")
    print(f"tags    : {', '.join(body['snippet']['tags'][:8])}")
    print(f"long    : {long_url or '(not recorded yet — run the long-form publish first)'}")

    if args.dry_run:
        print("\n--- description that would be posted ---\n")
        print(body["snippet"]["description"])
        print("\ndry run: nothing uploaded")
        return 0

    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from googleapiclient.errors import HttpError
    from yt_auth import load_credentials

    creds = load_credentials(expected)
    yt = build("youtube", "v3", credentials=creds, cache_discovery=False)
    ch = assert_channel(yt, expected, args.channel)
    print(f"  authorised as: {ch['snippet']['title']} ({ch['id']})")

    print("\nuploading Short ...")
    try:
        request = yt.videos().insert(
            part="snippet,status", body=body,
            media_body=MediaFileUpload(args.file, chunksize=8 * 1024 * 1024,
                                       resumable=True))
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"  {int(status.progress() * 100)}%", flush=True)
    except HttpError as exc:
        print(f"upload failed: {exc}", file=sys.stderr)
        return 1

    vid = response["id"]
    url = f"https://youtu.be/{vid}"
    print(f"  uploaded: {url}  status={response['status']['privacyStatus']}")

    if args.base:
        try:
            when = record_receipt(args.base, {
                "episode": args.episode, "slug": args.episode,
                "platform": "youtube-short", "url": url,
                "title": body["snippet"]["title"], "privacy": args.privacy,
                "video_id": vid,
            })
            print(f"reported to the channel at {when}")
        except Exception as exc:
            print(f"upload OK, but the receipt was not recorded: {exc}",
                  file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
