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
    """
    im = ImageEnhance.Color(im).enhance(1.35)
    im = ImageEnhance.Contrast(im).enhance(1.10)
    px = im.load()
    for y in range(0, im.height, 2):               # step 2 for speed
        for x in range(0, im.width, 2):
            r, g, b = px[x, y]
            lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255.0
            # shadows -> teal, highlights -> orange
            r = int(max(0, min(255, r + (lum - 0.5) * 22)))
            b = int(max(0, min(255, b - (lum - 0.5) * 22)))
            g = int(max(0, min(255, g + (lum - 0.5) * 3)))
            px[x, y] = (r, g, b)
    return im


def vignette(im: Image.Image, strength: float = 0.85) -> Image.Image:
    """Radial darkening, built once per size and reused as a mask."""
    mask = Image.new("L", (im.width, im.height), 0)
    d = ImageDraw.Draw(mask)
    cx, cy = im.width / 2, im.height / 2
    maxd = math.hypot(cx, cy)
    step = 6
    for y in range(0, im.height, step):
        for x in range(0, im.width, step):
            dist = math.hypot(x - cx, y - cy) / maxd
            v = int(255 * min(1.0, max(0.0, (dist - 0.30) / 0.70)) * strength)
            d.rectangle([x, y, x + step, y + step], fill=v)
    mask = mask.filter(ImageFilter.GaussianBlur(60))
    dark = Image.new("RGB", im.size, (0, 0, 0))
    return Image.composite(dark, im, mask)


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


def wrap_lines(d: ImageDraw.ImageDraw, text: str, f: ImageFont.FreeTypeFont,
               max_w: float) -> list[str]:
    """Greedy character wrap -- Thai has no word spaces, so wrap on characters."""
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
    block_h = t_lh * len(tlines) + (16 + s_lh * len(slines) if slines else 0)
    center_y = int(H * rule_y)
    top = center_y - block_h // 2
    x = W // 2 if side == "center" else (SAFE if side == "left" else W - SAFE)
    return {"side": side, "halign": _halign(side), "x": x, "max_w": max_w,
            "title_lines": tlines, "title_font": ft, "title_size": ts, "title_lh": t_lh,
            "sub_lines": slines, "sub_font": fs, "sub_size": ss, "sub_lh": s_lh,
            "chapter_lines": clines, "chapter_font": fc, "chapter_size": cs,
            "center_y": center_y, "block_h": block_h, "top": top, "bottom": top + block_h}


def build(image_path: str, out: str, title: str, subtitle: str,
          layout: int, chapter: str = "", index: str = "") -> None:
    im = cover(Image.open(image_path).convert("RGB"), W, H)
    im = grade(im)
    im = vignette(im)
    d = ImageDraw.Draw(im, "RGBA")

    lay = text_layout(title, subtitle, layout, chapter)
    x, ha = lay["x"], lay["halign"]
    f_idx = font("Kanit-Bold.ttf", 34)

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
    sy = ty + lay["title_lh"] * len(lay["title_lines"]) + 16
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
