#!/usr/bin/env python3
"""Build a 1280x720 YouTube thumbnail from art + 3-5 big Thai words.

The rule from the growth plan: one focal point, high contrast, and only 3-5
words on the image. Dark blue + gold is the channel's consistent look, so the
same code gives every video a family resemblance.

Usage:
    python3 scripts/make_thumbnail.py --art art.png --out t.jpg \
        --line "หยุดคิด" --line "แล้วพักใจ"
"""
import argparse
import os

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(os.path.dirname(HERE), "assets", "fonts")

W, H = 1280, 720
GOLD = (245, 199, 90)
WHITE = (248, 249, 252)


def font(name, size):
    return ImageFont.truetype(os.path.join(FONTS, name), size)


def cover(im, w, h, bias=0.4):
    r = max(w / im.width, h / im.height)
    im = im.resize((max(w, int(im.width * r)), max(h, int(im.height * r))), Image.LANCZOS)
    left = (im.width - w) // 2
    top = int((im.height - h) * bias)
    return im.crop((left, top, left + w, top + h))


def make(art, out, lines):
    im = cover(Image.open(art).convert("RGB"), W, H)
    im = ImageEnhance.Color(im).enhance(1.12)
    im = ImageEnhance.Contrast(im).enhance(1.1)
    # No lines means no text block: render the graded cover, never raise (the
    # bare max() below would raise on an empty list).
    if not lines:
        im.save(out, quality=92)
        return out

    # bottom-to-top gradient scrim so big text always reads
    scrim = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(scrim)
    for y in range(H):
        d.line([(0, y), (W, y)], fill=int(190 * (y / H) ** 1.4))
    im = Image.composite(Image.new("RGB", (W, H), (4, 8, 20)), im, scrim)

    d = ImageDraw.Draw(im)
    # pick the largest size that fits the longest line
    size = 150
    while size > 60:
        f = font("Kanit-Bold.ttf", size)
        widest = max(d.textbbox((0, 0), ln, font=f)[2] for ln in lines)
        if widest <= W - 120:
            break
        size -= 6
    f = font("Kanit-Bold.ttf", size)

    # stack the lines in the lower third, left-aligned with a gold bar
    heights = [d.textbbox((0, 0), ln, font=f)[3] - d.textbbox((0, 0), ln, font=f)[1]
               for ln in lines]
    gap = int(size * 0.22)
    total = sum(heights) + gap * (len(lines) - 1)
    y = H - 70 - total

    d.rectangle([56, y + 8, 66, y + total - 8], fill=GOLD)
    for ln, hh in zip(lines, heights):
        d.text((92, y), ln, font=f, fill=GOLD if lines.index(ln) == 0 else WHITE,
               stroke_width=4, stroke_fill=(0, 0, 0))
        y += hh + gap

    im.save(out, quality=92)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--art", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--line", action="append", required=True)
    a = ap.parse_args()
    print("wrote", make(a.art, a.out, a.line))


if __name__ == "__main__":
    main()
