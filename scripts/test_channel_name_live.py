#!/usr/bin/env python3
"""Guard: the repo's channel-name target must match the LIVE channel name.

Measured 2026-11-17: K renamed ch4 in Studio to "PCSEV" (handle @PCSEV), but
`set_channel_name.TARGET['kongkeat-story']['title']` still held the retired genre
name "เกร็ดความรู้รอบตัว". The daily rails (channel-branding, ch4-realign) run
`set_channel_name.py --apply`, which PUTs `localizations.th_TH.title` = the target --
so a stale target silently rewrites the channel name back, undoing K's rename for the
Thai audience the channel serves. A committed doc is just another claim; the live
channel is the source of truth, so this guard reads the live name (quota-free: the
channel RSS feed) and FAILS when it disagrees with the repo target.

It sweeps the set from `TARGET` (never hardcodes it) and maps each slug to its
channel id through `channels.json`. A dead network SKIPs a channel (a flaky feed must
not fail an unrelated CI run) -- the same rule as `test_broll.py`.

    python3 scripts/test_channel_name_live.py
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = Path(HERE).parent
sys.path.insert(0, HERE)

import set_channel_name as scn  # noqa: E402

RSS = "https://www.youtube.com/feeds/videos.xml?channel_id="


def live_title(channel_id: str) -> str | None:
    """The channel's live name from its RSS feed; None if the feed is unreachable."""
    req = urllib.request.Request(RSS + channel_id, headers={"User-Agent": "Mozilla/5.0"})
    try:
        xml = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "replace")
    except (urllib.error.URLError, OSError, TimeoutError):
        return None
    start = xml.find("<title>")
    end = xml.find("</title>", start)
    return xml[start + 7:end] if start != -1 and end != -1 else None


def main() -> int:
    channels = json.loads((ROOT / "channels.json").read_text(encoding="utf-8"))["channels"]
    by_slug = {c["slug"]: c for c in channels}

    fails, skipped = [], []
    for slug, t in scn.TARGET.items():
        ch = by_slug.get(slug)
        if not ch:
            fails.append(f"{slug}: no channel_id in channels.json")
            continue
        got = live_title(ch["channel_id"])
        if got is None:
            skipped.append(slug)
            print(f"SKIP {slug}: RSS unreachable (offline) -- cannot read the live name")
            continue
        ok = got == t["title"]
        print(f"{'ok ' if ok else 'BAD'} {slug}: live={got!r} target={t['title']!r}")
        if not ok:
            fails.append(f"{slug}: live name {got!r} != repo target {t['title']!r} -- "
                         f"the rail would rewrite the live name back to the stale target")

    if fails:
        for f in fails:
            print(f"FAIL: {f}")
        return 1
    print(f"OK: every repo name target matches the live channel name "
          f"({len(scn.TARGET) - len(skipped)} checked, {len(skipped)} skipped offline)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
