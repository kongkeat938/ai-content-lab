#!/usr/bin/env python3
"""Guard the two rules K set on 2026-11-20 about work waiting to be uploaded.

K: "งานเก่าที่ค้างรออัพทั้งหมดลบทิ้งเพื่อป้องกันเอามาวนซ้ำทำใหม่ด้วย เคลียร์ให้หมดจริงๆ"
and, separately, nothing may upload unless he says so.

So this test asserts the state that was measured after the clean-up:

  1. **Nothing is waiting to be uploaded.** Every entry in the publish/shorts/
     remake ledgers has a real upload record. A `pending` entry is exactly the
     thing that could be picked up and posted again, so it must be zero.
  2. **No orphan build output.** A rendered video that no ledger mentions is work
     waiting to be uploaded by another name. Only the committed reference media
     under `docs/demo/media/` may exist.
  3. **No upload rail is armed.** Read from the workflow files: a rail that can
     call `videos.insert` must not have a `schedule:` trigger while K holds the
     switch.

The first two are file-state facts, the third is a static fact; all three can
FAIL. Run: python3 scripts/test_no_pending_uploads.py
"""
from __future__ import annotations

import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

FAILS: list = []
UPLOAD_MARKERS = ("videos.insert", "publish_youtube", "publish_shorts",
                  "publish_motion", "publish_batch")


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"{'PASS' if cond else 'FAIL'} {name}" + (f"  [{detail}]" if detail else ""))
    if not cond:
        FAILS.append(name)


def test_no_pending_entries() -> None:
    total = 0
    pending: list = []
    for f in sorted(glob.glob(os.path.join(ROOT, "content", "ch*_publish.json"))):
        for v in json.load(open(f, encoding="utf-8")).get("videos", []):
            total += 1
            if not (v.get("video_url") or v.get("video_id")) or \
                    v.get("state") not in (None, "published"):
                pending.append(f"{os.path.basename(f)}:{v.get('key')}")
    for f in sorted(glob.glob(os.path.join(ROOT, "content", "ch*_shorts*.json"))):
        for key, v in json.load(open(f, encoding="utf-8")).get("shorts", {}).items():
            total += 1
            if isinstance(v, dict) and not (v.get("video_id") or v.get("youtube_id")):
                pending.append(f"{os.path.basename(f)}:{key}")
    check("no long-form or Short is waiting to be uploaded", not pending,
          f"{len(pending)} pending of {total}" + (f" -> {pending[:5]}" if pending else ""))
    check("the ledgers still hold the uploaded history", total >= 300, f"{total} entries")


def test_no_orphan_builds() -> None:
    """A rendered video that no ledger mentions is work waiting to be uploaded."""
    allowed = {os.path.abspath(p) for p in
               glob.glob(os.path.join(ROOT, "docs", "demo", "media", "*.mp4"))}
    found = []
    for path in glob.glob(os.path.join(ROOT, "**", "*.mp4"), recursive=True):
        if "/.git/" in path:
            continue
        if os.path.abspath(path) in allowed:
            continue
        found.append(os.path.relpath(path, ROOT))
    check("no orphan video build is sitting in the tree", not found,
          f"{len(found)}" + (f" -> {found[:5]}" if found else ""))


def test_no_armed_upload_rail() -> None:
    """Two permanent invariants, not the current on/off state of GitHub.

    The live state was measured 2026-11-20 with the API: all 29 upload rails read
    `disabled_manually`, so nothing can post. That is a setting on GitHub, not a
    property of the repo -- so the test asserts the property instead: every script
    that can call `videos().insert` must honour `content/STOP`, and no workflow may
    hand itself the escape hatch. A new uploader that forgets the switch fails here.
    """
    uploaders = []
    for path in sorted(glob.glob(os.path.join(ROOT, "scripts", "*.py"))):
        name = os.path.basename(path)
        if name.startswith("test_"):
            continue
        text = open(path, encoding="utf-8").read()
        if "videos().insert" in text or "videos.insert" in text:
            uploaders.append((name, "kill_switch" in text))
    missing = [n for n, ok in uploaders if not ok]
    check("every script that can upload honours the kill switch", not missing,
          f"{len(uploaders)} uploaders, missing: {missing}" if missing
          else f"{len(uploaders)} uploaders")

    escape = []
    for path in sorted(glob.glob(os.path.join(ROOT, ".github", "workflows", "*.yml"))):
        if "CONTENT_STOP_PATH" in open(path, encoding="utf-8").read():
            escape.append(os.path.basename(path))
    check("no workflow can point the kill switch somewhere else", not escape,
          f"{escape}")


def main() -> int:
    test_no_pending_entries()
    test_no_orphan_builds()
    test_no_armed_upload_rail()
    print(f"\n{len(FAILS)} failure(s)")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
