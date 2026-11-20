#!/usr/bin/env python3
"""The Shorts hook must never leave a closing mark alone on its own line.

Measured 2026-11-19: a hook of "คืนนี้ นอนไม่หลับ?" wrapped to
['คืนนี้ นอนไม่หลับ', '?'] -- the question mark became a one-glyph line and the
thumbnail read as a typo. A vision check scored that build 7/10 against 8/10 for
the same hook without the orphan, so this is a real loss, not cosmetics.

The assertions below fail on the old per-character split and pass on the fix, so
this test can FAIL -- a test that only checks the happy path proves nothing.
"""
from __future__ import annotations

import os
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_short_thumbnail as M  # noqa: E402

FAILS: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    if ok:
        print(f"  PASS {name}")
    else:
        print(f"  FAIL {name} {detail}")
        FAILS.append(name)


def main() -> int:
    d = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    f = M._font(132)
    max_w = M.W - 2 * 90

    # 1. The measured regression: a trailing "?" must stay on the line it closes.
    lines = M.wrap(d, "คืนนี้ นอนไม่หลับ?", f, max_w)
    check("trailing ? is not orphaned", "?" not in lines,
          f"-> {lines}")
    check("trailing ? stays attached", lines[-1].endswith("?"),
          f"-> {lines}")

    # 2. Every closing mark in CLOSERS obeys the same rule.
    for mark in M.CLOSERS:
        got = M.wrap(d, "ทดสอบข้อความยาวพอสมควร" + mark, f, max_w)
        check(f"closer {mark!r} not orphaned", mark not in got, f"-> {got}")

    # 3. No text is lost: the join of the lines must equal the input.
    src = "คืนนี้ ถ้าคุณนอนไม่หลับ ลองวางมือบนท้อง"
    got = M.wrap(d, src, f, max_w)
    check("no characters dropped", "".join(got) == src, f"-> {got}")

    # 4. An over-long line is still split (the fix must not disable wrapping).
    got = M.wrap(d, "ก" * 200, f, max_w)
    check("long line still wraps", len(got) > 1, f"-> {len(got)} lines")

    # 5. The real build path produces a valid 9:16 file that passes the gate.
    art = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "assets", "branding", "thumbs")
    base = None
    for name in sorted(os.listdir(art)) if os.path.isdir(art) else []:
        if name.endswith(".jpg"):
            base = os.path.join(art, name)
            break
    if base:
        out = "/tmp/_wrap_check.jpg"
        M.build(base, None, "คืนนี้ นอนไม่หลับ?", out)
        im = Image.open(out)
        check("build is 9:16", (im.width, im.height) == (1080, 1920),
              f"-> {im.size}")
        check("build under 2 MB", os.path.getsize(out) < 2 * 1024 * 1024,
              f"-> {os.path.getsize(out)} bytes")
        os.remove(out)
    else:
        print("  SKIP build check (no art in assets/branding/thumbs)")

    print(f"\n{'FAIL' if FAILS else 'PASS'}: {len(FAILS)} failure(s)")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
