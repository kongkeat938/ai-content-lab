#!/usr/bin/env python3
"""Compose a YouTube banner (2560x1440) and avatar (800x800) from art + Thai text.

YouTube shows only the middle 1546x423 of a banner on TV, 1235x338 on desktop
and 423x423 on mobile, so all text goes inside a centred safe box. The avatar is
cropped to a circle by YouTube, so the subject stays centred.

Every banner is a BRIGHT background with DARK type -- a dark background is never
used on any channel (K, 2026-11-07: "do not make dark backgrounds again"). Two
compositions:
  * `--style lavish` (default) -- a cinematic poster: warm colour grade, a bright
    centre that falls off to the edges, a bronze ornamental frame with corner
    flourishes, the title in espresso with a cream halo, a bronze diamond
    divider, and a light film grain.
  * `--style classic` -- the original flat composition, also bright with dark type.
  * `--style knowledge` -- ch4's post-pivot look (2026-11-16): drawn flat, no photo.
    A bright blue->cream gradient, faint geometry, a minimal light-bulb-with-"?"
    mark, deep-navy type and an amber accent. `--banner-art`/`--avatar-art` are not
    needed for this style.

Everything is Pillow + numpy; no paid tool and no generative model.

Usage:
    python3 scripts/make_branding.py --banner-art art.jpg --avatar-art a.jpg \
        --out-dir out/ --title "เกร็ดความรู้รอบตัว" \
        --kicker "เกร็ดน่ารู้รอบตัว" \
        --subtitle "ไขคำถามคาใจ · ฟังเพลินได้ทุกวัน"
"""
from __future__ import annotations

import argparse
import math
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
INK_DARK = (14, 9, 3)      # espresso type, for a bright background
CREAM = (252, 243, 220)     # light halo/stroke behind dark type
BRONZE = (122, 86, 26)      # ornament that reads on a bright background

# "knowledge" style (ch4 pivot, 2026-11-16) -- panel-designed flat look:
# bright background, deep-navy type, amber accent. No photo needed.
KN_BG_TOP = (233, 242, 247)     # crisp light blue
KN_BG_BOT = (255, 250, 240)     # warm cream
KN_NAVY = (10, 25, 47)          # #0A192F type + icon
KN_AMBER = (255, 111, 0)        # #FF6F00 accent / "?"
KN_SOFT = (223, 230, 240)       # faint geometry on the bright field


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


def draw_centered_ls(draw, cx, y, txt, f, fill, sp, stroke_w=0, stroke_fill=INK):
    x = cx - letterspaced(draw, txt, f, sp) / 2
    for ch in txt:
        draw.text((x, y), ch, font=f, fill=fill,
                  stroke_width=stroke_w, stroke_fill=stroke_fill)
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


def ornament(d: ImageDraw.ImageDraw, box, col=GOLD) -> None:
    """A double gold rule with corner flourishes, drawn on a box.

    The box is the TV-visible band (1546x423 centred), not the canvas edge: on a
    2560x1440 banner the desktop crop is only 1235x338, so anything pinned to the
    canvas edge is never seen. Ornament inside the TV band is visible on TV and
    clipped only as decoration on desktop and mobile.
    """
    x0, y0, x1, y1 = box
    for off, c, wid in ((0, col, 6), (18, col, 3)):
        d.rectangle([x0 + off, y0 + off, x1 - off, y1 - off], outline=c, width=wid)
    L = 120
    for x, y, sx, sy in ((x0, y0, 1, 1), (x1, y0, -1, 1),
                         (x0, y1, 1, -1), (x1, y1, -1, -1)):
        d.line([x, y, x + sx * L, y], fill=col, width=8)
        d.line([x, y, x, y + sy * L], fill=col, width=8)
        d.ellipse([x - 10, y - 10, x + 10, y + 10], fill=col)
    mx, my = (x0 + x1) // 2, (y0 + y1) // 2
    for x, y in ((mx, y0), (mx, y1), (x0, my), (x1, my)):
        d.polygon([(x, y - 14), (x + 14, y), (x, y + 14), (x - 14, y)], fill=col)



def kn_background(w: int, h: int) -> Image.Image:
    """A bright vertical gradient with faint geometry -- no photo required."""
    top, bot = np.array(KN_BG_TOP, np.float32), np.array(KN_BG_BOT, np.float32)
    t = np.linspace(0.0, 1.0, h, dtype=np.float32)[:, None, None]
    arr = top[None, None, :] * (1 - t) + bot[None, None, :] * t
    arr = np.repeat(arr, w, axis=1)
    im = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")
    d = ImageDraw.Draw(im, "RGBA")
    for i, (cx, cy, r) in enumerate(((w * 0.14, h * 0.20, h * 0.42),
                                     (w * 0.88, h * 0.80, h * 0.50),
                                     (w * 0.72, h * 0.16, h * 0.22))):
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=KN_SOFT + (110,), width=6)
    d.ellipse([w * 0.06 - h * 0.10, h * 0.86 - h * 0.10, w * 0.06 + h * 0.10, h * 0.86 + h * 0.10],
              fill=KN_AMBER + (28,))
    return im


