#!/usr/bin/env python3
"""The learning loop must send the tension hint, and must not write flat subjects.

Measured 2026-11-11: `studio_ai.TOPICS_HINT` was keyed "kongkeat" while
`question_for()` is always called with the Studio id ("ch4"), so the hint was
never sent, the panel proposed flat scenes, `content/insights/ch4.json` was
written flat, and `test_pace.py` went red -- the one CI failure in 100 runs. The
bug survived a day because the guard checked only the *file*, not the wiring that
produces it.

So this guards the wiring directly and deterministically (no live LLM):
  1. question_for("ch4") actually carries the tension hint;
  2. write_insights drops off-rule subjects for a rule-bound channel, and falls
     back to the channel's own on-rule subjects rather than writing an empty set;
  3. a channel with no rule is left untouched.

    python3 scripts/test_insights_wiring.py     # exit 0 = the loop is wired
"""
from __future__ import annotations

import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import studio_ai as S  # noqa: E402

FAILS = 0


def check(label: str, ok: bool, got=None) -> None:
    global FAILS
    print(f"  {'ok  ' if ok else 'FAIL'} {label}" + ("" if ok else f" -- got {got!r}"))
    if not ok:
        FAILS += 1


def main() -> int:
    # 1. The hint reaches the prompt for the channel the workflow actually calls.
    q = S.question_for("ch4")
    check("question_for('ch4') carries the tension hint", "ปมตึง" in q, q[-120:])
    # ...and via the generator's own name, too.
    check("question_for('kongkeat-story') carries the hint",
          "ปมตึง" in S.question_for("kongkeat-story"))
    check("a channel with no rule gets the plain question",
          "ปมตึง" not in S.question_for("ch1"))

    # 2. write_insights filters off-rule subjects for a rule-bound channel.
    req = getattr(S, "required_hook", lambda _c: None)("ch4")
    check("ch4 resolves to a required hook marker", req is not None)
    if req is None:
        print(f"{FAILS} wiring check(s) failed")
        return 1
    flat = "พ่อกอดลูกชายในวันเกิด"          # no tension marker
    tense = "คืนที่พ่อจากไปโดยไม่บอกลา"      # carries a marker
    with tempfile.TemporaryDirectory() as td:
        orig = S.ROOT
        S.ROOT = td
        try:
            ans = {"gemini": f"TOPICS: {flat} | {tense} |"}
            path = S.write_insights("ch4", [], ans)
            blob = json.load(open(path, encoding="utf-8"))
            got = blob.get("topics", [])
            check("off-rule subject dropped, on-rule kept",
                  flat not in got and tense in got, got)
            check("every written subject carries the marker",
                  all(req.search(t) for t in got), got)
            # Nothing usable -> fall back to the channel's own on-rule subjects.
            path = S.write_insights("ch4", [], {"gemini": f"TOPICS: {flat} |"})
            got = json.load(open(path, encoding="utf-8")).get("topics", [])
            check("an all-flat panel answer falls back, not empty",
                  bool(got) and all(req.search(t) for t in got), got)
            # A channel with no rule is left untouched.
            path = S.write_insights("ch1", [], {"gemini": f"TOPICS: {flat} |"})
            got = json.load(open(path, encoding="utf-8")).get("topics", [])
            check("a channel with no rule keeps its subjects", flat in got, got)
        finally:
            S.ROOT = orig

    print("OK: the tension hint reaches the panel and flat subjects never reach the file"
          if not FAILS else f"{FAILS} wiring check(s) failed")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
