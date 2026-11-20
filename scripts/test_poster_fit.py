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




def contrast_ratio(rgb1, rgb2) -> float:
    """WCAG 2.x contrast ratio between two RGB colours."""
    def rel(rgb) -> float:
        def ch(c: float) -> float:
            c /= 255.0
            return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
        r, g, b = (ch(v) for v in rgb)
        return 0.2126 * r + 0.7152 * g + 0.0722 * b
    hi, lo = sorted((rel(rgb1), rel(rgb2)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def band_colour(path: str, top: int, bottom: int):
    """The band averaged to one RGB, i.e. what the text actually sits on."""
    im = Image.open(path).convert("RGB")
    band = im.crop((0, max(0, top), im.width, min(im.height, bottom)))
    return band.resize((1, 1), Image.BOX).getpixel((0, 0))


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

    # The vision grader measured Thai text lost against a bright background
    # ("ข้อความทับซ้อนกับแสงเทียน", 5/10 on two published clips, 2026-11-19). The
    # measurable form of that complaint is WCAG contrast: the title colour against
    # the band it sits on. Measured on a real poster background, the scrim moved
    # 2.67:1 -> 6.06:1, so 4.5:1 (AA for normal text) is the bar, and a plain
    # blown-out photo without the scrim lands under it -- the guard can FAIL.
    print("the title reads against whatever photo is behind it")
    import tempfile
    tmp = tempfile.mkdtemp(prefix="posterfit_")
    bright = os.path.join(tmp, "bright.jpg")
    Image.new("RGB", (mp.W, mp.H), (252, 244, 226)).save(bright)
    title, sub = "ปรัชญาชีวิต", "รวมข้อคิดให้ใจเบาลง"
    lay = mp.text_layout(title, sub, 3)
    title_rgb = (247, 243, 236)
    out = os.path.join(tmp, "card.jpg")
    mp.build(bright, out, title, sub, 3)
    got = contrast_ratio(title_rgb, band_colour(out, lay["top"], lay["bottom"]))
    check("the title meets WCAG AA (4.5:1) over a blown-out photo", got >= 4.5,
          f"{got:.2f}:1")

    print("the guard can fail: the same photo without a scrim is unreadable")
    plain = mp.vignette(mp.grade(Image.new("RGB", (mp.W, mp.H), (252, 244, 226))))
    raw_path = os.path.join(tmp, "plain.jpg")
    plain.save(raw_path)
    raw = contrast_ratio(title_rgb, band_colour(raw_path, lay["top"], lay["bottom"]))
    check("without the scrim the same test would fail", raw < 4.5, f"{raw:.2f}:1")

    print("Thai text is never split inside a cluster")
    # Measured 2026-11-19: a plain character wrap broke 276 of the real titles in
    # content/ -- "โดยไม่ต้องแบกโ" / "ลก" (โลก cut in half), "นำมาใ" / "ห้". The
    # vision grader had been reporting this as "text overlaps the background",
    # which is what a broken word looks like at a glance.
    import unicodedata
    LEAD = set("เแโใไ")
    NOSTART = set("ะาำๅๆ")

    def illegal(lines: list[str]) -> str:
        for i in range(len(lines) - 1):
            if lines[i] and lines[i][-1] in LEAD:
                return f"line {i} ends with a leading vowel: {lines[i]!r}"
            nxt = lines[i + 1]
            if nxt and (unicodedata.category(nxt[0]) in ("Mn", "Mc", "Me")
                        or nxt[0] in NOSTART):
                return f"line {i + 1} starts with an attached mark: {nxt!r}"
        return ""

    sample = "เพราะความรักไม่เคยเลือกใครและไม่เคยถามว่าเราเตรียมใจไว้หรือยัง"
    f = mp.font("Kanit-Bold.ttf", 80)
    drawn = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    bad = []
    for maxw in range(300, 1401, 10):
        lines = mp.wrap_lines(drawn, sample, f, maxw)
        why = illegal(lines)
        if why:
            bad.append((maxw, lines, why))
    check("no width splits a Thai cluster", not bad, str(bad[:2]))

    # The guard can FAIL: the old character wrap, on the same sample, does split.
    def naive(text: str, maxw: float) -> list[str]:
        out, cur = [], ""
        for ch in text:
            if not cur or drawn.textlength(cur + ch, font=f) <= maxw:
                cur += ch
            else:
                out.append(cur)
                cur = ch
        if cur:
            out.append(cur)
        return out

    broken = [w for w in range(300, 1401, 10) if illegal(naive(sample, w))]
    check("the guard can FAIL: the naive wrap it replaced is caught",
          len(broken) > 0, f"{len(broken)} widths")

    print()
    if FAILS:
        print(f"FAIL: {len(FAILS)} check(s) failed: {FAILS}")
        return 1
    print("OK: poster titles wrap to fit the frame on every layout")
    return 0


if __name__ == "__main__":
    sys.exit(main())
