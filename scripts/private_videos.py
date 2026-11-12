#!/usr/bin/env python3
"""List and remove the non-public videos on a channel.

Two different things end up non-public and they must not be treated alike:

  * a SCHEDULED release -- `private` with a future `status.publishAt`. YouTube
    flips it public at the slot on its own clock (that is the whole point of
    `publish_batch --publish-at`). Deleting one would throw away a queued video.
  * a PARKED clip -- `private` with no future `publishAt` (a rogue upload we hid,
    a paused bad cut, or something inserted outside the rails). This is the set
    that should go.

`--list` (default) prints every non-public video and its kind, read-only.
`--delete` removes the parked ones (never a scheduled release), writing each
video's full metadata to content/deleted/ first, the same backup `delete_video`
keeps. It needs `--yes`.

Runs in CI (.github/workflows/private-videos.yml): the pod IP is throttled by the
Data API, CI is not.

    python3 scripts/private_videos.py --slug dharma                 # list
    python3 scripts/private_videos.py --slug dharma --delete --yes  # remove parked
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import publish_batch  # noqa: E402

API = "https://www.googleapis.com/youtube/v3"
BACKUP_DIR = os.path.join(ROOT, "content", "deleted")


def _get(token: str, url: str) -> dict:
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    last = ""
    for _ in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as f:
                return json.load(f)
        except urllib.error.HTTPError as exc:
            last = f"HTTP {exc.code}: {exc.read().decode(errors='replace')[:200]}"
            if exc.code in (403, 429, 500, 503):
                time.sleep(4)
                continue
            break
    raise SystemExit(f"gave up on {url}\n  {last}")


def uploads_playlist(token: str) -> str:
    ch = _get(token, f"{API}/channels?part=contentDetails&mine=true")
    items = ch.get("items") or []
    if not items:
        raise SystemExit("channels.list returned nothing (wrong token or spent quota)")
    return items[0]["contentDetails"]["relatedPlaylists"]["uploads"]


def all_upload_ids(token: str, playlist: str) -> list[str]:
    ids, tok = [], None
    while True:
        url = (f"{API}/playlistItems?part=contentDetails&playlistId={playlist}"
               f"&maxResults=50" + (f"&pageToken={tok}" if tok else ""))
        r = _get(token, url)
        ids += [i["contentDetails"]["videoId"] for i in r.get("items", [])]
        tok = r.get("nextPageToken")
        if not tok:
            return ids


def videos(token: str, ids: list[str]) -> list[dict]:
    out = []
    for i in range(0, len(ids), 50):
        chunk = ids[i:i + 50]
        r = _get(token, f"{API}/videos?part=snippet,status,statistics&id={','.join(chunk)}")
        out += r.get("items", [])
    return out


def kind(v: dict) -> str:
    st = v["status"]
    if st["privacyStatus"] == "public":
        return "public"
    publish_at = st.get("publishAt")
    if publish_at:
        try:
            when = datetime.fromisoformat(publish_at.replace("Z", "+00:00"))
            if when > datetime.now(timezone.utc):
                return "scheduled"
        except ValueError:
            pass
    return "parked"


def parked_only(rows: list[dict]) -> list[dict]:
    """The videos a delete should remove: `private` and NOT a future schedule.

    Unlisted is deliberately excluded: the owner asked to remove what shows as
    "private" (`ส่วนตัว`), and unlisted clips (`ไม่เป็นสาธารณะ`) may still be live
    links someone shared -- one carries >1000 views. Pass --include-unlisted to
    widen the set on purpose.
    """
    return [v for v in rows if kind(v) == "parked" and v["status"]["privacyStatus"] == "private"]


def delete(token: str, vid: str) -> tuple[int, str]:
    req = urllib.request.Request(f"{API}/videos?id={vid}",
                                 headers={"Authorization": f"Bearer {token}"},
                                 method="DELETE")
    try:
        with urllib.request.urlopen(req, timeout=120) as f:
            return f.status, f.read().decode(errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode(errors="replace")


def backup(v: dict) -> str:
    os.makedirs(BACKUP_DIR, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    path = os.path.join(BACKUP_DIR, f"{v['id']}-{stamp}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(v, fh, ensure_ascii=False, indent=1)
    return path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", action="append", required=True,
                    help="channel slug; repeat for more than one")
    ap.add_argument("--delete", action="store_true", help="delete the PARKED videos")
    ap.add_argument("--include-unlisted", action="store_true",
                    help="also delete unlisted clips (default: private only)")
    ap.add_argument("--yes", action="store_true", help="confirm a delete")
    a = ap.parse_args()

    report = {}
    rc = 0
    for slug in a.slug:
        print("=" * 70)
        print(slug)
        token = publish_batch.access_token(slug)
        try:
            pl = uploads_playlist(token)
            rows = videos(token, all_upload_ids(token, pl))
        except SystemExit as exc:
            print(f"  cannot read {slug}: {exc}")
            rc = 1
            continue
        nonpub = [(kind(v), v) for v in rows if v["status"]["privacyStatus"] != "public"]
        print(f"  uploads: {len(rows)}   non-public: {len(nonpub)}")
        report[slug] = []
        for k, v in sorted(nonpub, key=lambda t: t[0]):
            s = v["snippet"]
            row = {"id": v["id"], "kind": k,
                   "privacy": v["status"]["privacyStatus"],
                   "publishAt": v["status"].get("publishAt"),
                   "publishedAt": s.get("publishedAt"),
                   "views": int(v.get("statistics", {}).get("viewCount", 0)),
                   "title": s["title"]}
            report[slug].append(row)
            print(f"    {k:9} {v['id']}  {row['privacy']:7} views={row['views']:>6}  "
                  f"{row['publishedAt']}  {s['title'][:52]}")
        if a.delete:
            doomed = [v for v in rows
                      if kind(v) == "parked"
                      and (a.include_unlisted or v["status"]["privacyStatus"] == "private")]
            if not a.yes:
                print(f"  dry run: would delete {len(doomed)} parked (pass --yes)")
                continue
            for v in doomed:
                b = backup(v)
                st, body = delete(token, v["id"])
                print(f"    DELETE {v['id']} -> HTTP {st}  (backup {os.path.relpath(b, ROOT)})"
                      + ("" if st in (200, 204) else f"  {body[:160]}"))
                if st not in (200, 204):
                    rc = 1

    out = os.path.join(ROOT, "work", "private_videos.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=1)
    print(f"\nreport -> {os.path.relpath(out, ROOT)}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