def kn_bulb(draw: ImageDraw.ImageDraw, cx: float, cy: float, scale: float,
            bulb=KN_AMBER, mark=KN_NAVY) -> None:
    """A minimal light-bulb with a question mark: the "idea / knowledge" mark."""
    r = scale
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=bulb)
    # the neck + base
    bw, bh = r * 0.62, r * 0.44
    draw.rounded_rectangle([cx - bw / 2, cy + r * 0.74, cx + bw / 2, cy + r * 0.74 + bh],
                           radius=int(r * 0.12), fill=bulb)
    for k in range(3):
        yy = cy + r * 0.80 + k * bh * 0.30
        draw.line([cx - bw * 0.42, yy, cx + bw * 0.42, yy], fill=mark, width=max(3, int(r * 0.05)))
    f = font("Kanit-Bold.ttf", int(r * 1.18))
    tb = draw.textbbox((0, 0), "?", font=f)
    draw.text((cx - (tb[2] - tb[0]) / 2 - tb[0], cy - (tb[3] - tb[1]) / 2 - tb[1]), "?", font=f, fill=mark)


def knowledge_banner(title: str, subtitle: str, kicker: str, out: str) -> str:
    im = kn_background(BANNER_W, BANNER_H).convert("RGBA")
    cx = BANNER_W // 2
    f_kick = font("Prompt-SemiBold.ttf", 48)
    f_title = font("Kanit-Bold.ttf", 132)
    f_sub = font("Prompt-SemiBold.ttf", 60)
    probe = ImageDraw.Draw(im)
    th = probe.textbbox((0, 0), title, font=f_title)[3]
    sh = probe.textbbox((0, 0), subtitle, font=f_sub)[3]
    kh = probe.textbbox((0, 0), kicker, font=f_kick)[3]
    g1, g2, rule = 22, 30, 18
    block = kh + g1 + th + g2 + rule + sh
    y = (BANNER_H - block) // 2
    if kicker:
        draw_centered_ls(probe, cx, y, kicker, f_kick, KN_AMBER, 10)
        y += kh + g1
    tw = probe.textlength(title, font=f_title)
    im.alpha_composite(_with_halo(title, f_title, KN_NAVY, (255, 255, 255), cx, y))
    y += th + g2
    d = ImageDraw.Draw(im)
    d.line([cx - 220, y + 8, cx - 34, y + 8], fill=KN_AMBER, width=6)
    d.line([cx + 34, y + 8, cx + 220, y + 8], fill=KN_AMBER, width=6)
    d.ellipse([cx - 12, y - 4, cx + 12, y + 20], fill=KN_NAVY)
    y += rule
    d.text((cx - d.textlength(subtitle, font=f_sub) / 2, y), subtitle, font=f_sub,
           fill=KN_NAVY, stroke_width=2, stroke_fill=(255, 255, 255))
    # icon tucked in the safe band, left of the copy
    kn_bulb(d, cx - tw / 2 - 150, BANNER_H // 2 - 10, 92)
    im.convert("RGB").save(out, quality=94)
    return out


def _with_halo(txt: str, f, fill, halo, cx, y) -> Image.Image:
    layer = Image.new("RGBA", (BANNER_W, BANNER_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    w = d.textlength(txt, font=f)
    d.text((cx - w / 2, y), txt, font=f, fill=halo + (255,), stroke_width=10, stroke_fill=halo + (255,))
    layer = layer.filter(ImageFilter.GaussianBlur(14))
    d = ImageDraw.Draw(layer)
    d.text((cx - w / 2, y), txt, font=f, fill=fill + (255,))
    return layer


def knowledge_avatar(out: str, title: str = "") -> str:
    im = kn_background(800, 800).convert("RGBA")
    d = ImageDraw.Draw(im, "RGBA")
    # the circle YouTube crops to: keep the bulb well inside it (icon-only, per panel)
    d.ellipse([140, 140, 660, 660], fill=(255, 255, 255, 210))
    d.ellipse([140, 140, 660, 660], outline=KN_NAVY, width=9)
    kn_bulb(d, 400, 380, 128, bulb=KN_AMBER, mark=KN_NAVY)
    im.convert("RGB").save(out, quality=95)
    return out

def banner(art: str, out: str, title: str, kicker: str, subtitle: str,
           style: str = "lavish") -> str:
    im = cover(Image.open(art).convert("RGB"), BANNER_W, BANNER_H)
    if style == "classic":
        # Bright background, dark type. A dark background is never used on any
        # channel (K, 2026-11-07: "do not make dark backgrounds again").
        im = ImageEnhance.Brightness(im).enhance(1.15)
        d = ImageDraw.Draw(im)
        cx = BANNER_W // 2
        ft, fs, fg = font("Kanit-Bold.ttf", 150), font("Prompt-SemiBold.ttf", 72), font("Prompt-Regular.ttf", 50)
        tw, sw, gw = (d.textlength(t, font=f) for t, f in ((title, ft), (subtitle, fs), (kicker, fg)))
        y = BANNER_H // 2 - 150
        d.text((cx - tw / 2, y), title, font=ft, fill=INK_DARK, stroke_width=4, stroke_fill=CREAM)
        d.text((cx - sw / 2, y + 200), subtitle, font=fs, fill=INK_DARK, stroke_width=3, stroke_fill=CREAM)
        d.rectangle([cx - 150, y + 320, cx + 150, y + 326], fill=INK_DARK)
        d.text((cx - gw / 2, y + 380), kicker, font=fg, fill=INK_DARK, stroke_width=2, stroke_fill=CREAM)
        im.save(out, quality=92)
        return out

    im = warm_grade(im)
    im = ImageEnhance.Brightness(im).enhance(1.04)
    # bright centre with softly darker edges -- K chose this bright look, so the
    # type is dark on purpose rather than the background being dimmed.
    glow = ImageEnhance.Brightness(im).enhance(1.30)
    im = Image.composite(glow, im, radial_mask(BANNER_W, BANNER_H))
    inv = Image.fromarray(255 - np.asarray(radial_mask(BANNER_W, BANNER_H, power=1.7)))
    im = Image.composite(ImageEnhance.Brightness(im).enhance(0.62), im, inv)
    # a soft cream plate behind the copy: the background stays bright (K's rule)
    # while the dark type always reads, even over busy AI art.
    plate = Image.new("L", (BANNER_W, BANNER_H), 0)
    ImageDraw.Draw(plate).rounded_rectangle([556, 466, 2004, 988], radius=96, fill=178)
    plate = plate.filter(ImageFilter.GaussianBlur(64))
    im = Image.composite(Image.new("RGB", im.size, CREAM), im, plate)
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

    draw_centered_ls(ImageDraw.Draw(im), cx, y, f"\u2726 {kicker} \u2726", f_kick, INK_DARK, 8, 2, CREAM)
    y += kh + g1
    glow_text(im, cx, y, title, f_title, INK_DARK, 4, glow=CREAM)
    y += th + g2
    d = ImageDraw.Draw(im)
    d.line([cx - 210, y + 6, cx - 28, y + 6], fill=BRONZE, width=5)
    d.line([cx + 28, y + 6, cx + 210, y + 6], fill=BRONZE, width=5)
    d.polygon([(cx, y - 5), (cx + 13, y + 6), (cx, y + 17), (cx - 13, y + 6)], fill=BRONZE)
    y += 12 + g3
    d.text((cx - d.textlength(subtitle, font=f_sub) / 2, y), subtitle, font=f_sub, fill=INK_DARK,
           stroke_width=3, stroke_fill=CREAM)

    # ornament on the TV-visible band, so it is actually seen
    ornament(d, (500, 500, 2060, 940), col=BRONZE)
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
    ap.add_argument("--banner-art", required=False, default="")
    ap.add_argument("--avatar-art", required=False, default="")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--subtitle", required=True)
    ap.add_argument("--kicker", default="")
    ap.add_argument("--tagline", default="", help="alias for --kicker (classic look)")
    ap.add_argument("--style", choices=("lavish", "classic", "knowledge"), default="lavish",
                    help="lavish/classic need art; knowledge is drawn flat (no photo)")
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)
    kicker = a.kicker or a.tagline
    if a.style == "knowledge":
        print("wrote", knowledge_banner(a.title, a.subtitle, kicker,
                                        os.path.join(a.out_dir, "banner_2560x1440.jpg")))
        print("wrote", knowledge_avatar(os.path.join(a.out_dir, "avatar_800x800.jpg")))
        return 0
    if not (a.banner_art and a.avatar_art):
        ap.error("--banner-art and --avatar-art are required for lavish/classic")
    print("wrote", banner(a.banner_art, os.path.join(a.out_dir, "banner_2560x1440.jpg"),
                         a.title, kicker, a.subtitle, a.style))
    print("wrote", avatar(a.avatar_art, os.path.join(a.out_dir, "avatar_800x800.jpg"), a.style))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
