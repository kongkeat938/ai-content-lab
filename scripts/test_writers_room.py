#!/usr/bin/env python3
"""The writing room's gate must be able to FAIL.

A judge that accepts everything is decoration: it would ship a digit that
edge-tts reads wrong, or a hook that is a copy of one already published. Each
case below is a defect measured in a real draft, plus the good shape that must
pass, so a future loosening of `problems()` is caught here.

    python3 scripts/test_writers_room.py
"""
from __future__ import annotations

import sys

import writers_room as wr

GOOD = {
    "hook": "คืนนี้ลองวางมือบนท้องแล้วขอบคุณร่างกายที่แบกเรามาทั้งวัน",
    "lines": [
        "ร่างกายนี้ทำงานให้เราโดยไม่เคยขอพัก",
        "เช้าถึงเย็นมันพาเราเดิน พาเราหายใจ",
        "คืนนี้ลองวางมือลงบนหน้าท้องช้า ๆ",
        "บอกมันเบา ๆ ว่าขอบคุณที่อดทนมาทั้งวัน",
        "ไม่ต้องทำอะไรอีก แค่นอนฟังลมหายใจของตัวเอง",
        "ปล่อยให้ความเหนื่อยค่อย ๆ ละลายไปกับความมืด",
    ],
    "cta": "กดติดตามช่องเพื่อฟังธรรมะเต็มบทก่อนนอน",
}

failures: list[str] = []


def check(ok: bool, what: str) -> None:
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        failures.append(what)


def main() -> int:
    check(wr.problems(GOOD) == [], f"the good draft ships ({wr.problems(GOOD)})")

    digit = dict(GOOD, hook="คืนนี้ลองวางมือบนท้องแล้วนับลมหายใจ ๑๐ ครั้ง")
    digit["hook"] = "คืนนี้ลองวางมือบนท้องแล้วนับลมหายใจ 10 ครั้ง"
    check(any("digit" in p for p in wr.problems(digit)), "a bare digit is caught")

    emoji = dict(GOOD, cta="กดติดตามช่อง 🌙 เพื่อฟังธรรมะเต็มบทก่อนนอน")
    check(any("emoji" in p for p in wr.problems(emoji)), "an emoji is caught")

    short = dict(GOOD, lines=["ขอบคุณร่างกาย", "นอนเถอะ"])
    check(any("lines" in p for p in wr.problems(short)), "too few lines is caught")

    quiet = dict(GOOD, lines=["อืม"] * 6)
    check(any("speech" in p for p in wr.problems(quiet)), "speech too short is caught")

    long_hook = dict(GOOD, hook="คืนนี้ลองวางมือบนท้องแล้วขอบคุณร่างกายที่แบกเรามาทั้งวันและทุกคืนที่ผ่านมาอีกด้วยนะ"
                              "และอีกหลายปีที่มันยังคงทำงานให้เราโดยไม่เคยขอพักผ่อนเลยสักครั้ง")
    check(any("hook" in p for p in wr.problems(long_hook)), "an overlong hook is caught")

    copy = wr.problems(GOOD, [GOOD["hook"] + " และอีกมากมาย"])
    check(any("repeats" in p for p in copy), "a repeated hook is caught")

    check(wr.problems(None) == ["not JSON"], "a non-JSON reply is rejected")
    check(wr.parse('```json\n{"hook":"ก","lines":["ข"],"cta":"ค"}\n```') is not None,
          "a fenced reply still parses")
    check(wr.parse("ขอโทษนะครับ ผมเขียนไม่ได้") is None, "chatty non-JSON is rejected")

    brief = wr.build_brief("หัวข้อทดสอบ")
    check("JSON เท่านั้น" in brief and "ห้ามมีตัวเลขโดด" in brief,
          "the brief states the rules it is judged by")
    check("Farmmer" in brief, "the brief names the channel")

    print(f"\n{'FAILED' if failures else 'PASS'} ({len(failures)} failures)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
