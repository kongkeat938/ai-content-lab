#!/usr/bin/env python3
"""The metadata restore rebuilds the right description + tags, and only when needed.

`videos.update` erased description+tags (measured 2026-11-14), so `restore_metadata.py`
puts them back from the manifests. This guard pins the two things that make it safe:

  1. The Shorts description is byte-identical to what `publish_shorts` uploaded
     (hook + lines + cta + tail [+ music credit]) -- not an approximation.
  2. `needs_restore` fires on a missing description OR missing tags, and does not fire
     on a healthy snippet (so an idempotent re-run writes nothing).

It can FAIL: change the description formula and (1) goes red; make `needs_restore`
always/never true and (2) goes red.

    python3 scripts/test_restore_metadata.py
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import publish_shorts as ps  # noqa: E402
import restore_metadata as rm  # noqa: E402


def main() -> int:
    for ch in ps.CHANNELS:
        spec = ps.CHANNELS[ch]
        scripts = {x["id"]: x for x in json.load(open(spec["scripts"], encoding="utf-8"))}
        man = json.load(open(spec["manifest"], encoding="utf-8"))["shorts"]
        targets = rm.short_targets(ch)
        checked = 0
        for key, e in man.items():
            vid, s = e.get("video_id"), scripts.get(key)
            if not vid or not s or vid not in targets:
                continue
            want = (f"{s['hook']}\n\n" + "\n".join(s["lines"]) + f"\n\n{s['cta']}"
                    + spec["tail"] + (ps.MUSIC_CREDIT if spec.get("music_dir") else ""))[:5000]
            got = targets[vid]["description"]
            if got != want:
                print(f"FAIL: {ch}/{key} ({vid}) description differs from publish_shorts")
                print(f"  want {want[:80]!r}...")
                print(f"  got  {got[:80]!r}...")
                return 1
            if targets[vid]["tags"] != spec["tags"]:
                print(f"FAIL: {ch}/{key} tags != channel spec tags")
                return 1
            checked += 1
        print(f"OK: {ch}: {checked} Shorts descriptions match publish_shorts exactly")

    # needs_restore: fires on either loss, quiet on a healthy snippet.
    cases = [
        ({"description": "d", "tags": ["t"]}, False, "healthy"),
        ({"description": "", "tags": ["t"]}, True, "no description"),
        ({"description": "   ", "tags": ["t"]}, True, "blank description"),
        ({"description": "d"}, True, "no tags key"),
        ({"description": "d", "tags": []}, True, "empty tags"),
    ]
    for sn, want, label in cases:
        got = rm.needs_restore(sn)
        if got != want:
            print(f"FAIL: needs_restore({label}) = {got}, expected {want}")
            return 1
    print("OK: needs_restore fires on missing description or tags, quiet when healthy")
    return 0


if __name__ == "__main__":
    sys.exit(main())
