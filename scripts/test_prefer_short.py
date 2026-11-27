#!/usr/bin/env python3
"""The queue must spend its slots on the short end, and it must know a clip's
length before rendering it.

Measured 2026-11-27 (n=333 Shorts, dharma+genx, controlled for theme): the
>48 s bucket has a median of 8 lifetime views against 142-201 at 33-48 s, and
the effect holds inside one theme. That is only actionable if the rail can tell
a long clip from a short one *before* building it, which is what the calibration
fitted on 241 published clips buys (R2=0.956).

    python3 scripts/test_prefer_short.py
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import publish_shorts as ps  # noqa: E402

CHECKS = []


def check(name, ok, detail=""):
    CHECKS.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'} {name}" + (f" -- {detail}" if detail and not ok else ""))


def script(chars: int, sid: str = "x") -> dict:
    """A script whose spoken text is exactly `chars` characters."""
    body = "ก" * max(chars - len(" ") * 4, 0)
    quarter = body[: max(len(body) // 4, 1)]
    return {"id": sid, "hook": quarter, "lines": [quarter, quarter, quarter], "cta": ""}


def main() -> int:
    cal = json.load(open(os.path.join(ROOT, "content", "duration_calibration.json"), encoding="utf-8"))
    check("the fit rests on a real sample", cal.get("n", 0) >= 100, str(cal.get("n")))
    check("the fit explains the duration", 0.90 <= float(cal.get("r2", 0)) <= 1.0, str(cal.get("r2")))
    check("both coefficients are positive",
          float(cal["intercept_sec"]) > 0 and float(cal["sec_per_char"]) > 0, str(cal))
    check("the fit is dated", bool(cal.get("measured_at")), str(cal.get("measured_at")))

    # a 30 s clip is ~293 characters by the measurement; the predictor must say so
    p30 = ps.predicted_seconds(script(293))
    check("293 characters predict about 30 s", 27 <= p30 <= 33, f"{p30:.1f}")
    check("a longer script predicts a longer clip",
          ps.predicted_seconds(script(500)) > ps.predicted_seconds(script(300)))

    # the ordering itself: shortest first, and stable for equal lengths
    todo = [script(560, "long"), script(300, "short"), script(430, "mid")]
    got = [s["id"] for s in ps.prefer_short(todo)]
    check("the short clip goes first", got[0] == "short", str(got))
    check("the long clip goes last", got[-1] == "long", str(got))
    check("the input list is not mutated", [s["id"] for s in todo] == ["long", "short", "mid"])

    # the live pool must actually contain clips this ordering can save
    pool = json.load(open(os.path.join(ROOT, "content", "ch2_shorts", "scripts.json"), encoding="utf-8"))
    man = json.load(open(os.path.join(ROOT, "content", "ch2_shorts.json"), encoding="utf-8"))
    todo = [s for s in pool if not man["shorts"].get(s["id"], {}).get("video_id")]
    over = [s for s in todo if ps.predicted_seconds(s) > 48]
    check("the dharma pool has unpublished clips", len(todo) >= 10, str(len(todo)))
    check("some unpublished dharma clips are predicted over 48 s", len(over) > 0, str(len(over)))
    if todo:
        ordered = ps.prefer_short(todo)
        check("the pool is ordered shortest-first",
              ps.predicted_seconds(ordered[0]) <= ps.predicted_seconds(ordered[-1]))

    # wiring: the two live channels opt in, and the sort runs before the cue sort
    src = open(os.path.join(HERE, "publish_shorts.py"), encoding="utf-8").read()
    check("dharma opts in", '"prefer_short": True' in src)
    i_short, i_pace = src.find("todo = prefer_short(todo)"), src.find("pace.order(todo")
    check("the length sort runs before the cue sort", 0 < i_short < i_pace, f"{i_short} vs {i_pace}")
    check("the channel spec turns it on", "spec.get(\"prefer_short\")" in src)

    bad = [n for n, ok, _ in CHECKS if not ok]
    print()
    print(f"{len(CHECKS) - len(bad)}/{len(CHECKS)} checks passed" if not bad
          else f"FAIL: {len(bad)} check(s): {bad}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
