#!/usr/bin/env python3
"""Guard the ch4 CTA experiment (2026-11-09).

Measured: kongkeat (ch4) watched to the end (59.5% avg, like genx's 69.5%) but
converted 1.79 subscribers per 1k views against genx's 5.38, with 0 shares and 0
comments. The subscribe ask sat at the tail of every clip, after the viewer had
already swiped. A five-advisor panel put the fix at "speak the CTA after the
story's peak"; this locks the mechanics of that change so a later edit cannot
silently drop it or, worse, apply it to a channel the numbers do not flag.

    python3 scripts/test_cta_mid.py     # exit 0 = placement intact
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import make_short  # noqa: E402
import publish_shorts  # noqa: E402


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def main() -> int:
    script = {"id": "70", "hook": "hook",
              "lines": ["l1", "l2", "l3", "l4", "l5", "l6", "l7", "l8"],
              "cta": "กดติดตาม"}

    tail = make_short.spoken_sequence(script, cta_mid=False)
    if tail[-1] != "กดติดตาม":
        fail(f"default placement no longer ends with the CTA: {tail}")
    if tail.index("กดติดตาม") != len(tail) - 1:
        fail("default CTA is not the last item")

    mid = make_short.spoken_sequence(script, cta_mid=True)
    i = mid.index("กดติดตาม")
    if i == 0 or i == len(mid) - 1:
        fail(f"mid placement did not move the CTA off the tail: {mid}")
    # The hook stays first and the story order is preserved around the CTA.
    if mid[0] != "hook":
        fail("the hook is no longer first after the CTA move")
    if [x for x in mid if x != "กดติดตาม"] != tail[:-1]:
        fail("the story lines were reordered by the CTA move")
    # Peak, not tail: the CTA should land past the halfway point of the story.
    story_pos = i - 1                      # lines before the CTA
    if story_pos < len(script["lines"]) // 2:
        fail(f"CTA landed too early ({story_pos}/{len(script['lines'])} lines in)")

    # Only kongkeat is flagged. If another channel's numbers ever look the same,
    # flag it deliberately -- do not leak the experiment into a healthy channel.
    flagged = [slug for slug, spec in publish_shorts.CHANNELS.items() if spec.get("cta_mid")]
    if flagged != ["kongkeat"]:
        fail(f"cta_mid should be kongkeat only, got {flagged}")

    # The rail must actually pass the flag through to the renderer.
    for name in ("publish_shorts.py", "remake_shorts.py"):
        src = open(os.path.join(HERE, name), encoding="utf-8").read()
        if '"--cta-mid"' not in src:
            fail(f"{name} does not pass --cta-mid to make_short")
    ms = open(os.path.join(HERE, "make_short.py"), encoding="utf-8").read()
    if "cta_mid=args.cta_mid" not in ms:
        fail("make_short does not wire --cta-mid into build()")

    print("OK: ch4 CTA speaks after the peak, other channels unchanged, rail wired")
    return 0


if __name__ == "__main__":
    sys.exit(main())
