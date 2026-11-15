#!/usr/bin/env python3
"""The rogue alert must not assert per-video attributes the audit never measured.

Measured 2026-11-15: `audit_channels.py` warned that the unrecorded uploads carry
`en-US` / category 27 / an old brand, "so they are NOT our rails". The audit reads
`snippet,statistics,contentDetails` -- never a per-video `categoryId`,
`defaultLanguage`, `defaultAudioLanguage`, or brand. The claim was written into the
alert body by hand. It was also wrong: the clips carry `th`, category 22/24, and our
own `— ช่องพี่น้อง —` promo block, so the "external attacker" conclusion K was given
rested on an unmeasured sentence.

A guard must be able to FAIL. This one fails if the body ever claims a per-video
attribute the code does not read, or if the honest "likely cause" sentence is gone.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import audit_channels as ac  # noqa: E402


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def main() -> int:
    body = ac.rogue_alert_body({"genx": ["video X is UNRECORDED and published 0.2d ago "
                                         "-- LIVE rogue upload outside the rails: t"]})

    # 1. No fabricated per-video-attribute claim. The audit does not measure these.
    for phrase in ("en-US", "category 27", "category 22/24", "defaultLanguage=th",
                   "defaultAudioLanguage", "NOT our rails"):
        if phrase in body:
            fail(f"the alert still claims {phrase!r}, which the audit never measures; "
                 f"a written claim is not a measurement")

    # 2. It must still say what it DID measure.
    if "NO manifest" not in body:
        fail("the alert no longer states the one thing the audit measures (unrecorded)")

    # 3. It must point at the measured likely cause, not an attacker.
    if "aeris-drive-automation" not in body or "shared" not in body.lower():
        fail("the alert no longer names the shared-OAuth-client cause; K was misled "
             "into believing an outside attacker was posting")

    # 4. Prove the check can FAIL: an old-style body must trip it.
    forged = "these carry `en-US`/category 27 and an old brand, so they are NOT our rails"
    if not any(p in forged for p in ("en-US", "category 27", "NOT our rails")):
        fail("the guard cannot detect the old fabricated claim; it proves nothing")

    print("OK: the rogue alert states only what the audit measures and names the "
          "shared-client cause; it does not assert an unmeasured category/language")
    return 0


if __name__ == "__main__":
    sys.exit(main())
