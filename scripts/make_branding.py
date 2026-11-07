#!/usr/bin/env python3
"""Compose a YouTube banner (2560x1440) and avatar (800x800) from art + Thai text.

YouTube shows only the middle 1546x423 of a banner on TV, 1235x338 on desktop
and 423x423 on mobile, so all text goes inside a centred safe box. The avatar is
cropped to a circle by YouTube, so the subject stays centred.

Two looks:
  * `--style lavish` (default) -- a cinematic poster: warm colour grade, a
    spotlight that brightens the centre and sinks the edges, a gold ornamental
    frame with corner flourishes, the title in gold with a soft glow and a dark
    stroke, a gold diamond divider, and a light film grain.
  * `--style classic` -- the original flat composition, kept for compatibility.

Everything is Pillow + numpy; no paid tool and no generative model.

Usage:
    python3 scripts/make_branding.py --banner-art art.jpg --avatar-art a.jpg \
        --out-dir out/ --title "เรื่องเล่าอบอุ่นใจ" \
        --kicker "รวมเรื่องเล่าครอบครัวไทย" \
        --subtitle "ฟังเพลินทั้งคืน · เสียงนุ่ม ๆ ก่อนนอน"
"""
from __future__ import annotations

import argparse
import os

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(os.path.dirname(HERE), "assets", "fonts")

BANNER_W, BANNER_H = 2560, 1440
GOLD = (243, 205, 116)
GOLD_DEEP = (196, 150, 58)
WHITE = (247, 248, 252)
SOFT = (222, 228, 240)
INK = (18, 11, 4)


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(os.path.join(FONTS, name), size)


def cover(im: Image.Image, w: int, h: int, bias: float = 0.45) -> Image.Image:
    r = max(w / im.width, h / im.height)
    im = im.resize((max(w, int(im.width * r)), max(h, int(im.height * r))), Image.LANCZOS)
    left = (im.width - w) // 2
    top = int((im.height - h) * bias)
    return im.crop((left, top, left + w, top + h))


