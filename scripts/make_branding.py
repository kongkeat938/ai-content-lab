#!/usr/bin/env python3
"""Compose a YouTube banner (2560x1440) and avatar (800x800) from art + Thai text.

YouTube shows only the middle 1546x423 of a banner on TV, 1235x338 on desktop
and 423x423 on mobile, so all text goes inside a centred safe box. The avatar is
cropped to a circle by YouTube, so the subject stays centred.

Usage:
    python3 scripts/make_branding.py --banner-art art.png --avatar-art a.png \
        --out-dir out/ --title "Farmmer" --subtitle "ธรรมะก่อนนอน" \
        --tagline "วางความทุกข์ไว้ตรงนี้ แล้วพักใจให้สบาย"
"""
import argparse
import os

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(os.path.dirname(HERE), "assets", "fonts")

BANNER_W, BANNER_H = 2560, 1440


def font(name, size):
    return ImageFont.truetype(os.path.join(FONTS, name), size)


def cover(im, w, h, bias=0.45):
    r = max(w / im.width, h / im.height)
    im = im.resize((max(w, int(im.width * r)), max(h, int(im.height * r))), Image.LANCZOS)
    left = (im.width - w) // 2
    top = int((im.height - h) * bias)
    return im.crop((left, top, left + w, top + h))


def text_size(draw, txt, f):
    l, t, r, b = draw.textbbox((0, 0), txt, font=f)
    return r - l, b - t


def banner(art, out, title, subtitle, tagline):
    im = cover(Image.open(art).convert("RGB"), BANNER_W, BANNER_H)
    im = ImageEnhance.Brightness(im).enhance(0.6)

    # vignette: keeps the centre calm so the text always reads
    vig = Image.new("L", (BANNER_W, BANNER_H), 0)
    ImageDraw.Draw(vig).ellipse(
        [-BANNER_W // 3, -BANNER_H // 3, BANNER_W + BANNER_W // 3,
         BANNER_H + BANNER_H // 3], fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(180))
    im = Image.composite(im, Image.new("RGB", im.size, (6, 10, 24)), vig)

    d = ImageDraw.Draw(im)
    cx = BANNER_W // 2
    f_title = font("Kanit-Bold.ttf", 150)
    f_sub = font("Prompt-SemiBold.ttf", 72)
    f_tag = font("Prompt-Regular.ttf", 50)
    gold, white = (240, 199, 106), (245, 246, 250)

    # YouTube only guarantees the centre 1235x338; centre the whole block there.
    GAP1, GAP2, GAP3 = 52, 42, 42
    tw, th = text_size(d, title, f_title)
    sw, sh = text_size(d, subtitle, f_sub)
    gw, gh = text_size(d, tagline, f_tag)
    block_h = th + GAP1 + sh + GAP2 + 6 + GAP3 + gh
    y = (BANNER_H - block_h) // 2

    d.text((cx - tw // 2, y), title, font=f_title, fill=gold)
    y += th + GAP1
    d.text((cx - sw // 2, y), subtitle, font=f_sub, fill=white)
    y += sh + GAP2
    d.rectangle([cx - 150, y, cx + 150, y + 6], fill=gold)
    y += 6 + GAP3
    d.text((cx - gw // 2, y), tagline, font=f_tag, fill=(214, 220, 235))

    im.save(out, quality=92)
    return out


def avatar(art, out):
    im = cover(Image.open(art).convert("RGB"), 800, 800, bias=0.5)
    ImageEnhance.Contrast(im).enhance(1.06).save(out, quality=95)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--banner-art", required=True)
    ap.add_argument("--avatar-art", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--subtitle", required=True)
    ap.add_argument("--tagline", required=True)
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)
    print("wrote", banner(a.banner_art, os.path.join(a.out_dir, "banner_2560x1440.jpg"),
                         a.title, a.subtitle, a.tagline))
    print("wrote", avatar(a.avatar_art, os.path.join(a.out_dir, "avatar_800x800.jpg")))


if __name__ == "__main__":
    main()
