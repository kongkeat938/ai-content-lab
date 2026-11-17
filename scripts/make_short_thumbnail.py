#!/usr/bin/env python3
"""Build a 9:16 portrait Shorts thumbnail from the clip's own art + its hook.

Measured 2026-11-17: every Short we shipped wore YouTube's auto frame -- the
Shorts manifest had no `thumbnail` field and publish_shorts.py never called
`thumbnails.set`. The owner made a Shorts thumbnail a hard standard: a Short that
does not meet it must not upload.

YouTube's OWN rule (support.google.com/youtube/answer/72431, read 2026-11-17) is
the source here, not an advisor: for Shorts it recommends a **9:16** aspect, a
recommended size of **2160x3840**, a **minimum height of 640 px**, JPG/PNG, and
"remain under MB limits" (mobile 2 MB). So the thumbnail is PORTRAIT (the panel's
1280x720 advice was wrong for Shorts). This builds **1080x1920** (9:16, well over
the 640-px minimum) and keeps the file small.

    python3 scripts/make_short_thumbnail.py --art art.jpg --hook "ทำไม..." --out t.jpg
    python3 scripts/make_short_thumbnail.py --video short_15.mp4 --hook "..." --out t.jpg

A thumbnail with no readable word is not a thumbnail, so the hook is required and
is wrapped to fit; a hook that cannot be drawn raises rather than writing a blank.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FONTS = os.path.join(ROOT, "assets", "fonts")

W, H = 1080, 1920            # 9:16, portrait -- YouTube's Shorts thumbnail shape
GOLD = (245, 199, 90)
WHITE = (248, 249, 252)
# Mobile caps a custom thumbnail at 2 MB; stay well under so it never defers.
MAX_BYTES = 1_800_000


def _font(size: int):
    return ImageFont.truetype(os.path.join(FONTS, "Kanit-Bold.ttf"), size)


def cover(im: Image.Image) -> Image.Image:
    """Fill 1080x1920, cropping the overflow -- never letterbox (black bars read
    as a broken thumbnail on the Shorts shelf)."""
    r = max(W / im.width, H / im.height)
    im = im.resize((max(W, int(im.width * r)), max(H, int(im.height * r))), Image.LANCZOS)
    left = (im.width - W) // 2
    top = int((im.height - H) * 0.35)
    return im.crop((left, top, left + W, top + H))


def frame_from_video(path: str) -> Image.Image:
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as fh:
        tmp = fh.name
    try:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "1.0",
                        "-i", path, "-frames:v", "1", tmp], check=True)
        return Image.open(tmp).convert("RGB")
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def wrap(draw: ImageDraw.ImageDraw, text: str, f, max_w: int) -> list[str]:
    lines, cur = [], ""
    for ch in text:
        if draw.textlength(cur + ch, font=f) <= max_w or not cur:
            cur += ch
        else:
            lines.append(cur)
            cur = ch
    if cur:
        lines.append(cur)
    return lines


def build(art: str | None, video: str | None, hook: str, out: str) -> str:
    if art and os.path.exists(art):
        im = Image.open(art).convert("RGB")
    elif video and os.path.exists(video):
        im = frame_from_video(video)
    else:
        raise SystemExit("need --art or --video that exists")
    im = cover(im)
    im = ImageEnhance.Brightness(im).enhance(1.06)
    im = ImageEnhance.Color(im).enhance(1.12)
    im = ImageEnhance.Contrast(im).enhance(1.06)

    # Top-to-bottom scrim so a bright word always reads, heaviest where the hook sits.
    scrim = Image.new("L", (W, H), 0)
    d0 = ImageDraw.Draw(scrim)
    for y in range(H):
        v = int(200 * (1 - y / H) ** 1.5)
        d0.line([(0, y), (W, y)], fill=v)
    im = Image.composite(Image.new("RGB", (W, H), (6, 10, 20)), im, scrim)

    if not hook.strip():
        raise SystemExit("empty hook: a thumbnail with no word is not a thumbnail")

    d = ImageDraw.Draw(im)
    size = 132
    margin = 90
    while size > 66:
        f = _font(size)
        lines = wrap(d, hook.strip(), f, W - 2 * margin)
        if len(lines) <= 4:
            break
        size -= 6
    f = _font(size)
    lines = wrap(d, hook.strip(), f, W - 2 * margin)
    lh = size + int(size * 0.28)
    y = int(H * 0.12)
    d.rectangle([margin, y, margin + 14, y + lh * len(lines) - int(size * 0.28)], fill=GOLD)
    for i, ln in enumerate(lines):
        d.text((margin + 34, y), ln, font=f, fill=GOLD if i == 0 else WHITE,
               stroke_width=6, stroke_fill=(0, 0, 0))
        y += lh

    quality = 92
    im.save(out, quality=quality)
    while os.path.getsize(out) > MAX_BYTES and quality > 60:
        quality -= 8
        im.save(out, quality=quality)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--art")
    ap.add_argument("--video")
    ap.add_argument("--hook", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = build(a.art, a.video, a.hook, a.out)
    im = Image.open(out)
    print(f"wrote {out} ({im.width}x{im.height}, {os.path.getsize(out)//1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
