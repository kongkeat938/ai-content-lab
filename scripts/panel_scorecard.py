#!/usr/bin/env python3
"""Score the advisor panel: does each advisor actually do the job?

K's rule: a team of advisors must be measured too -- on timeline, output and
goal. A vendor that is slow, ignores the format, or invents numbers is not an
advisor, it is noise. This sends each advisor the same three checkable probes and
grades the result, so a replacement decision is based on numbers.

Probes (each has a verifiable pass/fail, never "it replied"):
  1. format   -- asks for a JSON object with fixed keys; passes only if it parses.
  2. grounding-- embeds the real channel numbers and asks for the view total;
                 passes only if the exact number comes back (catches invented data).
  3. thai     -- must answer in Thai; passes only if Thai characters are present.

    python3 scripts/panel_scorecard.py                 # fast free advisors
    python3 scripts/panel_scorecard.py --all           # include the slow OpenHands ones
    python3 scripts/panel_scorecard.py --only gemini,pollinations
    python3 scripts/panel_scorecard.py --out docs/PANEL-SCORECARD.md
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from advise import ADVISORS  # noqa: E402

# The numbers here are the real measured channel state, so a grounded answer can
# be checked against a fact rather than an opinion.
VIEWS = 19946
SUBS = 106
V = f"{VIEWS:,}"

PROBES = {
    "format": (
        'ตอบกลับเป็น JSON เท่านั้น ในรูปแบบ {"ok": true, "first_step": "<ขั้นแรก>"} '
        'โดย first_step เป็นภาษาไทยไม่เกิน 10 คำ'),
    "grounding": (
        f"ข้อมูลช่อง: ผู้ติดตาม {SUBS} คน, คลิป 78 คลิป, ยอดวิวรวม {V}. "
        "ตอบด้วยตัวเลขยอดวิวรวมเท่านั้น ห้ามมีคำอื่น"),
    "thai": "เขียนหนึ่งประโยคภาษาไทยที่ให้กำลังใจคนทำช่องใหม่",
}
THAI = re.compile(r"[\u0E00-\u0E7F]")


def _call(name: str, prompt: str, timeout: int = 240) -> tuple[str, float, str]:
    """Return (answer, seconds, error)."""
    start = time.time()
    try:
        ans = ADVISORS[name](prompt)
        return ans.strip(), time.time() - start, ""
    except Exception as exc:  # noqa: BLE001 - a dead advisor is a data point
        return "", time.time() - start, str(exc)[:160]


def grade(name: str, full: bool) -> dict:
    res = {"advisor": name, "probes": {}, "error": "", "seconds": 0.0}
    for pname, prompt in PROBES.items():
        ans, secs, err = _call(name, prompt)
        res["seconds"] += secs
        if err:
            res["probes"][pname] = False
            res["error"] = err
            continue
        if pname == "format":
            ok = False
            m = re.search(r"\{.*\}", ans, re.S)
            if m:
                try:
                    ok = set(json.loads(m.group(0))) >= {"ok", "first_step"}
                except json.JSONDecodeError:
                    ok = False
        elif pname == "grounding":
            ok = str(VIEWS) in ans.replace(",", "") or V in ans
        else:
            ok = bool(THAI.search(ans))
        res["probes"][pname] = ok
    res["answer_sample"] = ans[:80]
    return res


def score(res: dict) -> int:
    p = res["probes"]
    pts = 25 * bool(p.get("format")) + 30 * bool(p.get("grounding")) + 20 * bool(p.get("thai"))
    pts += 25 if any(p.values()) else 0  # reachability: did it answer at all
    return pts


def verdict(res: dict) -> str:
    s = score(res)
    if s >= 80:
        return "KEEP"
    if s >= 50:
        return "WATCH"
    return "REPLACE"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="include the slow OpenHands advisors")
    ap.add_argument("--only", default="", help="comma list of advisors")
    ap.add_argument("--out", help="write a markdown report here")
    args = ap.parse_args()

    fast = ["gemini", "pollinations"]
    names = ([n.strip() for n in args.only.split(",") if n.strip()]
             or (list(ADVISORS) if args.all else fast))

    print(f"Scoring {len(names)} advisors: {', '.join(names)}\n")
    rows: list[dict] = []
    with ThreadPoolExecutor(max_workers=len(names)) as pool:
        for r in pool.map(lambda n: grade(n, args.all), names):
            rows.append(r)

    lines = ["| advisor | format | grounding | thai | secs | score | verdict |",
             "|---|---|---|---|---|---|---|"]
    for r in sorted(rows, key=score, reverse=True):
        p = r["probes"]
        mark = lambda k: "OK" if p.get(k) else "-"  # noqa: E731
        lines.append(f"| {r['advisor']} | {mark('format')} | {mark('grounding')} | "
                     f"{mark('thai')} | {r['seconds']:.1f} | {score(r)} | {verdict(r)} |")
    table = "\n".join(lines)
    print(table)
    print(f"\nmeasured {time.strftime('%Y-%m-%d %H:%M')}")

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write("# Advisor panel scorecard\n\n" + table + "\n")
            fh.write("\n## Raw\n\n```json\n"
                     + json.dumps(rows, ensure_ascii=False, indent=2) + "\n```\n")
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
