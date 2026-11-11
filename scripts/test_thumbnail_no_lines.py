#!/usr/bin/env python3
"""A thumbnail must render even when the title yields no card words.

`words()` returns [] when the title is empty and the keyword is a hashtag (or
absent). `draw()` then did `max(d.textbbox(...) for ln in lines)`, which raises
"max() iterable argument is empty". Measured 2026-11-10: the polish-all job died
on exactly that, and because the loop had no per-video guard it dropped every
later video in the batch too.

Two fixes, both locked here:
  1. draw() renders the cover untouched when there are no lines (never raises).
  2. main() catches a per-video build failure so one bad video cannot abort a pass.

    python3 scripts/test_thumbnail_no_lines.py    # exit 0 = empty title is safe
"""
from __future__ import annotations

import ast
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from PIL import Image  # noqa: E402

import make_video_thumbnail as t  # noqa: E402

FAILS = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" -- {detail}" if detail and not ok else ""))
    if not ok:
        FAILS.append(name)


def main() -> int:
    print("words() returns no lines for an empty title / hashtag keyword")
    check("empty title yields []", t.words("", "") == [], f"{t.words('', '')}")
    check("hashtag keyword yields []", t.words("", "#shorts") == [], f"{t.words('', '#shorts')}")

    print("draw() renders a card with no lines instead of raising")
    cover = Image.new("RGB", (t.W, t.H), (30, 40, 60))
    try:
        out = t.draw(cover.copy(), [])
        rendered = isinstance(out, Image.Image) and out.size == (t.W, t.H)
        check("draw([]) returns a full-size image", rendered,
              f"{type(out)} {getattr(out, 'size', None)}")
    except Exception as exc:  # noqa: BLE001
        check("draw([]) returns a full-size image", False, f"{type(exc).__name__}: {exc}")

    print("draw() still renders real lines")
    try:
        out2 = t.draw(cover.copy(), ["คืนที่พ่อจากไป", "ฉันพบจดหมาย"])
        check("draw(lines) returns a full-size image",
              isinstance(out2, Image.Image) and out2.size == (t.W, t.H))
    except Exception as exc:  # noqa: BLE001
        check("draw(lines) returns a full-size image", False, f"{type(exc).__name__}: {exc}")

    print("main() guards each video so one failure cannot abort the pass")
    src = open(os.path.join(HERE, "make_video_thumbnail.py"), encoding="utf-8").read()
    tree = ast.parse(src)
    loop_guarded = False
    for node in ast.walk(tree):
        if isinstance(node, ast.For):
            for sub in ast.walk(node):
                if isinstance(sub, ast.Try):
                    handlers = [h for h in sub.handlers
                                if h.type is None
                                or (isinstance(h.type, ast.Name) and h.type.id == "Exception")]
                    if handlers:
                        loop_guarded = True
    check("the per-video build call is inside try/except Exception", loop_guarded)

    print()
    if FAILS:
        print(f"FAIL: {len(FAILS)} check(s) failed: {FAILS}")
        return 1
    print("OK: a title with no card words is safe")
    return 0


if __name__ == "__main__":
    sys.exit(main())
