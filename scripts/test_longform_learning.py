#!/usr/bin/env python3
"""Guard the fix that makes the long-form rail actually learn.

Measured 2026-11-09: the learning loop ranked "winners" by **views**. Views always
crown the Shorts (they out-view long-form a hundred to one) and Shorts contribute
**zero** YPP watch-hours, so the panel learned from the wrong videos and the
long-form rail -- the only content that moves watch-hours -- learned nothing.
`content/insights/*.json` were 100% Shorts titles, and `gen_night_scripts.py` did
not read insights at all.

The fix: rank winners by long-form watch time, hand the panel a long-form view,
ask it for long-form night-set THEMES, and let gen_night_scripts consume those
themes and the review RULES. This test locks each link in so it cannot be lost.

    python3 scripts/test_longform_learning.py     # exit 0 = the rail learns
"""
from __future__ import annotations

import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import studio_ai as S  # noqa: E402
import gen_night_scripts as G  # noqa: E402
import video_review as V  # noqa: E402

FAILS = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if cond else 'FAIL'} {name}{(' -- ' + detail) if detail else ''}")
    if not cond:
        FAILS.append(name)


def main() -> int:
    # 1. A high-view Short must NOT outrank a long-form in the winners.
    shorts = [{"title": "Short ที่คนดูเยอะ", "views": 99999, "estimatedMinutesWatched": 500}]
    longform = [{"title": "คลิปยาวที่ได้ watch time จริง", "views": 40,
                 "estimatedMinutesWatched": 900}]
    winners = S.rank_winners(shorts, longform)
    check("winners prefer long-form over high-view Shorts",
          winners == ["คลิปยาวที่ได้ watch time จริง"], str(winners))

    # 2. With no long-form at all, the loop still runs (top-by-views fallback).
    fallback = S.rank_winners(shorts, [])
    check("falls back to top-by-views when a channel has no long-form",
          fallback == ["Short ที่คนดูเยอะ"], str(fallback))

    # 3. longform_ids reads the published long-form ids from the publish manifest.
    ids = S.longform_ids("ch2")
    manifest = json.load(open(os.path.join(S.ROOT, "content/ch2_publish.json"), encoding="utf-8"))
    want = {v["video_id"] for v in manifest["videos"]
            if v.get("video_id") and v.get("state") == "published"}
    check("longform_ids returns the published long-form ids", ids == want,
          f"{len(ids)} ids")

    # 4. THEMES are parsed out of a panel answer, separately from TOPICS.
    ans = ("...\nTHEMES: ปล่อยวางความกังวลเรื่องเงิน | ความเหงาในตอนกลางคืน\n"
           "TOPICS: นอนไม่หลับ ลองทำท่านี้ #Shorts | วางมือบนท้องแล้วหายใจ")
    themes = S.parse_themes(ans)
    topics = S.parse_topics(ans)
    check("parse_themes pulls the long-form themes", themes == ["ปล่อยวางความกังวลเรื่องเงิน", "ความเหงาในตอนกลางคืน"], str(themes))
    check("parse_topics still pulls the Shorts subjects", len(topics) == 2, str(topics))

    # 5. write_insights stores long-form winners + themes, not the Shorts.
    orig_root = S.ROOT
    with tempfile.TemporaryDirectory() as td:
        S.ROOT = td
        try:
            S.write_insights("ch2", shorts, {"gemini": ans}, longform)
            blob = json.load(open(os.path.join(td, "content/insights/dharma.json"), encoding="utf-8"))
        finally:
            S.ROOT = orig_root
        check("insights winners are the long-form videos",
              blob["winners"] == ["คลิปยาวที่ได้ watch time จริง"], str(blob["winners"]))
        check("insights carry the long-form themes",
              blob.get("themes") == ["ปล่อยวางความกังวลเรื่องเงิน", "ความเหงาในตอนกลางคืน"], str(blob.get("themes")))

    # 6. gen_night_scripts learns the theme and injects the rules into its prompt.
    orig_groot = G.ROOT
    with tempfile.TemporaryDirectory() as td:
        G.ROOT = td
        os.makedirs(os.path.join(td, "content/insights"), exist_ok=True)
        json.dump({"themes": ["ธีมที่เรียนรู้มา"], "rules": ["เปิดด้วยการลงมือทำทันที"]},
                  open(os.path.join(td, "content/insights/dharma.json"), "w", encoding="utf-8"),
                  ensure_ascii=False)
        try:
            ins = G.learned("dharma")
            prompt = G.prompt_for("ธีมที่เรียนรู้มา", "open", "ชวนลงมือทำ", ins.get("rules"))
        finally:
            G.ROOT = orig_groot
        check("gen_night_scripts reads the learned themes",
              ins.get("themes") == ["ธีมที่เรียนรู้มา"], str(ins.get("themes")))
        check("gen_night_scripts injects the review rules into the prompt",
              "เปิดด้วยการลงมือทำทันที" in prompt)

    # 7. The review grades the long-form too (same fix as studio_ai).
    check("video_review knows the long-form ids",
          V.longform_ids("ch2") == ids, f"{len(V.longform_ids('ch2'))} ids")

    if FAILS:
        print(f"\nFAILED: {FAILS}")
        return 1
    print("\nOK: the long-form rail learns from watch time, not Shorts views")
    return 0


if __name__ == "__main__":
    sys.exit(main())
