#!/usr/bin/env python3
"""Measure each advisor's quality and speed on checkable questions.

K's rule is a panel of at least five independent advisors, and the team must be
**fast and high quality**. Speed alone is not enough: a panelist that refuses, or
answers an exact-format question with a paragraph, drags the whole panel down.

This asks every advisor a small set of probes whose answer can be checked by a
machine (arithmetic, logic, exact-format, a Thai instruction, a counting trap),
times each call, and prints a table sorted by (passes desc, median latency asc).
It does not trust a vendor's own claim of quality -- it measures it.

    python3 scripts/panel_bench.py                 # the fast advisors
    python3 scripts/panel_bench.py --only gemini-3.5,openrouter
    python3 scripts/panel_bench.py --repeat 2      # steadier latency
"""
from __future__ import annotations

import argparse
import os
import re
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import advise  # noqa: E402

REFUSAL = re.compile(r"(ขอโทษ|ไม่สามารถ|ไม่สะดวก|sorry|i (?:can'?t|cannot|am unable))",
                     re.I)

# (name, prompt, checker). A checker gets the raw reply and returns True/False.
PROBES = [
    ("arith",
     "What is 17 * 23? Reply with just the number, no other words.",
     lambda t: _has_number(t, "391")),
    ("logic",
     "All bloops are razzies. All razzies are lazzies. Are all bloops lazzies? "
     "Reply with exactly one word: yes or no.",
     lambda t: t.strip().lower().strip(".").startswith("yes")),
    ("exact",
     "Reply with exactly the single word PINEAPPLE and nothing else.",
     lambda t: t.strip().strip(".").upper() == "PINEAPPLE"),
    ("thai",
     "ตอบเป็นตัวเลขเท่านั้น ห้ามมีคำอื่น: 25 + 17 เท่ากับเท่าไร",
     lambda t: _has_number(t, "42")),
    ("count",
     "How many times does the letter r appear in the word strawberry? "
     "Reply with just the number.",
     lambda t: _has_number(t, "3")),
]


def _has_number(text: str, want: str) -> bool:
    nums = re.findall(r"\d[\d,]*", text)
    return any(n.replace(",", "") == want for n in nums)


def _median(values: list[float]) -> float:
    return statistics.median(values) if values else float("nan")


def bench_one(name: str, repeat: int) -> dict:
    fn = advise.ADVISORS.get(name)
    if fn is None:
        return {"name": name, "error": "unknown advisor"}
    passes = 0
    total = 0
    latencies: list[float] = []
    notes: list[str] = []
    for _ in range(repeat):
        for pname, prompt, check in PROBES:
            t0 = time.time()
            try:
                ans = fn(prompt)
            except Exception as exc:  # noqa: BLE001 - a dead advisor is a data point
                latencies.append(time.time() - t0)
                total += 1
                notes.append(f"{pname}:ERR")
                continue
            dt = time.time() - t0
            latencies.append(dt)
            total += 1
            if REFUSAL.search(ans) or not ans.strip():
                notes.append(f"{pname}:REFUSAL")
            elif check(ans):
                passes += 1
            else:
                notes.append(f"{pname}:WRONG({ans.strip()[:24]!r})")
    return {"name": name, "passes": passes, "total": total,
            "rate": passes / total if total else 0.0,
            "median_s": _median(latencies), "notes": notes}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--include-deep", action="store_true")
    args = ap.parse_args()

    if args.only:
        names = [n.strip() for n in args.only.split(",") if n.strip()]
    else:
        names = list(advise.FAST_PLUS)
        if args.include_deep:
            names += advise.DEEP

    results = []
    for name in names:
        r = bench_one(name, args.repeat)
        results.append(r)
        if "error" in r:
            print(f"{name:16s}  {r['error']}", flush=True)
        else:
            print(f"{name:16s}  {r['passes']}/{r['total']} pass  "
                  f"median {r['median_s']:.1f}s  {' '.join(r['notes'])[:80]}",
                  flush=True)

    print("\n=== ranked (pass-rate desc, median latency asc) ===", flush=True)
    ranked = sorted(results, key=lambda r: (-r.get("rate", 0), r.get("median_s", 9e9)))
    for r in ranked:
        if "error" in r:
            continue
        print(f"{r['rate']*100:5.0f}%  {r['median_s']:6.1f}s  {r['name']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
