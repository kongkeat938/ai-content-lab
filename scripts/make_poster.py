"""Cinematic poster / title-card generator.

Turns a free photo into a movie-poster-style background card: heavy vignette,
teal-orange grade, letterbox bars, and a Thai display title with an English
subtitle. Layouts are indexed so consecutive cards never look the same.

Usage:
    python make_poster.py <image> <out.jpg> --title "..." --subtitle "..." \
        --layout 3 --text "chapter line"
"""
import argparse
import math
import os
import unicodedata
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(os.path.dirname(HERE), "assets", "fonts")

# 1920x1080 keeps the encode fast; the poster look comes from grading + layout,
# not from resolution.
W, H = 1920, 1080
BAR = 108  # letterbox bar height, poster "cinema" cue


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    path = os.path.join(FONTS, name)
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    return ImageFont.truetype(path, size)


def cover(im: Image.Image, w: int, h: int) -> Image.Image:
    """Scale-and-crop to exactly w x h (like CSS object-fit: cover)."""
    r = max(w / im.width, h / im.height)
    im = im.resize((max(w, int(im.width * r)), max(h, int(im.height * r))), Image.LANCZOS)
    left = (im.width - w) // 2
    top = int((im.height - h) * 0.42)  # bias slightly above centre
    return im.crop((left, top, left + w, top + h))


def grade(im: Image.Image) -> Image.Image:
    """Teal-orange cinematic grade: cool the shadows, warm the highlights.

    Saturation is raised (not lowered) because the vignette and the shadow
    crush both drain colour; reference posters sit around 0.30-0.60.

    Vectorised with numpy (already a declared dependency): the previous
    per-pixel Python loop cost 0.43 s for one 1920x1080 poster, and the rails
    build one per chapter.
    """
    im = ImageEnhance.Color(im).enhance(1.35)
    im = ImageEnhance.Contrast(im).enhance(1.10)
    a = np.asarray(im, dtype=np.float32)
    lum = (0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2]) / 255.0
    shift = (lum - 0.5)[..., None]
    # shadows -> teal, highlights -> orange
    a[..., 0] += shift[..., 0] * 22
    a[..., 2] -= shift[..., 0] * 22
    a[..., 1] += shift[..., 0] * 3
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGB")


@lru_cache(maxsize=8)
def _vignette_mask(w: int, h: int, strength: float) -> Image.Image:
    """The radial mask for one size, built once and reused across posters.

    The docstring below used to claim it was reused; it was not, and a rail builds
    one poster per chapter at the same size, so the same mask was rebuilt each
    time (0.23 s of the 0.53 s per card, measured 2026-11-19).
    """
    mask = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(mask)
    cx, cy = w / 2, h / 2
    maxd = math.hypot(cx, cy)
    step = 6
    for y in range(0, h, step):
        for x in range(0, w, step):
            dist = math.hypot(x - cx, y - cy) / maxd
            v = int(255 * min(1.0, max(0.0, (dist - 0.30) / 0.70)) * strength)
            d.rectangle([x, y, x + step, y + step], fill=v)
    return mask.filter(ImageFilter.GaussianBlur(60))


def vignette(im: Image.Image, strength: float = 0.85) -> Image.Image:
    """Radial darkening, built once per size and reused as a mask."""
    mask = _vignette_mask(im.width, im.height, strength)
    dark = Image.new("RGB", im.size, (0, 0, 0))
    return Image.composite(dark, im, mask)


def scrim(im: Image.Image, top: int, bottom: int, pad: int = 46,
          fill: int = 150) -> Image.Image:
    """A soft dark band behind the text block, so text never sits on a highlight.

    Measured 2026-11-19 by the vision grader on 4 of 10 published clips: Thai
    text over a candle flame was unreadable ("ข้อความทับซ้อนกับแสงเทียน", scored
    5/10 twice). A stroke alone cannot fix that -- a bright, busy background
    needs the text lifted off it, which is what the reference posters do.
    """
    layer = Image.new("L", im.size, 0)
    d = ImageDraw.Draw(layer)
    d.rectangle([0, max(0, top - pad), im.width, min(im.height, bottom + pad)], fill=fill)
    layer = layer.filter(ImageFilter.GaussianBlur(48))
    return Image.composite(Image.new("RGB", im.size, (8, 7, 6)), im, layer)


def draw_text(d: ImageDraw.ImageDraw, xy, text, f, fill, anchor="la",
              shadow=True, shadow_off=(3, 3), stroke=0, stroke_fill=None):
    x, y = xy
    if shadow:
        d.text((x + shadow_off[0], y + shadow_off[1]), text, font=f,
               fill=(0, 0, 0), anchor=anchor,
               stroke_width=stroke, stroke_fill=(0, 0, 0))
    d.text((x, y), text, font=f, fill=fill, anchor=anchor,
           stroke_width=stroke, stroke_fill=stroke_fill)


