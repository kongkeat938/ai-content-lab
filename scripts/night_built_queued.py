#!/usr/bin/env python3
"""Is the built night release already QUEUED in the publish manifest?

Exit 0 = queued or published (has a video_id); exit 1 = not queued.

The night rail must tell two states apart, and conflating them loses a video:

  * the release exists AND its manifest entry is published -> skip everything
  * the release exists BUT the manifest push was lost (a build finished, then
    'git push' lost a race) -> the hand-off must still run

Measured 2026-11-09: a 120-min build passed its gates, the release was created,
and the manifest push failed -- so re-running saw "release exists" and skipped the
hand-off, leaving the finished video stranded on a Release forever.

    python3 scripts/night_built_queued.py night-abc123 [manifest.json]
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEFAULT_MANIFEST = os.path.join(ROOT, "content", "ch2_publish.json")


def is_queued(tag: str, manifest: str = DEFAULT_MANIFEST) -> bool:
    try:
        with open(manifest, encoding="utf-8") as fh:
            man = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return False
    hit = next((v for v in man.get("videos", [])
                if tag in (v.get("video_url", "") + v.get("audio_url", ""))), None)
    return bool(hit and hit.get("video_id"))


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: night_built_queued.py <release-tag> [manifest.json]")
        return 1
    manifest = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_MANIFEST
    return 0 if is_queued(sys.argv[1], manifest) else 1


if __name__ == "__main__":
    sys.exit(main())