def radial_mask(w: int, h: int, inner: float = 0.30, power: float = 1.35) -> Image.Image:
    """A soft centre-weighted mask: 255 at the middle, 0 at the edges."""
    yy, xx = np.mgrid[0:h, 0:w]
    cx, cy = w / 2.0, h / 2.0
    rx, ry = w * 0.55, h * 0.55
    r = np.sqrt(((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2)
    m = np.clip(1.0 - r, 0.0, 1.0) ** power
    m = np.clip(m + inner * (m > 0.02), 0.0, 1.0)
    return Image.fromarray((m * 255).astype(np.uint8), "L").filter(ImageFilter.GaussianBlur(40))


def warm_grade(im: Image.Image) -> Image.Image:
    """A warm, slightly faded film look: lift warmth, pull the blues down."""
    im = ImageEnhance.Color(im).enhance(1.18)
    im = ImageEnhance.Contrast(im).enhance(1.08)
    warm = Image.new("RGB", im.size, (255, 176, 92))
    im = Image.blend(im, warm, 0.12)
    a = np.asarray(im).astype(np.float32)
    a[..., 2] *= 0.94          # cool the blues
    a[..., 0] *= 1.03          # lift the reds
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGB")


def film_grain(im: Image.Image, amount: float = 5.0) -> Image.Image:
    a = np.asarray(im).astype(np.float32)
    n = np.random.default_rng(7).normal(0, amount, a.shape[:2])[..., None]
    return Image.fromarray(np.clip(a + n, 0, 255).astype(np.uint8), "RGB")


def letterspaced(draw: ImageDraw.ImageDraw, txt: str, f, sp: int) -> int:
    return int(sum(draw.textlength(ch, font=f) for ch in txt) + sp * (len(txt) - 1))


def draw_centered_ls(draw, cx, y, txt, f, fill, sp):
    x = cx - letterspaced(draw, txt, f, sp) / 2
    for ch in txt:
        draw.text((x, y), ch, font=f, fill=fill)
        x += draw.textlength(ch, font=f) + sp


def glow_text(base: Image.Image, cx, y, txt, f, fill, stroke_w, glow=GOLD) -> None:
    """Gold text with a dark stroke and a soft glow, centred on cx."""
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    w = d.textlength(txt, font=f)
    d.text((cx - w / 2, y), txt, font=f, fill=glow + (255,))
    halo = layer.filter(ImageFilter.GaussianBlur(26))
    base.alpha_composite(halo)
    base.alpha_composite(halo)
    d = ImageDraw.Draw(base)
    d.text((cx - w / 2, y), txt, font=f, fill=fill,
           stroke_width=stroke_w, stroke_fill=INK)


def ornament(d: ImageDraw.ImageDraw, box) -> None:
    """A double gold rule with corner flourishes, drawn on a box.

    The box is the TV-visible band (1546x423 centred), not the canvas edge: on a
    2560x1440 banner the desktop crop is only 1235x338, so anything pinned to the
    canvas edge is never seen. Ornament inside the TV band is visible on TV and
    clipped only as decoration on desktop and mobile.
    """
    x0, y0, x1, y1 = box
    for off, col, wid in ((0, GOLD_DEEP, 6), (18, GOLD, 3)):
        d.rectangle([x0 + off, y0 + off, x1 - off, y1 - off], outline=col, width=wid)
    L = 120
    for x, y, sx, sy in ((x0, y0, 1, 1), (x1, y0, -1, 1),
                         (x0, y1, 1, -1), (x1, y1, -1, -1)):
        d.line([x, y, x + sx * L, y], fill=GOLD, width=8)
        d.line([x, y, x, y + sy * L], fill=GOLD, width=8)
        d.ellipse([x - 10, y - 10, x + 10, y + 10], fill=GOLD)
    mx, my = (x0 + x1) // 2, (y0 + y1) // 2
    for x, y in ((mx, y0), (mx, y1), (x0, my), (x1, my)):
        d.polygon([(x, y - 14), (x + 14, y), (x, y + 14), (x - 14, y)], fill=GOLD)


def banner(art: str, out: str, title: str, kicker: str, subtitle: str,
           style: str = "lavish") -> str:
    im = cover(Image.open(art).convert("RGB"), BANNER_W, BANNER_H)
    if style == "classic":
        im = ImageEnhance.Brightness(im).enhance(0.6)
        vig = Image.new("L", (BANNER_W, BANNER_H), 0)
        ImageDraw.Draw(vig).ellipse(
            [-BANNER_W // 3, -BANNER_H // 3, BANNER_W + BANNER_W // 3,
             BANNER_H + BANNER_H // 3], fill=255)
        vig = vig.filter(ImageFilter.GaussianBlur(180))
        im = Image.composite(im, Image.new("RGB", im.size, (6, 10, 24)), vig)
        d = ImageDraw.Draw(im)
        cx = BANNER_W // 2
        ft, fs, fg = font("Kanit-Bold.ttf", 150), font("Prompt-SemiBold.ttf", 72), font("Prompt-Regular.ttf", 50)
        tw = d.textlength(title, font=ft)
        sw = d.textlength(subtitle, font=fs)
        gw = d.textlength(kicker, font=fg)
        y = BANNER_H // 2 - 150
        d.text((cx - tw / 2, y), title, font=ft, fill=GOLD)
        d.text((cx - sw / 2, y + 200), subtitle, font=fs, fill=WHITE)
        d.rectangle([cx - 150, y + 320, cx + 150, y + 326], fill=GOLD)
        d.text((cx - gw / 2, y + 380), kicker, font=fg, fill=SOFT)
        im.save(out, quality=92)
        return out

    im = warm_grade(im)
    im = ImageEnhance.Brightness(im).enhance(0.80)
    # spotlight: brighten the centre, then sink the edges into a warm dark
    glow = ImageEnhance.Brightness(im).enhance(1.55)
    im = Image.composite(glow, im, radial_mask(BANNER_W, BANNER_H))
    dark = ImageEnhance.Brightness(im).enhance(0.32)
    inv = Image.fromarray(255 - np.asarray(radial_mask(BANNER_W, BANNER_H, power=1.7)))
    im = Image.composite(dark, im, inv)
    im = im.convert("RGBA")

    cx = BANNER_W // 2
    f_kick = font("Prompt-SemiBold.ttf", 46)
    f_title = font("Kanit-Bold.ttf", 124)
    f_sub = font("Prompt-SemiBold.ttf", 56)

    # The text block must fit the desktop-safe band (1235x338, y 551..889), or
    # YouTube's header overlay clips it. Sizes above are chosen to fit that band.
    probe = ImageDraw.Draw(im)
    th = probe.textbbox((0, 0), title, font=f_title)[3]
    sh = probe.textbbox((0, 0), subtitle, font=f_sub)[3]
    kh = probe.textbbox((0, 0), kicker, font=f_kick)[3]
    g1, g2, g3 = 12, 20, 16
    block = kh + g1 + th + g2 + 12 + g3 + sh
    y = (BANNER_H - block) // 2

    draw_centered_ls(ImageDraw.Draw(im), cx, y, f"\u2726 {kicker} \u2726", f_kick, GOLD, 8)
    y += kh + g1
    glow_text(im, cx, y, title, f_title, GOLD, 6)
    y += th + g2
    d = ImageDraw.Draw(im)
    d.line([cx - 210, y + 6, cx - 28, y + 6], fill=GOLD, width=4)
    d.line([cx + 28, y + 6, cx + 210, y + 6], fill=GOLD, width=4)
    d.polygon([(cx, y - 5), (cx + 13, y + 6), (cx, y + 17), (cx - 13, y + 6)], fill=GOLD)
    y += 12 + g3
    d.text((cx - d.textlength(subtitle, font=f_sub) / 2, y), subtitle, font=f_sub, fill=WHITE)

    # ornament on the TV-visible band, so it is actually seen
    ornament(d, (500, 500, 2060, 940))
    film_grain(im.convert("RGB")).save(out, quality=94)
    return out


def avatar(art: str, out: str, style: str = "lavish") -> str:
    im = cover(Image.open(art).convert("RGB"), 800, 800, bias=0.5)
    if style == "classic":
        ImageEnhance.Contrast(im).enhance(1.06).save(out, quality=95)
        return out
    im = warm_grade(im)
    im = ImageEnhance.Contrast(im).enhance(1.10)
    im = im.convert("RGBA")
    d = ImageDraw.Draw(im)
    # gold ring just inside the circle YouTube crops to
    d.ellipse([26, 26, 774, 774], outline=GOLD, width=10)
    d.ellipse([44, 44, 756, 756], outline=GOLD_DEEP, width=4)
    film_grain(im.convert("RGB")).save(out, quality=95)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--banner-art", required=True)
    ap.add_argument("--avatar-art", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--subtitle", required=True)
    ap.add_argument("--kicker", default="")
    ap.add_argument("--tagline", default="", help="alias for --kicker (classic look)")
    ap.add_argument("--style", choices=("lavish", "classic"), default="lavish")
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)
    kicker = a.kicker or a.tagline
    print("wrote", banner(a.banner_art, os.path.join(a.out_dir, "banner_2560x1440.jpg"),
                         a.title, kicker, a.subtitle, a.style))
    print("wrote", avatar(a.avatar_art, os.path.join(a.out_dir, "avatar_800x800.jpg"), a.style))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
