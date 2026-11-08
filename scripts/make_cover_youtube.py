#!/usr/bin/env python3
"""Build a YouTube cover for a dharma video: glowing gold Buddha + hook text.

Why this exists (measured 2026-11-08): a search for "ธรรมะก่อนนอน" returns no
Farmmer video in the top 30, while channels with only 4,300 subscribers hold
600k-800k views. The blocker is packaging, not reach: the winning covers all
share one recipe -- a glowing gold Buddha on a deep-navy night, with a few big
heavy-stroke Thai words. This script reproduces that recipe with free tools
only: Pillow, the fonts already in assets/fonts, and CC0 art from
assets/branding/farmmer/art (see that folder's credits.json).

It is deliberately separate from make_poster.py, which builds the in-video
"cinema poster" cards; this one builds the 1280x720 cover that sits on the
browse and search surfaces, where the click is won.

    python3 scripts/make_cover_youtube.py --key night_money_01 \
        --line1 "หลับลึกถึงเช้า" --line2 "เทวดาคุ้มครอง" \
        --sub "ปล่อยวางเรื่องเงิน" --out cover.jpg

The art is chosen from the library by a hash of --key, so the same video always
gets the same Buddha (a re-run does not shuffle the covers).
"""
from __future__ import annotations

import argparse
import hashlib
import os

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FONTS = os.path.join(ROOT, "assets", "fonts")
ART_DIR = os.path.join(ROOT, "assets", "branding", "farmmer", "art")

W, H = 1280, 720
NAVY_TOP = (8, 12, 38)     # deep night sky
NAVY_BOT = (3, 6, 20)
GOLD = (255, 214, 0)
WHITE = (255, 255, 255)
AURA = (255, 205, 90)      # warm glow colour behind the statue


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(os.path.join(FONTS, name), size)


def pick_art(key: str) -> str:
    """Deterministic art choice so a re-run keeps the same cover."""
    files = sorted(f for f in os.listdir(ART_DIR)
                   if f.endswith(".jpg") and not f.startswith("_"))
    if not files:
        raise SystemExit(f"no art in {ART_DIR}")
    idx = int(hashlib.sha1(key.encode()).hexdigest(), 16) % len(files)
    return os.path.join(ART_DIR, files[idx])


def _gild(im: Image.Image) -> Image.Image:
    """Push a statue toward glowing gold.

    The Commons statues are museum bronze: grey and dark, and they vary in tone
    from piece to piece. Autocontrast first normalises that spread, then a gold
    layer is applied in proportion to each pixel's own brightness, so the lit
    stone lifts to gold while the shadows stay dark -- a statue that reads as
    "glowing", and a family of covers that share one warm grade.
    """
    im = ImageOps.autocontrast(im, cutoff=1)
    lum = ImageOps.grayscale(im).convert("L")
    gold = Image.new("RGB", im.size, (255, 202, 84))
    return Image.composite(gold, im, lum.point(lambda v: int(v * 0.72)))


def statue(src: str, target_h: int) -> Image.Image:
    """Load the statue, gild it, and feather its edges to the navy."""
    im = Image.open(src).convert("RGBA")
    r = target_h / im.height
    im = im.resize((max(1, int(im.width * r)), target_h), Image.LANCZOS)
    im = ImageEnhance.Contrast(im).enhance(1.20)
    im = ImageEnhance.Color(im).enhance(1.25)
    im = ImageEnhance.Brightness(im).enhance(1.15)
    im = _gild(im.convert("RGB")).convert("RGBA")

    # Feather the left edge and the bottom so the photo melts into the navy
    # instead of reading as a pasted rectangle. The radial mask darkens whatever
    # background the photo itself carries, leaving the lit statue.
    mask = Image.new("L", im.size, 255)
    md = ImageDraw.Draw(mask)
    fw = int(im.width * 0.32)
    for x in range(fw):
        md.line([(x, 0), (x, im.height)], fill=int(255 * (x / fw) ** 1.3))
    fh = int(im.height * 0.12)
    for y in range(fh):
        md.line([(0, im.height - 1 - y), (im.width, im.height - 1 - y)],
                fill=int(255 * ((fh - y) / fh) ** 1.3))
    vig = Image.new("L", im.size, 0)
    vd = ImageDraw.Draw(vig)
    cx, cy = im.width * 0.6, im.height * 0.42
    for i in range(40, 0, -1):
        rr = int(max(im.size) * i / 40)
        vd.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=int(255 * (i / 40)))
    vig = vig.filter(ImageFilter.GaussianBlur(40))
    im.putalpha(ImageChops.multiply(mask, vig))
    return im


def radial_glow(size, color, strength, cx=0.72, cy=0.45, r=0.62):
    w, h = size
    g = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(g)
    px, py = w * cx, h * cy
    for i in range(60, 0, -1):
        rr = int(max(w, h) * r * i / 60)
        d.ellipse([px - rr, py - rr, px + rr, py + rr],
                  fill=int(strength * 255 * (1 - i / 60) ** 1.6))
    gl = Image.new("RGBA", (w, h), color + (0,))
    gl.putalpha(g.filter(ImageFilter.GaussianBlur(50)))
    return gl


