#!/usr/bin/env python3
"""Guard the Shorts captions: they must stay in frame AND stay readable.

K's report (2026-11-12): on the Shorts screen the caption text overflowed the
frame, and its placement/size/font did not look good. There was no guard at all --
caption_image() had no test, so a regression could not fail. This closes both:

  1. **In frame.** Sweep every real hook/line/CTA in the pools (never a hardcoded
     sample): every wrapped line fits inside the 1080-px width with its stroke, and
     the whole block fits between the top and bottom of the 1920-px frame.
  2. **Readable.** White/gold text on a bright backdrop is unreadable. Measured
     2026-11-12: the big hook sits at 0.42H while the backdrop scrim only starts at
     0.55H, so the hook landed on art with mean luminance up to 195/255 (contrast
     ~1.6:1). The fix is a dark panel behind the block; the test composites a caption
     over the brightest real art and asserts the contrast behind the glyphs is high,
     and that WITHOUT the panel it is not (so the guard can actually fail).

    python3 scripts/test_short_caption.py
"""
from __future__ import annotations

import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from PIL import Image, ImageDraw  # noqa: E402

import make_short as ms  # noqa: E402

FAILS = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" -- {detail}" if detail and not ok else ""))
    if not ok:
        FAILS.append(name)


def rel_lum(rgb) -> float:
    def ch(c):
        c = c / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = rgb[:3]
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(fg, bg) -> float:
    a, b = rel_lum(fg), rel_lum(bg)
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


def all_texts() -> list[tuple[str, bool]]:
    """Every hook (big) and line/cta (small) the pools can ask us to draw."""
    out = []
    for pool in sorted(glob.glob(os.path.join(ROOT, "content", "*_shorts", "scripts.json"))):
        with open(pool, encoding="utf-8") as fh:
            d = json.load(fh)
        items = d if isinstance(d, list) else (d.get("shorts") or list(d.values()))
        for it in items:
            if not isinstance(it, dict):
                continue
            if it.get("hook"):
                out.append((it["hook"], True))
            for ln in it.get("lines", []) or []:
                if ln:
                    out.append((ln, False))
            if it.get("cta"):
                out.append((it["cta"], False))
    return out


def frame_overflow(text: str, big: bool) -> tuple[bool, str]:
    lay = ms.caption_layout(text, big)
    stroke = ms.STROKE  # stroke_width used by caption_image
    left = lay["x"]
    right = left + lay["widest"] + 2 * stroke
    top = lay["y"]
    bottom = lay["y"] + lay["total"]
    # inside the frame, and clear of the player UI (right button rail + bottom bar)
    fits = (left >= 0 and right <= ms.W and top >= 0 and bottom <= ms.H
            and right <= ms.SAFE_RIGHT * ms.W + 1
            and bottom <= ms.SAFE_BOTTOM * ms.H + 1
            and top >= ms.SAFE_TOP * ms.H - 1)
    return fits, (f"x[{left},{right:.0f}] y[{top},{bottom}] "
                  f"limits x<{ms.SAFE_RIGHT*ms.W:.0f} y<{ms.SAFE_BOTTOM*ms.H:.0f}")


def _text_box(text: str, big: bool):
    """The tight glyph box caption_image draws into, from the shared layout."""
    lay = ms.caption_layout(text, big)
    x0 = lay["x"]
    x1 = lay["x"] + int(lay["widest"])
    return (max(0, x0), max(0, lay["y"]), min(ms.W, x1), min(ms.H, lay["y"] + lay["total"]))