# Layouts: (title anchor, title size, subtitle size, rule y, block side)
LAYOUTS = [
    ("mm", 132, 44, 0.62, "center"),
    ("lm", 118, 40, 0.58, "left"),
    ("rm", 118, 40, 0.58, "right"),
    ("mm", 156, 50, 0.70, "center"),
    ("lm", 104, 36, 0.52, "left"),
    ("rm", 104, 36, 0.52, "right"),
    ("mm", 176, 54, 0.50, "center"),
    ("lm", 128, 42, 0.72, "left"),
]

# Text is wrapped and shrunk to stay inside this margin. Measured 2026-11-12: a
# single-line title at 176px is 5862px wide against a 1920px frame, so a long title
# ran off both edges -- the real rails pass short titles ("ปรัชญาชีวิต"), so it never
# bit, but nothing stopped it. The same blind spot the Shorts captions had.
SAFE = 130            # min margin from either frame edge, px
TITLE_MAX_LINES = 3
SUB_MAX_LINES = 2


def _halign(side: str) -> str:
    return {"left": "l", "center": "m", "right": "r"}[side]


# Thai vowels that are written BEFORE the consonant they belong to. They must
# never end a line: "โดยไม่ต้องแบกโ" / "ลก" reads as "โลก" split in half. Measured
# 2026-11-19: 276 of the real poster/hook titles in content/ broke this way under
# a plain character wrap, at the sizes the rails actually use.
LEADING_VOWELS = set("เแโใไ")
# Characters that cannot begin a line because they hang off the one before it:
# the following vowels, the repeat mark, and every combining mark (tone marks,
# vowel signs above/below). Measured on the same sweep: after fixing only the
# leading vowels, "ว่" / "าเรา" appeared -- า is a following vowel, not a mark.
NO_LINE_START = set("ะาำๅๆ")


def _starts_a_cluster(ch: str) -> bool:
    """True if `ch` may legally begin a line."""
    if not ch:
        return True
    if unicodedata.category(ch[0]) in ("Mn", "Mc", "Me"):
        return False
    return ch[0] not in NO_LINE_START


def wrap_lines(d: ImageDraw.ImageDraw, text: str, f: ImageFont.FreeTypeFont,
               max_w: float) -> list[str]:
    """Greedy character wrap that breaks only between Thai clusters.

    Thai has no word spaces, so wrapping on characters is right -- but a break is
    only legal between *clusters*. A line may not end with a leading vowel, and the
    next line may not start with a mark or a following vowel; when it would, the
    last cluster moves down instead.
    """
    if not text:
        return []
    lines: list[str] = []
    cur = ""
    for ch in text:
        if ch == "\n":
            lines.append(cur)
            cur = ""
            continue
        if not cur or d.textlength(cur + ch, font=f) <= max_w:
            cur += ch
        else:
            keep = cur
            while keep and (keep[-1] in LEADING_VOWELS or not _starts_a_cluster(ch)):
                ch = keep[-1] + ch
                keep = keep[:-1]
            if keep:
                lines.append(keep)
                cur = ch
            else:
                # One cluster is wider than the frame; breaking it is the lesser
                # evil, and fit_text() will shrink the font until it is not.
                lines.append(cur)
                cur = ch
    if cur or not lines:
        lines.append(cur)
    return lines


def fit_text(d: ImageDraw.ImageDraw, text: str, name: str, size: int,
             max_w: float, max_lines: int, floor: int):
    """Shrink the font until the text wraps into at most `max_lines` lines."""
    s = size
    f = font(name, s)
    lines = wrap_lines(d, text, f, max_w)
    while s > floor and len(lines) > max_lines:
        s -= 4
        f = font(name, s)
        lines = wrap_lines(d, text, f, max_w)
    return f, s, lines


