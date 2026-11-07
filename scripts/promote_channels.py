#!/usr/bin/env python3
"""Close the two promotion gaps the audit measured, safely.

Measured on the live channels 2026-11-02:
  * 33 of 40 Shorts name a channel in words but link no video, so the discovery
    engine cannot funnel anyone to the long-form.
  * 64 of 64 long-form videos link neither a sibling channel nor a playlist.
Every audience therefore arrives and finds no next step.

This writes ONE short block into a description when it is missing: the sibling
channel and the channel's own home. It is idempotent (it skips a video that
already has the block), additive (it never rewrites existing text), and dry-run
by default.

    python3 scripts/promote_channels.py                 # show what it would do
    python3 scripts/promote_channels.py --apply         # write the blocks
    python3 scripts/promote_channels.py --slug dharma --apply

Quota: videos.update costs 50 units; the 10,000-unit day allows 200 updates, and
the tool only touches videos that are missing the block.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import yt_auth  # noqa: E402

# The three channels promote each other, so each audience can find the other two.
SIBLING = {
    "genx": ("Farmmer — ธรรมะก่อนนอน", "https://www.youtube.com/@farmmer-n9t"),
    "dharma": ("เรื่องเล่าอบอุ่นใจ — ความทรงจำครอบครัว",
               "https://www.youtube.com/channel/UC7gCIu4G_7QCEJ8hJ-34zoQ"),
    "kongkeat-story": ("ตาต้า GenX — ปรัชญาชีวิต", "https://www.youtube.com/@tatagenxgeny"),
}
MARKER = "— ช่องพี่น้อง —"


def block_for(slug: str, handle: str) -> str:
    name, url = SIBLING[slug]
    home = f"https://www.youtube.com/{handle}"
    return (f"\n\n{MARKER}\n{name}\n{url}\n\n"
            f"รวมทุกตอนไว้ในช่องเดียว: {home}")


def fetch_videos(yt, limit: int = 200) -> list:
    up = (yt.channels().list(part="contentDetails", mine=True).execute()
          ["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"])
    ids, token = [], None
    while len(ids) < limit:
        r = yt.playlistItems().list(part="contentDetails", playlistId=up,
                                    maxResults=50, pageToken=token).execute()
        ids += [i["contentDetails"]["videoId"] for i in r.get("items", [])]
        token = r.get("nextPageToken")
        if not token:
            break
    out = []
    for i in range(0, len(ids), 50):
        out += yt.videos().list(part="snippet", id=",".join(ids[i:i + 50])).execute()["items"]
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug")
    ap.add_argument("--apply", action="store_true",
                    help="write the blocks (default: dry run)")
    a = ap.parse_args()

    reg = json.load(open(os.path.join(os.path.dirname(HERE), "channels.json"),
                         encoding="utf-8"))
    chans = [c for c in reg["channels"]
             if "CANCELLED" not in (c.get("status") or "")
             and (not a.slug or c["slug"] == a.slug)]
    summary = {}
    for c in chans:
        slug = c["slug"]
        creds = yt_auth.load_credentials(expected_channel=c["channel_id"])
        from googleapiclient.discovery import build
        yt = build("youtube", "v3", credentials=creds, cache_discovery=False)
        got = (yt.channels().list(part="id", mine=True).execute()
               .get("items") or [{}])[0].get("id")
        if got != c["channel_id"]:
            print(f"  !! {slug}: token answered as {got}; skipped")
            continue
        block = block_for(slug, c["handle"])
        vids = fetch_videos(yt)
        missing = [v for v in vids
                   if MARKER not in (v["snippet"].get("description") or "")]
        print(f"== {slug}: {len(vids)} videos, {len(missing)} missing the promo block")
        if not a.apply:
            for v in missing[:3]:
                print(f"     would add to {v['id']}: {v['snippet']['title'][:45]}")
            if len(missing) > 3:
                print(f"     ... and {len(missing) - 3} more")
        else:
            from googleapiclient.errors import HttpError
            done = skipped_long = 0
            failed = []
            for v in missing:
                sn = v["snippet"]
                desc = sn.get("description") or ""
                # YouTube rejects a description over 5000 characters, and one
                # video already carried 4900, so a blind append fails the whole
                # run. Skip what cannot fit rather than truncate someone's credits.
                if len(desc) + len(block) > 4900:
                    skipped_long += 1
                    continue
                body = {
                    "id": v["id"],
                    "snippet": {
                        "title": sn["title"],
                        "description": desc + block,
                        "categoryId": sn.get("categoryId", "27"),
                        "tags": sn.get("tags", []),
                        "defaultLanguage": sn.get("defaultLanguage", "th"),
                        "defaultAudioLanguage": sn.get("defaultAudioLanguage", "th"),
                    },
                }
                try:
                    yt.videos().update(part="snippet", body=body).execute()
                    done += 1
                except HttpError as e:
                    failed.append((v["id"], str(e)[:120]))
            print(f"     wrote {done} blocks, skipped {skipped_long} (too long), "
                  f"failed {len(failed)}")
            for vid, err in failed:
                print(f"       FAIL {vid}: {err}")
        summary[slug] = {"videos": len(vids), "missing": len(missing),
                         "applied": bool(a.apply)}
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