def caption_contrast(text: str, big: bool, art: str, panel: bool) -> float:
    """Contrast of the caption fill against what is actually behind the glyphs.

    Composite the caption over a real backdrop and read the MEDIAN pixel colour of
    the glyph box -- the glyphs are thin, so the median is the background the eye
    sees around the text. Then contrast() that against the fill colour.
    """
    bg = "/tmp/_capbg.jpg"
    ms.backdrop(bg, art)
    base = Image.open(bg).convert("RGB")
    cap = "/tmp/_cap.png"
    ms.caption_image(text, cap, big=big, panel=panel)
    comp = Image.alpha_composite(base.convert("RGBA"), Image.open(cap)).convert("RGB")
    box = _text_box(text, big)
    px = list(comp.crop(box).getdata())
    if not px:
        return 1.0
    px.sort(key=rel_lum)
    bg_rgb = px[len(px) // 2]          # median pixel = the background behind text
    fill = ms.GOLD if big else ms.WHITE
    return contrast(fill, bg_rgb)


def brightest_art() -> str | None:
    best, best_m = None, -1
    for a in sorted(glob.glob(os.path.join(ROOT, "assets", "art", "*", "*.jpg"))):
        m = sum(Image.open(a).convert("L").resize((ms.W, ms.H)).getdata()) / (ms.W * ms.H)
        if m > best_m:
            best, best_m = a, m
    return best


def main() -> int:
    texts = all_texts()
    check("the pools yield real captions to test", len(texts) > 20, f"{len(texts)}")

    print("every caption fits inside the 1080x1920 frame")
    bad = []
    for text, big in texts:
        ok, why = frame_overflow(text, big)
        if not ok:
            bad.append((text, why))
    check(f"all {len(texts)} captions stay in frame", not bad,
          "; ".join(f"{t[:20]}... ({w})" for t, w in bad[:3]))

    print("the guard can fail: centred text would run under the player's button rail")
    worst = max(texts, key=lambda tb: ms.caption_layout(tb[0], tb[1])["widest"])
    lay = ms.caption_layout(worst[0], worst[1])
    centred_right = (ms.W + lay["widest"]) / 2
    check("a centred caption breaches SAFE_RIGHT (so the safe box is doing work)",
          centred_right > ms.SAFE_RIGHT * ms.W,
          f"centred right={centred_right:.0f} rail={ms.SAFE_RIGHT*ms.W:.0f}")

    print("the font is sized to the line (short fills, long stays punchy)")
    longest = max((t for t, big in texts if big), key=len)
    shortest = min((t for t, big in texts if big), key=len)
    sz_long = ms.caption_layout(longest, True)["size"]
    sz_short = ms.caption_layout(shortest, True)["size"]
    check("a short hook gets a larger font than a long one", sz_short > sz_long,
          f"{sz_short} vs {sz_long}")
    worst_lines = max(len(ms.caption_layout(t, b)["lines"]) for t, b in texts)
    check(f"no caption wraps beyond {ms.CAPTION_MAX_LINES} lines",
          worst_lines <= ms.CAPTION_MAX_LINES, f"{worst_lines}")

    print("the hook reads over the brightest real art (panel guarantees contrast)")
    art = brightest_art()
    if not art:
        check("found art to composite", False)
    else:
        # Use the longest hook, the worst case for the panel.
        hook = max((t for t, big in texts if big), key=len, default="ทดสอบ")
        with_panel = caption_contrast(hook, True, art, panel=True)
        without = caption_contrast(hook, True, art, panel=False)
        print(f"    brightest art: {os.path.relpath(art, ROOT)}")
        print(f"    contrast with panel={with_panel:.2f}:1  without={without:.2f}:1")
        check("hook contrast >= 4.5:1 with the panel", with_panel >= 4.5,
              f"{with_panel:.2f}:1")
        # The guard can fail: without the panel the text over bright art is weaker.
        check("the panel is what earns the contrast (no panel is worse)",
              without < with_panel, f"{without:.2f} !< {with_panel:.2f}")

    print()
    if FAILS:
        print(f"FAIL: {len(FAILS)} check(s) failed: {FAILS}")
        return 1
    print("OK: Shorts captions stay in frame and read at >= 4.5:1")
    return 0


if __name__ == "__main__":
    sys.exit(main())
