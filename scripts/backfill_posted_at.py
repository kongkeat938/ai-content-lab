#!/usr/bin/env python3
"""Backfill `posted_at` on the Shorts manifests from git history.

`publish_shorts.py` records `posted_at` only for Shorts uploaded after
2026-11-09, so the clips already live have no clock and `pace.gate` cannot space
them. The manifest is committed the moment a Short gets its id, so the commit
that first introduced a video_id is the post time, to the minute.

One-time, and idempotent: an entry that already has `posted_at` is left alone.
Needs full history (`git fetch --unshallow`) -- CI checks out one commit, so run
this locally and commit the result.

    python3 scripts/backfill_posted_at.py            # write
    python3 scripts/backfill_posted_at.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

MANIFESTS = {
    "dharma": "content/ch2_shorts.json",
    "genx": "content/ch1_shorts.json",
    "kongkeat": "content/ch4_shorts.json",
}


def first_seen(rel: str) -> dict[str, str]:
    """video_id -> the ISO commit time that first added it to the manifest."""
    # Walk the history oldest-first; the first commit whose blob contains the id
    # is the post time. -G limits to commits that changed the id count, so this is
    # a handful of commits, not the whole log.
    out = subprocess.run(["git", "-C", ROOT, "log", "--reverse",
                          "--format=%H\t%cI", "--", rel],
                         capture_output=True, text=True, check=True).stdout
    seen: dict[str, str] = {}
    for line in out.splitlines():
        if "\t" not in line:
            continue
        sha, ts = line.split("\t", 1)
        blob = subprocess.run(["git", "-C", ROOT, "show", f"{sha}:{rel}"],
                              capture_output=True, text=True).stdout
        try:
            man = json.loads(blob)
        except ValueError:
            continue
        for sid, entry in man.get("shorts", {}).items():
            vid = entry.get("video_id")
            if vid and vid not in seen:
                seen[vid] = ts
    return seen


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    total = 0
    for slug, rel in MANIFESTS.items():
        path = os.path.join(ROOT, rel)
        with open(path, encoding="utf-8") as fh:
            man = json.load(fh)
        stamps = first_seen(rel)
        changed = 0
        for sid, entry in man.get("shorts", {}).items():
            if entry.get("posted_at") or not entry.get("video_id"):
                continue
            ts = stamps.get(entry["video_id"])
            if not ts:
                continue
            entry["posted_at"] = ts
            changed += 1
        if changed and not args.dry_run:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(man, fh, ensure_ascii=False, indent=2)
                fh.write("\n")
        print(f"{slug}: stamped {changed} entries")
        total += changed
    print(f"{'would stamp' if args.dry_run else 'stamped'} {total} Shorts total")
    return 0


if __name__ == "__main__":
    sys.exit(main())
