#!/usr/bin/env python3
"""Build a vertical Short (1080x1920) from a script: voice, captions, and a slow
ken-burns backdrop -- free tools only.

Shorts are the reach engine: they get shown to people who do not know the
channel, and each one points at a long video. The long video is what collects the
watch hours the Partner Programme counts, so the funnel is Short -> long, and
this script makes the Short.

    python3 scripts/make_short.py --scripts content/ch2_shorts/scripts.json \
        --out-dir work/ch2_shorts --index 01

Input shape (written by Gemini, see content/ch2_shorts/scripts.json):
    {"id": "01", "hook": "...", "lines": ["...", ...], "cta": "..."}

The hook is spoken first and shown big; the CTA is appended as the last line, so
every Short ends asking for the follow. Numbers must already be Thai words --
edge-tts has no Thai number dictionary and would read a digit wrong.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys

import edge_tts
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FONTS = os.path.join(ROOT, "assets", "fonts")
VOICE = "th-TH-NiwatNeural"      # calm male narrator, the channel's voice
# A slower read: the niche's winners run about a minute, and a slow read holds a
# sleepy listener better than a clipped one.
RATE = "-15%"
W, H = 1080, 1920
GOLD = (245, 199, 90)
WHITE = (250, 250, 252)


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(os.path.join(FONTS, name), size)


def run(cmd: list) -> None:
    subprocess.run(cmd, check=True, capture_output=True)


async def speak(text: str, out: str) -> None:
    await edge_tts.Communicate(text, VOICE, rate=RATE).save(out)


def duration(path: str) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", path], capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def backdrop(out: str, art: str | None) -> None:
    """A dark, calm 1080x1920 frame. Uses channel art when given, else a gradient."""
    if art and os.path.exists(art):
        im = Image.open(art).convert("RGB")
        r = max(W / im.width, H / im.height)
        im = im.resize((int(im.width * r), int(im.height * r)), Image.LANCZOS)
        left = (im.width - W) // 2
        top = (im.height - H) // 2
        im = im.crop((left, top, left + W, top + H))
    else:
        im = Image.new("RGB", (W, H), (8, 14, 30))
    # Bottom scrim so captions always read, plus a gentle vignette.
    scrim = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(scrim)
    for y in range(H):
        v = 0
        if y > H * 0.35:
            v = int(210 * ((y - H * 0.35) / (H * 0.65)) ** 1.3)
        d.line([(0, y), (W, y)], fill=v)
    im = Image.composite(Image.new("RGB", (W, H), (3, 6, 16)), im, scrim)
    im.save(out, quality=95)


def wrap(draw: ImageDraw.ImageDraw, text: str, f: ImageFont.FreeTypeFont,
         max_w: int) -> list[str]:
    """Thai has no spaces between words, so break by measuring character runs."""
    lines, cur = [], ""
    for ch in text:
        trial = cur + ch
        if draw.textlength(trial, font=f) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = ch
    if cur:
        lines.append(cur)
    return lines


def caption_image(text: str, out: str, big: bool = False) -> None:
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    size = 96 if big else 78
    f = font("Kanit-Bold.ttf", size)
    lines = wrap(d, text, f, W - 160)
    lh = int(size * 1.35)
    total = lh * len(lines)
    y = int(H * 0.66) if not big else int(H * 0.42)
    y = min(y, H - 340 - total)
    for i, ln in enumerate(lines):
        tw = d.textlength(ln, font=f)
        x = (W - tw) / 2
        d.text((x, y + i * lh), ln, font=f, fill=GOLD if big else WHITE,
               stroke_width=6, stroke_fill=(0, 0, 0, 235))
    im.save(out)


def build(script: dict, out_dir: str, art: str | None, music: str | None) -> str:
    sid = script["id"]
    d = os.path.join(out_dir, sid)
    os.makedirs(d, exist_ok=True)

    # Spoken text: hook, then the lines, then the CTA. Blank lines become the
    # pause edge-tts reads between them, so the read breathes.
    spoken = "\n".join([script["hook"], *script["lines"], script["cta"]])
    voice_mp3 = os.path.join(d, "voice.mp3")
    if not os.path.exists(voice_mp3):
        asyncio.run(speak(spoken, voice_mp3))
    dur = duration(voice_mp3)

    # Captions: one PNG per line, shown for its share of the audio.
    shown = [script["hook"], *script["lines"], script["cta"]]
    cards = []
    for i, text in enumerate(shown):
        p = os.path.join(d, f"cap_{i:02d}.png")
        caption_image(text, p, big=(i == 0))
        cards.append(p)

    # Rough per-line timing: proportional to character count. Exact timing is
    # not needed for a Short; the card changes feel deliberate either way.
    weights = [max(1, len(t)) for t in shown]
    tot = sum(weights)
    bounds, acc = [], 0.0
    for wgt in weights:
        acc += dur * wgt / tot
        bounds.append(acc)

    bg = os.path.join(d, "bg.jpg")
    backdrop(bg, art)

    # Assemble: loop the still, overlay each caption for its window, mux audio.
    parts = []
    prev = 0.0
    for i, (card, end) in enumerate(zip(cards, bounds)):
        seg = os.path.join(d, f"seg_{i:02d}.mp4")
        seg_len = max(0.4, end - prev)
        vf = (f"[1:v]scale={W}:{H}[c];[0:v][c]overlay=0:0:format=auto[v]")
        cmd = ["ffmpeg", "-y", "-loop", "1", "-t", f"{seg_len:.3f}", "-i", bg,
               "-loop", "1", "-t", f"{seg_len:.3f}", "-i", card,
               "-filter_complex", vf, "-map", "[v]",
               "-r", "30", "-pix_fmt", "yuv420p", "-c:v", "libx264",
               "-preset", "veryfast", "-crf", "20", seg]
        run(cmd)
        parts.append(seg)
        prev = end

    listfile = os.path.join(d, "parts.txt")
    with open(listfile, "w") as fh:
        for p in parts:
            fh.write(f"file '{p}'\n")
    silent = os.path.join(d, "silent.mp4")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", listfile,
         "-c", "copy", silent])

    out = os.path.join(d, f"short_{sid}.mp4")
    if music and os.path.exists(music):
        run(["ffmpeg", "-y", "-i", silent, "-i", voice_mp3, "-i", music,
             "-filter_complex",
             "[2:a]volume=0.18[m];[1:a][m]amix=inputs=2:duration=first:dropout_transition=0,"
             "loudnorm=I=-14:TP=-1.5:LRA=11[a]",
             "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac",
             "-b:a", "192k", "-shortest", out])
    else:
        run(["ffmpeg", "-y", "-i", silent, "-i", voice_mp3,
             "-map", "0:v", "-map", "1:a", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
             "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", out])
    print(f"  {sid}: {duration(out):.1f}s -> {out}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scripts", default=os.path.join(ROOT, "content", "ch2_shorts", "scripts.json"))
    ap.add_argument("--out-dir", default=os.path.join(ROOT, "work", "ch2_shorts"))
    ap.add_argument("--art", help="background image (default: a dark gradient)")
    ap.add_argument("--music", help="optional bed to mix under the voice")
    ap.add_argument("--index", action="append", help="build only these ids")
    args = ap.parse_args()

    with open(args.scripts, encoding="utf-8") as fh:
        scripts = json.load(fh)
    if args.index:
        scripts = [s for s in scripts if s["id"] in args.index]
    os.makedirs(args.out_dir, exist_ok=True)
    for s in scripts:
        build(s, args.out_dir, args.art, args.music)
    print(f"built {len(scripts)} short(s) in {args.out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