def text_layout(title: str, subtitle: str, layout: int, chapter: str = "") -> dict:
    """Wrapped lines + block geometry for a poster, shared with the guard.

    One source of truth: build() draws exactly this, and the guard measures exactly
    this, so a title that would overflow is caught before it ships.
    """
    _anchor, tsize, ssize, rule_y, side = LAYOUTS[layout % len(LAYOUTS)]
    max_w = W - 2 * SAFE
    d = ImageDraw.Draw(Image.new("L", (W, H)))
    ft, ts, tlines = fit_text(d, title, "Kanit-Bold.ttf", tsize, max_w, TITLE_MAX_LINES, 60)
    fs, ss, slines = fit_text(d, subtitle, "Prompt-Regular.ttf", ssize, max_w, SUB_MAX_LINES, 24)
    if chapter:
        fc, cs, clines = fit_text(d, chapter, "Kanit-Regular.ttf", 30, max_w, 1, 20)
    else:
        fc, cs, clines = None, 0, []
    t_lh = int(ts * 1.22)
    s_lh = int(ss * 1.35)
    # 16px read as cramped under a 156px title (vision grader, 2026-11-19:
    # "ตำแหน่งอยู่ชิดกับหัวข้อมากเกินไป"); the gap scales with the title size.
    gap = max(28, int(ts * 0.26))
    block_h = t_lh * len(tlines) + (gap + s_lh * len(slines) if slines else 0)
    center_y = int(H * rule_y)
    top = center_y - block_h // 2
    x = W // 2 if side == "center" else (SAFE if side == "left" else W - SAFE)
    return {"side": side, "halign": _halign(side), "x": x, "max_w": max_w,
            "title_lines": tlines, "title_font": ft, "title_size": ts, "title_lh": t_lh,
            "sub_lines": slines, "sub_font": fs, "sub_size": ss, "sub_lh": s_lh,
            "chapter_lines": clines, "chapter_font": fc, "chapter_size": cs,
            "center_y": center_y, "block_h": block_h, "top": top, "bottom": top + block_h,
            "gap": gap}


def build(image_path: str, out: str, title: str, subtitle: str,
          layout: int, chapter: str = "", index: str = "") -> None:
    try:
        src = Image.open(image_path)
        src.load()
    except (OSError, ValueError) as exc:
        # A corrupt or non-image source is a content problem, and the rails call
        # this per chapter: name the file instead of dying inside Pillow.
        raise SystemExit(f"make_poster: cannot read {image_path}: {exc}") from exc
    im = cover(src.convert("RGB"), W, H)
    im = grade(im)
    im = vignette(im)

    lay = text_layout(title, subtitle, layout, chapter)
    x, ha = lay["x"], lay["halign"]
    f_idx = font("Kanit-Bold.ttf", 34)

    im = scrim(im, lay["top"], lay["bottom"])
    d = ImageDraw.Draw(im, "RGBA")

    # letterbox bars
    d.rectangle([0, 0, W, BAR], fill=(0, 0, 0))
    d.rectangle([0, H - BAR, W, H], fill=(0, 0, 0))

    # short rule above the title block
    ry = lay["top"] - 34
    if ha == "m":
        d.line([(x - 90, ry), (x + 90, ry)], fill=(212, 175, 95, 220), width=3)
    elif ha == "l":
        d.line([(x, ry), (x + 180, ry)], fill=(212, 175, 95, 220), width=3)
    else:
        d.line([(x - 180, ry), (x, ry)], fill=(212, 175, 95, 220), width=3)

    ty = lay["top"]
    for i, ln in enumerate(lay["title_lines"]):
        draw_text(d, (x, ty + i * lay["title_lh"] + lay["title_lh"] // 2), ln,
                  lay["title_font"], (247, 243, 236), anchor=f"{ha}m",
                  stroke=2, stroke_fill=(10, 8, 6))
    sy = ty + lay["title_lh"] * len(lay["title_lines"]) + lay["gap"]
    for i, ln in enumerate(lay["sub_lines"]):
        draw_text(d, (x, sy + i * lay["sub_lh"] + lay["sub_lh"] // 2), ln,
                  lay["sub_font"], (198, 190, 178), anchor=f"{ha}m")

    if lay["chapter_lines"]:
        for ln in lay["chapter_lines"]:
            draw_text(d, (x, H - BAR - 44), ln, lay["chapter_font"],
                      (170, 164, 154), anchor=f"{ha}m")

    if index:
        d.text((W - 60, 34), index, font=f_idx, fill=(212, 175, 95), anchor="ra")

    # subtle film grain so flat photos do not look like plain slides
    noise = Image.effect_noise((W, H), 12).convert("L")
    im = Image.composite(Image.new("RGB", (W, H), (255, 255, 255)), im,
                         noise.point(lambda v: 18 if v > 200 else 0))

    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    im.save(out, quality=92, subsampling=1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("out")
    ap.add_argument("--title", required=True)
    ap.add_argument("--subtitle", default="")
    ap.add_argument("--chapter", default="")
    ap.add_argument("--index", default="")
    ap.add_argument("--layout", type=int, default=0)
    a = ap.parse_args()
    build(a.image, a.out, a.title, a.subtitle, a.layout, a.chapter, a.index)
    print(f"poster -> {a.out}")


if __name__ == "__main__":
    main()