def fit(s: str, name: str, size: int, max_w: int) -> ImageFont.FreeTypeFont:
    """Shrink the font until the line fits max_w, so text never hits the statue."""
    f = font(name, size)
    while size > 24 and f.getbbox(s)[2] > max_w:
        size -= 4
        f = font(name, size)
    return f


def text(d, xy, s, f, fill, stroke=(0, 0, 0, 235), sw=None, anchor="la"):
    x, y = xy
    sw = sw or max(4, int(f.size * 0.10))
    d.text((x + 4, y + 5), s, font=f, fill=(0, 0, 0, 210), anchor=anchor,
           stroke_width=sw, stroke_fill=(0, 0, 0, 210))
    d.text((x, y), s, font=f, fill=fill, anchor=anchor,
           stroke_width=sw, stroke_fill=stroke)


def build(art: str, out: str, tag: str, line1: str, line2: str, sub: str,
          key: str = "cover") -> None:
    variant = int(hashlib.sha1(key.encode()).hexdigest(), 16) % 2  # 0=text left, 1=text right
    base = Image.new("RGB", (W, H), NAVY_TOP)
    ramp = Image.new("L", (1, H))
    for y in range(H):
        ramp.putpixel((0, y), int(255 * (1 - y / H)))
    base = Image.composite(base, Image.new("RGB", (W, H), NAVY_BOT), ramp.resize((W, H)))

    glow_cx = 0.72 if variant == 0 else 0.28
    base = Image.alpha_composite(base.convert("RGBA"),
                                 radial_glow((W, H), AURA, 0.9, cx=glow_cx)).convert("RGB")

    st = statue(art, int(H * 1.06))
    if variant == 1:
        st = ImageOps.mirror(st)
        sx = -int(st.width * 0.18)
    else:
        sx = W - st.width + int(st.width * 0.18)
    sy = H - st.height + int(st.height * 0.03)
    aura = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    aura.paste(st, (sx, sy), st)
    aura = aura.filter(ImageFilter.GaussianBlur(40))
    tint = Image.new("RGBA", (W, H), AURA + (0,))
    tint.putalpha(aura.split()[3].point(lambda v: int(v * 0.85)))
    base = Image.alpha_composite(base.convert("RGBA"), tint).convert("RGB")
    rim = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    rim.paste(st, (sx, sy), st)
    base = Image.alpha_composite(base.convert("RGBA"),
                                 rim.filter(ImageFilter.GaussianBlur(16))).convert("RGB")
    base.paste(st, (sx, sy), st)

    # Scrim on the text side so the words always sit on dark pixels.
    scrim = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(scrim)
    span = int(W * 0.66)
    for i in range(span):
        a = int(185 * (1 - i / span) ** 1.2)
        if variant == 0:
            sd.line([(i, 0), (i, H)], fill=(3, 6, 20, a))
        else:
            sd.line([(W - 1 - i, 0), (W - 1 - i, H)], fill=(3, 6, 20, a))
    base = Image.alpha_composite(base.convert("RGBA"), scrim).convert("RGB")

    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    max_w = int(W * 0.62)
    tx = 58 if variant == 0 else W - 58 - max_w
    align = "la" if variant == 0 else "ra"
    ax = 58 if variant == 0 else W - 58
    text(d, (ax, 74), tag, fit(tag, "Kanit-Bold.ttf", 50, max_w), WHITE + (255,), sw=7, anchor=align)
    d.rectangle([tx, 186, tx + 220, 192], fill=GOLD + (255,))
    text(d, (ax, 214), line1, fit(line1, "Kanit-Bold.ttf", 120, max_w), WHITE + (255,), sw=9, anchor=align)
    text(d, (ax, 344), line2, fit(line2, "Kanit-Bold.ttf", 120, max_w), GOLD + (255,), sw=9, anchor=align)
    text(d, (ax, 486), sub, fit(sub, "Kanit-SemiBold.ttf", 48, max_w), WHITE + (255,), sw=7, anchor=align)
    base = Image.alpha_composite(base.convert("RGBA"), ov).convert("RGB")

    base = ImageEnhance.Contrast(base).enhance(1.06)
    base.save(out, "JPEG", quality=92)
    print(f"saved {out} ({W}x{H})")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", default="cover", help="stable id, selects the art")
    ap.add_argument("--art", help="explicit art path (overrides --key)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--tag", default="ธรรมะก่อนนอน")
    ap.add_argument("--line1", required=True)
    ap.add_argument("--line2", required=True)
    ap.add_argument("--sub", required=True)
    args = ap.parse_args()
    build(args.art or pick_art(args.key), args.out,
          args.tag, args.line1, args.line2, args.sub, key=args.key)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
