#!/usr/bin/env python3
"""Guards the three-layer council (no network).

The point of a guard is that it can FAIL, so this injects fake vendors into
`council3.run` and proves each gate bites:

  * every vendor that answers becomes a draft; a dead vendor is named, not dropped
  * a critic is never the author of the draft it checks
  * fewer than `min_vendors` drafts -> FAIL (quorum), not a one-voice "decision"
  * one vendor cannot cross-check itself -> FAIL
  * a draft nobody critiques -> FAIL
  * a decision citing a number absent from FACTS -> FAIL (invented figure)
  * the same decision with a number that IS in FACTS -> PASS

    python3 scripts/test_council3.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import advise  # noqa: E402
import council3  # noqa: E402

FACTS = "genx 45,408 views; long-form 82.7 watch-hours; retention 27.8%"
OK_DECISION = "DECISION: ทำคลิปยาวต่อ\nREASONS: 1) 82.7 ชม. ยังห่าง 2) 27.8% 3) 45,408\nNOT: อัพเพิ่ม\nCONFIDENCE: 7/10\nNUMBERS: 82.7, 27.8"


def fake(name: str, decision: str = OK_DECISION, dead: bool = False,
         dead_on_check: bool = False):
    def call(prompt: str) -> str:
        if dead:
            raise RuntimeError(f"{name} is down")
        if "ตรวจร่างนี้แบบเข้มงวด" in prompt:
            if dead_on_check:
                raise RuntimeError(f"{name} cannot critique")
            return "คะแนน: 7/10\nตัวเลขที่ไม่มีใน FACTS: ไม่มี"
        if "ตัดสินจากร่างและคำวิจารณ์ทั้งหมด" in prompt:
            return decision
        return f"สรุป: จาก {name}\nเหตุผล: 1) a 2) b 3) c"
    return call


def main() -> int:
    checks = []

    def check(name, cond, detail=""):
        checks.append((name, bool(cond), detail))
        print(f"{'ok ' if cond else 'FAIL'}  {name}" + (f"  [{detail}]" if detail and not cond else ""))

    res = council3.run("ทำอะไรต่อ", FACTS,
                       {"a": fake("a"), "b": fake("b"), "c": fake("c")})
    check("three vendors draft", sorted(res["drafts"]) == ["a", "b", "c"], res["drafts"].keys())
    check("every draft is critiqued", sorted(res["critiques"]) == ["a", "b", "c"])
    check("critic is never the author",
          all(c["by"] != d for d, c in res["critiques"].items()),
          {d: c["by"] for d, c in res["critiques"].items()})
    check("grounded decision passes", res["ok"] and not res["ungrounded"], res["reason"])

    res = council3.run("q", FACTS,
                       {"a": fake("a"), "b": fake("b"), "c": fake("c", dead=True)})
    check("a dead vendor is named, not dropped",
          "c" in res["draft_errors"] and len(res["drafts"]) == 2, res["draft_errors"])

    res = council3.run("q", FACTS,
                       {"a": fake("a"), "b": fake("b", dead=True), "c": fake("c", dead=True)},
                       min_vendors=2)
    check("quorum failure fails the run",
          not res["ok"] and not res["decision"] and res["reason"].startswith("quorum"),
          res["reason"])

    res = council3.run("q", FACTS, {"a": fake("a")}, min_vendors=1)
    check("one vendor cannot cross-check",
          not res["ok"] and "cross-check" in res["reason"], res["reason"])

    res = council3.run("q", FACTS,
                       {"a": fake("a"), "b": fake("b", dead_on_check=True)})
    check("an uncriticised draft fails the run",
          not res["ok"] and "uncriticised" in res["reason"], res["reason"])

    bad = OK_DECISION.replace("45,408", "45,999")
    res = council3.run("q", FACTS, {"a": fake("a", bad), "b": fake("b", bad)})
    check("an invented number fails the run",
          not res["ok"] and "45,999" in res["ungrounded"], res["ungrounded"])

    check("small numbers and years are allowed",
          council3.ungrounded_numbers("มี 3 เหตุผล ในปี 2026", FACTS) == [],
          council3.ungrounded_numbers("มี 3 เหตุผล ในปี 2026", FACTS))
    check("a decimal absent from FACTS is caught",
          council3.ungrounded_numbers("CTR 4.2%", FACTS) == ["4.2"],
          council3.ungrounded_numbers("CTR 4.2%", FACTS))

    try:
        advise.advisor("no-such-camp")
        loud = False
    except KeyError:
        loud = True
    check("an unregistered camp is loud", loud)

    failed = [n for n, ok, _ in checks if not ok]
    if failed:
        print(f"\n{len(failed)} FAILED: {failed}")
        return 1
    print(f"\nall {len(checks)} council3 checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
