#!/usr/bin/env python3
"""Guard the free real-b-roll client (fetch_broll.py).

The reference is real live-action footage, and a free generative model cannot make
a believable human (measured 2026-11-17), so the standard uses REAL stock video
from Coverr. This test locks the selection rules and, when the network is up,
proves the client really returns a usable 1080p mp4:

  * the filter rejects premium / vertical / AI-generated / too-short / too-long /
    low-res clips -- a guard that could not fail proves nothing, so each rule is
    asserted against a synthetic hit that must be dropped;
  * a real search+download yields a >=720p landscape video, or the test SKIPS
    (a dead network must not fail an unrelated CI run).

    python3 scripts/test_broll.py    # exit 0 = the rules hold
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fetch_broll as fb  # noqa: E402


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def base(**kw) -> dict:
    h = {"base_filename": "coverr-x-1", "max_height": 1080, "duration": "10.0",
         "is_premium": False, "is_vertical": False, "is_ai_generated": False,
         "id": "x", "title": "t", "slug": "s"}
    h.update(kw)
    return h


def main() -> int:
    # Every rejection rule must actually reject.
    cases = {
        "premium": base(is_premium=True),
        "vertical": base(is_vertical=True),
        "ai-generated": base(is_ai_generated=True),
        "too short": base(duration="2.0"),
        "too long": base(duration="120.0"),
        "low-res": base(max_height=480),
        "no filename": base(base_filename=""),
        "no duration": base(duration=""),
    }
    for name, h in cases.items():
        if fb.usable(h):
            fail(f"usable() accepted a {name} clip")
    if not fb.usable(base()):
        fail("usable() rejected a perfectly good clip")

    # allow_ai flips the AI rule only.
    if not fb.usable(base(is_ai_generated=True), allow_ai=True):
        fail("allow_ai did not permit an AI clip")
    if fb.usable(base(is_premium=True), allow_ai=True):
        fail("allow_ai wrongly permitted a premium clip")

    # The URL is the CDN pattern the download relies on.
    if fb.video_url(base(), "1080p") != "https://cdn.coverr.co/videos/coverr-x-1/1080p.mp4":
        fail("video_url built the wrong CDN path")

    # Live check: a real query downloads a real, landscape, >=720p video.
    hits = fb.search("ocean waves")
    if not hits:
        print("SKIP: Coverr API unreachable (offline) -- selection rules still hold")
        return 0
    hit = fb.pick("ocean waves")
    if not hit:
        fail("no usable clip for a common query while the API is up")
    if not shutil.which("ffprobe"):
        print("SKIP: ffprobe missing -- could not verify the download")
        return 0
    tmp = tempfile.mkdtemp(prefix="broll_guard_")
    out = os.path.join(tmp, "c.mp4")
    if not fb.download(hit, out):
        fail("download() failed for a clip it selected")
    info = __import__("make_qa_video").probe(out)
    v = next((s for s in info.get("streams", []) if s["codec_type"] == "video"), {})
    if (v.get("width") or 0) <= (v.get("height") or 0):
        fail(f"selected clip is not landscape ({v.get('width')}x{v.get('height')})")
    if (v.get("height") or 0) < 720:
        fail(f"selected clip is only {v.get('height')}p")
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"PASS: b-roll rules hold; live pick = {hit.get('title','')[:40]!r} "
          f"({v.get('width')}x{v.get('height')})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
