#!/usr/bin/env python3
"""Guard the general-knowledge generator's gates and its arc.

Two rules that must be able to FAIL:
  * a piece with a digit, Latin text, emoji or too few lines must be rejected --
    the generators once let "หน้ายose" (Latin glued to Thai) through;
  * the arc must cover enough distinct questions to fill a long-form, and a set
    short of --count must refuse to write (a partial set silently shortens the
    file below its floor).
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gen_knowledge_scripts as gk  # noqa: E402

GOOD = "\n".join([
    "ลองแหงนหน้ามองท้องฟ้าในวันที่อากาศแจ่มใส",
    "แล้วคุณอาจจะสงสัยว่าทำไมมันถึงเป็นสีฟ้า",
    "ความจริงแล้วโลกของเรามีชั้นบรรยากาศห่อหุ้ม",
    "แสงสีฟ้ากระเจิงตัวได้ดีกว่าสีอื่นมาก",
    "ดวงตาของเราจึงมองเห็นแสงสีฟ้าเต็มท้องฟ้า",
    "นี่คือเหตุผลทางวิทยาศาสตร์ที่อธิบายได้",
])


def test_good_piece_passes() -> None:
    ok, reason = gk.valid(GOOD)
    assert ok, f"a valid Thai piece was rejected: {reason}"


def test_digits_rejected() -> None:
    ok, reason = gk.valid(GOOD + "\nรุ้งมี 7 สี")
    assert not ok and reason == "has digits", f"digits slipped through: {reason}"


def test_latin_rejected() -> None:
    ok, reason = gk.valid(GOOD.replace("สีฟ้า", "sky สีฟ้า"))
    assert not ok and reason == "foreign script", f"Latin slipped through: {reason}"


def test_emoji_rejected() -> None:
    ok, reason = gk.valid(GOOD + "\nน่าสนใจมาก 😀")
    assert not ok and reason == "foreign script", f"emoji slipped through: {reason}"


def test_too_short_rejected() -> None:
    ok, reason = gk.valid("ท้องฟ้าเป็นสีฟ้า\nเพราะแสงกระเจิง")
    assert not ok and reason.startswith("too short"), f"short piece passed: {reason}"


def test_arc_is_broad_enough() -> None:
    # Enough distinct questions that a 20-min file does not repeat one idea.
    assert len(gk.ARC) >= 12, f"arc too narrow: {len(gk.ARC)} questions"
    names = [n for n, _, _ in gk.ARC]
    assert len(set(names)) == len(names), "duplicate question names in the arc"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok {name}")
    print("OK: knowledge generator gates hold and the arc is broad")
