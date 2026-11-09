#!/usr/bin/env python3
"""A ch4 Short must not promise a "full clip" it cannot deliver.

Measured 2026-11-09: ch4's 120-min long-form files get 1-3 views each, so a CTA
like "go watch the full clip" sends a viewer to a dead end -- and the channel has
the worst subs-per-1k on the fleet (1.93). Twelve of its 71 scripts shipped with
that promise. An honest subscribe ask is the only funnel that exists, so:

  1. every ch4 script CTA must be a subscribe ask, not a full-clip promise;
  2. gen_short_scripts.valid() must reject a broken-promise CTA when a channel
     forbids it (so the pool cannot refill with the shape);
  3. the kongkeat-story channel config must actually forbid it.

    python3 scripts/test_ch4_cta.py     # exit 0 = no broken-promise CTA
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import gen_short_scripts as G  # noqa: E402

FAILS = 0


def check(label: str, ok: bool, got=None) -> None:
    global FAILS
    print(f"  {'ok  ' if ok else 'FAIL'} {label}" + ("" if ok else f" -- got {got!r}"))
    if not ok:
        FAILS += 1


def main() -> int:
    scripts = json.load(open(os.path.join(ROOT, "content", "ch4_shorts", "scripts.json"),
                            encoding="utf-8"))
    scripts = scripts if isinstance(scripts, list) else scripts["shorts"]
    man = json.load(open(os.path.join(ROOT, "content", "ch4_shorts.json"),
                         encoding="utf-8"))["shorts"]
    live = {k for k, v in man.items() if v.get("video_id")}
    # A published Short's CTA is spoken in the rendered audio, so it cannot be
    # changed -- only the ones still queued are held to the rule.
    broken = [s["id"] for s in scripts
              if s["id"] not in live and G._BROKEN_CTA.search(s.get("cta", ""))]
    check("no queued ch4 script promises a full clip", not broken, broken)

    # The gate itself must reject the shape, or the next pool refills with it.
    good = {"hook": "คืนนั้นแม่ทำกับข้าวให้เขากินด้วยกัน", "lines": ["ก", "ข", "ค"],
            "cta": "กดติดตามเพื่อรับเรื่องอบอุ่นใจแบบนี้ทุกวัน"}
    bad = dict(good, cta="กดติดตามแล้วไปดูคลิปเต็มในคลิปยาวกัน")
    check("valid() accepts an honest subscribe CTA",
          G.valid(good, ("แม่",), G._BROKEN_CTA))
    check("valid() rejects a full-clip promise",
          not G.valid(bad, ("แม่",), G._BROKEN_CTA))

    cfg = G.CHANNELS["kongkeat-story"]
    check("the kongkeat-story channel forbids the broken CTA",
          cfg.get("forbid_cta") is G._BROKEN_CTA)

    if FAILS:
        print(f"\nFAILED: {FAILS}")
        return 1
    print("\nOK: ch4 Shorts ask for a subscribe, never a clip that is not there")
    return 0


if __name__ == "__main__":
    sys.exit(main())
