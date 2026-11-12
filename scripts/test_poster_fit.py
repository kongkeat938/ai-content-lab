#!/usr/bin/env python3
"""A poster title must fit the frame, however long it is.

Measured 2026-11-12: a single-line title at 176px is 5862px wide against a 1920px
frame, so a long title ran off both edges. The real rails happen to pass short
titles ("ปรัชญาชีวิต"), so it never bit -- but nothing stopped it, the same blind
spot the Shorts captions had. The title (and subtitle) are now wrapped and shrunk
to a safe margin; this guards it:

  1. every title the workflows actually pass fits inside the margin, every layout;
  2. a deliberately long title wraps (never runs off the edge) and stays on screen;
  3. the guard can FAIL -- the un-wrapped title overflows, so wrapping is doing work.

The titles are swept from the workflow files, never hardcoded, so a new rail that
passes a longer title is covered the day it lands.

    python3 scripts/test_poster_fit.py
"""
from __future__ import annotations

import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from PIL import Image, ImageDraw  # noqa: E402

import make_poster as mp  # noqa: E402

FAILS = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" -- {detail}" if detail and not ok else ""))
    if not ok:
        FAILS.append(name)


def workflow_titles() -> list[tuple[str, str]]:
    """Every (title, subtitle) a workflow passes to the poster, swept from source."""
    out: list[tuple[str, str]] = []
    pat_t = re.compile(r'--title\s+"([^"]*)"')
    pat_s = re.compile(r'--subtitle\s+"([^"]*)"')
    for path in glob.glob(os.path.join(ROOT, ".github", "workflows", "*.yml")):
        text = open(path, encoding="utf-8").read()
        titles = pat_t.findall(text)
        subs = pat_s.findall(text)
        for i, t in enumerate(titles):
            out.append((t, subs[i] if i < len(subs) else ""))
    return out


def lines_fit(lay: dict) -> tuple[bool, str]:
    d = ImageDraw.Draw(Image.new("L", (mp.W, mp.H)))
    worst = 0.0
    for ln in lay["title_lines"]:
        worst = max(worst, d.textlength(ln, font=lay["title_font"]))
    for ln in lay["sub_lines"]:
        worst = max(worst, d.textlength(ln, font=lay["sub_font"]))
    on_screen = lay["top"] >= mp.BAR and lay["bottom"] <= mp.H - mp.BAR
    return worst <= lay["max_w"] + 1 and on_screen, \
        f"widest line {worst:.0f} vs max {lay['max_w']}, top {lay['top']} bottom {lay['bottom']}"


def main() -> int:
    cases = workflow_titles()
    print(f"real workflow titles swept: {len(cases)}")
    check("the workflows yield real titles to test", len(cases) > 0, str(cases))

    print("every real title fits, in every layout")
    bad = []
    for title, sub in cases:
        for li in range(len(mp.LAYOUTS)):
            ok, why = lines_fit(mp.text_layout(title, sub, li))
            if not ok:
                bad.append(f"layout{li} {title[:20]} ({why})")
    check(f"all {len(cases)} real titles fit all {len(mp.LAYOUTS)} layouts", not bad,
          "; ".join(bad[:3]))

    print("a deliberately long title wraps and stays on screen")
    long_title = "ทำไมคนดีถึงต้องเจ็บปวดที่สุดในชีวิต และวิธีปล่อยวางความทุกข์ให้ใจเบาสบายก่อนนอนทุกคืน"
    lay = mp.text_layout(long_title, "รวมข้อคิดให้ใจเบาลง", 0)
    d = ImageDraw.Draw(Image.new("L", (mp.W, mp.H)))
    widest = max(d.textlength(ln, font=lay["title_font"]) for ln in lay["title_lines"])
    check("the long title wraps into more than one line", len(lay["title_lines"]) > 1,
          f"{len(lay['title_lines'])} lines")
    check("no wrapped line runs past the margin", widest <= lay["max_w"] + 1,
          f"{widest:.0f} vs {lay['max_w']}")
    check("the wrapped title stays within the line cap", len(lay["title_lines"]) <= mp.TITLE_MAX_LINES,
          f"{len(lay['title_lines'])} lines")

    print("the guard can fail: an un-wrapped title overflows the frame")
    raw = ImageDraw.Draw(Image.new("L", (mp.W, mp.H)))
    raw_w = raw.textlength(long_title, font=mp.font("Kanit-Bold.ttf", mp.LAYOUTS[0][1]))
    check("the raw single-line title exceeds the margin (so wrapping does work)",
          raw_w > mp.W - 2 * mp.SAFE, f"raw {raw_w:.0f} vs max {mp.W - 2 * mp.SAFE}")

    print()
    if FAILS:
        print(f"FAIL: {len(FAILS)} check(s) failed: {FAILS}")
        return 1
    print("OK: poster titles wrap to fit the frame on every layout")
    return 0


if __name__ == "__main__":
    sys.exit(main())
