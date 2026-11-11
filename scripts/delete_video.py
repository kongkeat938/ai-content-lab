#!/usr/bin/env python3
"""Delete a YouTube video from one of our channels -- duplicates and bad cuts.

K's rule (2026-10-24): "อันไหนซ้ำ อันไหนไม่มีคุณภาพลบออกจากช่อง". The rail has
publish but no unpublish; when a build ships wrong (e.g. a double-loop that made
a 30-minute talk run 57 minutes) the only way to replace it is to remove it, and
publish_batch will not re-upload while a video with the same title is live.

A delete is irreversible, so this refuses to guess:
  * a video id is REQUIRED; it never scans and deletes on its own
  * --dry-run is the default; --yes must be passed to actually delete
  * the video's full metadata is written to a backup first
  * an id above --max-views (default 5) is skipped unless --force

It runs in CI (see .github/workflows/delete-video.yml) because the pod IP is
throttled by the Data API; DELETE itself is not blocked by the sandbox proxy.

    python3 scripts/delete_video.py --slug dharma --video HkbSguA53ro          # plan
    python3 scripts/delete_video.py --slug dharma --video HkbSguA53ro --yes    # delete
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import publish_batch  # noqa: E402

API = "https://www.googleapis.com/youtube/v3"
BACKUP_DIR = os.path.join(ROOT, "content", "deleted")


def get(token: str, vid: str) -> dict | None:
    url = (f"{API}/videos?part=snippet,status,statistics,contentDetails"
           f"&id={vid}")
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    for _ in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as f:
                items = json.load(f).get("items", [])
            return items[0] if items else None
        except urllib.error.HTTPError as exc:
            if exc.code in (403, 429, 500, 503):
                time.sleep(4)
                continue
            raise
    return None


def delete(token: str, vid: str) -> tuple[int, str]:
    """DELETE with no body -- a serialised None makes Google answer 400."""
    req = urllib.request.Request(f"{API}/videos?id={vid}",
                                 headers={"Authorization": f"Bearer {token}"},
                                 method="DELETE")
    try:
        with urllib.request.urlopen(req, timeout=120) as f:
            return f.status, f.read().decode(errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode(errors="replace")


def set_private(token: str, vid: str) -> tuple[int, str]:
    """Set a video private -- the reversible alternative to a delete.

    A delete cannot be undone, and the guarded delete refuses a video with views
    (`--max-views`), which is why remove-bad-cut looped 37 times on 2026-11-11.
    Private removes the same Reused-Content exposure (the video is no longer
    public) while staying reversible.
    """
    body = json.dumps({"id": vid, "status": {"privacyStatus": "private"}}).encode()
    req = urllib.request.Request(f"{API}/videos?part=status", data=body,
                                 headers={"Authorization": f"Bearer {token}",
                                          "Content-Type": "application/json"},
                                 method="PUT")
    try:
        with urllib.request.urlopen(req, timeout=120) as f:
            return f.status, f.read().decode(errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode(errors="replace")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", default="dharma", help="channel slug (dharma, genx, ...)")
    ap.add_argument("--video", required=True, help="the video id to delete")
    ap.add_argument("--yes", action="store_true", help="actually delete")
    ap.add_argument("--unpublish", action="store_true",
                    help="set the video private instead of deleting (reversible)")
    ap.add_argument("--force", action="store_true", help="allow deleting a video with views")
    ap.add_argument("--max-views", type=int, default=5)
    a = ap.parse_args()

    token = publish_batch.access_token(a.slug)
    row = get(token, a.video)
    if not row:
        print(f"{a.video}: NOT FOUND on {a.slug} (already deleted, or a read quota 403)")
        return 1

    os.makedirs(BACKUP_DIR, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    backup = os.path.join(BACKUP_DIR, f"{a.slug}-{a.video}-{stamp}.json")
    with open(backup, "w", encoding="utf-8") as fh:
        json.dump(row, fh, ensure_ascii=False, indent=1)

    views = int(row["statistics"].get("viewCount", 0))
    print(f"{row['id']}  {row['status']['privacyStatus']}  "
          f"{row['contentDetails']['duration']}  views={views}")
    print(f"  title: {row['snippet']['title'][:70]}")
    print(f"  backup -> {os.path.relpath(backup, ROOT)}")

    if a.unpublish:
        # Reversible path: private removes the Reused-Content exposure without the
        # irreversibility of a delete, and it is not gated on --max-views.
        if not a.yes:
            print("dry run -- nothing changed (pass --yes)")
            return 0
        if row["status"]["privacyStatus"] == "private":
            print("already private; writing the marker so the rail stops retrying")
            _mark_done(a.video)
            return 0
        st, body = set_private(token, a.video)
        print(f"PRIVATE {a.video} -> HTTP {st}" + ("" if st in (200, 204) else f"  {body[:200]}"))
        ok = st in (200, 204)
        if ok:
            _mark_done(a.video)
        return 0 if ok else 1

    if views > a.max_views and not a.force:
        print(f"SKIP: {views} views > --max-views {a.max_views} (pass --force to override)")
        return 1
    if not a.yes:
        print("dry run -- nothing deleted (pass --yes)")
        return 0

    st, body = delete(token, a.video)
    print(f"DELETE {a.video} -> HTTP {st}" + ("" if st in (200, 204) else f"  {body[:200]}"))
    ok = st in (200, 204)
    if ok:
        _mark_done(a.video)
    return 0 if ok else 1


def _mark_done(vid: str) -> None:
    """Write the success marker, so the rail and the foreman stop retrying.

    Without it a spent-quota or skip-rule retry loops forever -- the exact failure
    that ran ~37 times on 2026-11-11.
    """
    with open(os.path.join(BACKUP_DIR, f"{vid}.done"), "w", encoding="utf-8") as fh:
        fh.write(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()) + "\n")


if __name__ == "__main__":
    sys.exit(main())
