#!/usr/bin/env python3
"""Guard the learning loop's titles against a spent Data API quota.

studio_ai and video_review read the YouTube Analytics API (its own quota) and then
fetch titles from the Data API's videos.list. That second call 403s whenever the
shared Data API quota is spent -- which is most days here -- and the code used to
fall back to the literal "(title unavailable)" for every winner. The panel then
judged a channel it could not see and answered with generic filler subjects, which
gen_short_scripts.py picked up as the next content to make (measured 2026-11-09:
all three channels wrote "(title unavailable)" for every winner).

The fix resolves titles from the committed manifests instead. This test locks that
in: with the live titles absent (the quota-spent case), every video the manifest
knows must still come back with its real title, not the placeholder.

    python3 scripts/test_learning_titles.py     # exit 0 = titles survive a dead API
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import studio_ai  # noqa: E402


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def main() -> int:
    # Keep the test offline: stub the oEmbed last resort. (One dedicated case below
    # exercises the real code path by controlling the stub's return value.)
    real_oembed = studio_ai.oembed_titles
    studio_ai.oembed_titles = lambda ids, cap=50: {}

    channels = {"ch1": "content/ch1_shorts.json",
                "ch2": "content/ch2_shorts.json",
                "ch4": "content/ch4_shorts.json"}

    for channel, rel in channels.items():
        path = os.path.join(ROOT, rel)
        if not os.path.exists(path):
            fail(f"{rel} is missing; the {channel} generator has no title source")

        manifest = json.load(open(path, encoding="utf-8"))["shorts"]
        ids = {r["video_id"] for r in manifest.values() if r.get("video_id")}
        if not ids:
            fail(f"{rel} has no uploaded video_id; nothing to title")

        # The quota-spent path: no live titles at all.
        titles = studio_ai.manifest_titles(channel)
        missing = ids - set(titles)
        if missing:
            fail(f"{channel}: {len(missing)} uploaded video(s) have no committed "
                 f"title (e.g. {sorted(missing)[:3]}); a spent quota would show "
                 "'(title unavailable)' for them")

        # fill_titles must prefer the live title, fall back to the manifest, and
        # never leave a known video as the placeholder.
        rows = [{"video": vid} for vid in sorted(ids)]
        studio_ai.fill_titles(channel, rows, {})
        bad = [r for r in rows if r["title"] == "(title unavailable)"]
        if bad:
            fail(f"{channel}: fill_titles left {len(bad)} known video(s) untitled")

        # A live title wins over the manifest copy.
        sample = sorted(ids)[0]
        row = {"video": sample}
        studio_ai.fill_titles(channel, [row], {sample: "LIVE TITLE"})
        if row["title"] != "LIVE TITLE":
            fail(f"{channel}: a live title did not override the manifest copy")

        # An id nobody knows still degrades gracefully rather than crashing.
        row = {"video": "not-a-real-id"}
        studio_ai.fill_titles(channel, [row], {})
        if row["title"] != "(title unavailable)":
            fail(f"{channel}: an unknown video id should read the placeholder")

        print(f"OK: {channel} — {len(ids)} videos keep real titles with no Data API")

    # oEmbed is the last resort for an id neither the API nor the manifest knows:
    # with the live titles absent and the id uncommitted, fill_titles must reach
    # for it. Controlled stub so the assertion is deterministic and offline.
    studio_ai.oembed_titles = lambda ids, cap=50: {"orphanVid": "title from oEmbed"}
    row = {"video": "orphanVid"}
    studio_ai.fill_titles("ch2", [row], {})
    if row["title"] != "title from oEmbed":
        fail("fill_titles did not fall back to oEmbed for an unknown id")
    studio_ai.oembed_titles = real_oembed
    print("OK: an id absent from both the API and the manifest is recovered via oEmbed")

    # A title seen from the live API must be remembered, so a later quota day
    # cannot lose it. Proven with a real write/read against a throwaway channel
    # name (never a real one, so the committed caches are untouched).
    probe = "__test_remember__"
    path = os.path.join(ROOT, "content", "titles", f"{probe}.json")
    try:
        studio_ai.remember_titles(probe, {"vid1": "remembered title"})
        studio_ai.remember_titles(probe, {"vid2": "second title"})  # must merge, not replace
        got = studio_ai.manifest_titles(probe)
        if got.get("vid1") != "remembered title" or got.get("vid2") != "second title":
            fail(f"remember_titles did not persist/merge correctly: {got}")
        print("OK: a live-resolved title is cached and survives a later quota day")
    finally:
        if os.path.exists(path):
            os.remove(path)

    print("OK: the learning loop titles survive a spent Data API quota")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
