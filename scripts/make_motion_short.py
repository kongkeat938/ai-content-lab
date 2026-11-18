#!/usr/bin/env python3
"""Build a Short that MOVES: a still image with sparkling stars, leaves that
flutter on the wind, and a little character that dances to the music.

Why this exists (K, 2026-11-18): the current Short is a still photo with captions
sliding over it -- the picture itself never moves, so the feed reads it as a
slide-show and reach drops. This rail keeps the free, no-GPU pipeline but makes
every layer move, so the frame is alive the whole way through:

  * a slow ken-burns push on the still;
  * twinkling stars that pulse at their own rate (glow, additive);
  * leaves that drift and spin on a sine "wind";
  * a cute character that bounces and swings its arms on the BEAT of the music;
  * the spoken line as a caption, timed to the voice.

The look follows the story's genre (K, 2026-11-18): a calm genre (dharma/genx) gets
only the gentle layers -- twinkle + drift, NO dancing character and NO pulsing glow
disc, which read as a shape throbbing on the beat. The lively mascot is reserved for
the curious knowledge genre.

Audio is the real narration (edge-tts, the house voice) over a free music bed,
pinned to the house loudness (-14 LUFS / -3 dBTP) with make_short's own
`normalise`, so the same short_standard gate decides pass/fail.

    python3 scripts/make_motion_short.py --story content/motion/01.json \
        --out-dir work/motion --music assets/music/bed-calm-soft-piano-wav.mp3

Story shape: {"id","hook","lines":[..],"cta":..,"puppet":"owl","mood":"night"}
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import random
import subprocess
import sys

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import make_short as MS  # noqa: E402  (voice, loudness, fonts -- the one source)

W, H = 1080, 1920
FPS = 15                       # enough for smooth drift/bounce, cheap to render
BEAT_HZ = 1.7                  # the dance tempo (light genres only)
CAP_FONT = "Prompt-SemiBold.ttf"
# K, 2026-11-18: "slow the speaking pace down a bit". The house voice runs at
# make_short.RATE (-15%); a narrated still reads better slower, so this rail
# defaults to -25% unless the story sets its own `rate`.
RATE = "-25%"

# palette per mood (top sky -> horizon -> ground)
MOODS = {
    "night":   ((18, 24, 62), (58, 46, 92), (24, 20, 44)),
    "dawn":    ((70, 96, 150), (232, 176, 120), (60, 52, 60)),
    "forest":  ((30, 60, 60), (120, 160, 110), (24, 40, 30)),
    "sunset":  ((120, 80, 130), (250, 170, 110), (70, 46, 54)),
}

# The look MUST match the story, not a fixed cartoon (K, 2026-11-18): a dharma
# sleep clip gets calm ambient motion, a knowledge "why?" clip may get the lively
# mascot. So every layer is chosen from the story's `genre`, and the default is the
# calmest profile -- an unknown story never gets a dancing character it did not ask
# for. `character` is None for the calm genres on purpose.
PROFILES = {
    # ธรรมะก่อนนอน: serene, sleepy. slow twinkle + drifting petals. NO dancing
    # character and NO pulsing glow disc (K, 2026-11-18: "just the sparkle is
    # enough" -- the breathing circle read as a shape throbbing on the beat).
    "dharma":    {"stars": (30, 0.5, 10), "drift": (8, 26, 34, "petal"),
                  "character": None, "motion": 0.6},
    # ปรัชญาชีวิต (GenX): reflective, quiet. few stars + slow dust motes.
    "genx":      {"stars": (18, 0.4, 9), "drift": (10, 18, 26, "mote"),
                  "character": None, "motion": 0.7},
    # เกร็ดความรู้ "ทำไม…?" (PCSEV): curious + friendly. sparkles + a mascot that
    # bobs and points, on the beat. This is the one genre the mascot suits.
    "knowledge": {"stars": (40, 1.0, 12), "drift": (8, 40, 60, "leaf"),
                  "character": "mascot", "motion": 1.0},
}
DEFAULT_GENRE = "dharma"       # the calmest profile -- a safe default


def ease(x: float) -> float:
    return x * x * (3 - 2 * x)


def lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def draw_sunmoon(im: Image.Image, mood: str, seed: int) -> Image.Image:
    """A prominent sun or moon in the sky (K, 2026-11-18: "a sun or a moon image").
    Night moods get a pale moon with soft craters; dawn/sunset/forest get a warm
    sun with a halo. It is painted onto the backdrop so ken-burns carries it too."""
    d = ImageDraw.Draw(im, "RGBA")
    cx, cy, r = int(W * 0.72), int(H * 0.15), 150
    night = mood in ("night",)
    body = (245, 246, 240, 245) if night else (255, 236, 178, 250)
    halo = (220, 228, 255) if night else (255, 214, 140)

    for g in range(7, 0, -1):                       # the glow halo
        rad = r + g * 34
        d.ellipse([cx - rad, cy - rad, cx + rad, cy + rad], fill=halo + (10,))
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=body)

    if night:                                       # a few soft craters
        rnd = random.Random(seed + 9)
        for _ in range(6):
            a = rnd.uniform(0, math.tau)
            dist = rnd.uniform(0, r * 0.6)
            cr = rnd.uniform(r * 0.10, r * 0.22)
            px, py = cx + math.cos(a) * dist, cy + math.sin(a) * dist
            d.ellipse([px - cr, py - cr, px + cr, py + cr], fill=(214, 216, 214, 90))
    return im


def backdrop(mood: str, seed: int, art: str | None) -> Image.Image:
    """A calm 1080x1920 still: a real photo when given, else a painted gradient."""
    if art and os.path.exists(art):
        im = Image.open(art).convert("RGB")
        r = max(W / im.width, H / im.height)
        im = im.resize((int(im.width * r), int(im.height * r)), Image.LANCZOS)
        left, top = (im.width - W) // 2, (im.height - H) // 2
        return im.crop((left, top, left + W, top + H)).filter(ImageFilter.GaussianBlur(1.5))

    top, horizon, ground = MOODS.get(mood, MOODS["night"])
    arr = np.zeros((H, W, 3), np.uint8)
    for y in range(H):
        t = y / (H - 1)
        # sky above the horizon, ground below, eased so the band sits high
        if t < 0.62:
            arr[y, :] = lerp(top, horizon, ease(t / 0.62))
        else:
            arr[y, :] = lerp(horizon, ground, ease((t - 0.62) / 0.38))
    im = Image.fromarray(arr)
    im = draw_sunmoon(im, mood, seed)

    d = ImageDraw.Draw(im, "RGBA")
    # rolling hills near the horizon
    for band, (hy, col) in enumerate([(0.60, (0, 0, 0, 60)), (0.66, (0, 0, 0, 90))]):
        pts = [(0, H)]
        for x in range(0, W + 1, 60):
            y = int(H * hy + math.sin((x / W) * math.pi * (2 + band) + seed) * 40)
            pts.append((x, y))
        pts.append((W, H))
        d.polygon(pts, fill=col)
    return im


def ken_burns(base: Image.Image, t: float, dur: float, speed: float = 1.0) -> Image.Image:
    """A slow push-in so the still breathes (1.00 -> 1.06 over the clip)."""
    z = 1.0 + 0.06 * (t / max(dur, 0.001))
    cw, ch = int(W / z), int(H / z)
    left = int((W - cw) / 2 + math.sin(t * 0.15 * speed) * 8)
    top = int((H - ch) / 2 + math.cos(t * 0.12 * speed) * 6)
    crop = base.crop((left, top, left + cw, top + ch))
    return crop.resize((W, H), Image.BICUBIC)


def make_stars(seed: int, n: int = 46, size: tuple = (6, 18)) -> list[dict]:
    rnd = random.Random(seed + 1)
    lo, hi = size
    return [{"x": rnd.uniform(0, W), "y": rnd.uniform(0, H * 0.66),
             "s": rnd.uniform(lo, hi), "ph": rnd.uniform(0, math.tau),
             "sp": rnd.uniform(0.4, 1.5), "col": rnd.choice(
                 [(255, 240, 190), (255, 255, 255), (200, 220, 255), (255, 210, 140)])}
            for _ in range(n)]


def _star(d: ImageDraw.ImageDraw, x: float, y: float, s: float, a: int, col) -> None:
    r = s * 0.5
    d.polygon([(x, y - r * 2.2), (x + r * 0.5, y - r * 0.5), (x + r * 2.2, y),
               (x + r * 0.5, y + r * 0.5), (x, y + r * 2.2), (x - r * 0.5, y + r * 0.5),
               (x - r * 2.2, y), (x - r * 0.5, y - r * 0.5)], fill=col + (a,))


def draw_stars(img: Image.Image, stars: list[dict], t: float, speed: float = 1.0) -> Image.Image:
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for st in stars:
        tw = 0.5 + 0.5 * math.sin(math.tau * st["sp"] * speed * t + st["ph"])
        _star(d, st["x"], st["y"], st["s"] * (0.7 + 0.6 * tw), int(40 + 200 * tw), st["col"])
    glow = layer.filter(ImageFilter.GaussianBlur(7))
    out = ImageChops.screen(img.convert("RGB"), glow.convert("RGB"))
    return Image.alpha_composite(out.convert("RGBA"), layer).convert("RGB")


def make_leaves(seed: int, n: int = 12, kind: str = "leaf",
                vy: tuple = (40, 90)) -> list[dict]:
    rnd = random.Random(seed + 2)
    if kind == "leaf":
        cols = [(120, 170, 90), (86, 140, 70), (200, 170, 70), (150, 190, 120)]
        sz = (26, 54)
    elif kind == "petal":
        cols = [(255, 224, 236), (250, 200, 216), (240, 214, 224)]
        sz = (16, 34)
    else:  # mote -- soft dust in warm light
        cols = [(255, 244, 214), (250, 236, 200)]
        sz = (6, 16)
    return [{"x": rnd.uniform(0, W), "y": rnd.uniform(-H, H),
             "vy": rnd.uniform(*vy), "vx": rnd.uniform(-30, 30),
             "spin": rnd.uniform(-1.6, 1.6), "sz": rnd.uniform(*sz),
             "ph": rnd.uniform(0, math.tau), "kind": kind, "col": rnd.choice(cols)}
            for _ in range(n)]


def _leaf(d: ImageDraw.ImageDraw, x: float, y: float, sz: float, ang: float, col) -> None:
    pts = []
    steps = 14
    for i in range(steps + 1):                       # up the leading edge
        s = i / steps
        pts.append((s * sz * 0.55, -s * sz))
    for i in range(steps + 1):                       # back down the trailing edge
        s = 1 - i / steps
        pts.append((-s * sz * 0.55, -s * sz))
    ca, sa = math.cos(ang), math.sin(ang)
    rot = [(x + px * ca - py * sa, y + px * sa + py * ca) for px, py in pts]
    d.polygon(rot, fill=col + (215,))
    d.line(rot[:steps + 1], fill=(60, 90, 50, 220), width=2)


def _petal(d: ImageDraw.ImageDraw, x: float, y: float, sz: float, ang: float, col) -> None:
    r = sz * 0.5
    ca, sa = math.cos(ang), math.sin(ang)
    rot = [(x + px * ca - py * sa, y + px * sa + py * ca)
           for px, py in [(0, -r), (r * 0.7, 0), (0, r), (-r * 0.7, 0)]]
    d.polygon(rot, fill=col + (200,))


def draw_leaves(img: Image.Image, leaves: list[dict], t: float, speed: float = 1.0) -> Image.Image:
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for lf in leaves:
        y = (lf["y"] + lf["vy"] * speed * t) % (H + 200) - 100
        x = lf["x"] + lf["vx"] * speed * t + math.sin(t * 1.1 * speed + lf["ph"]) * 40
        if lf["kind"] == "petal":
            _petal(d, x, y, lf["sz"], lf["spin"] * t + lf["ph"], lf["col"])
        elif lf["kind"] == "mote":
            d.ellipse([x - lf["sz"], y - lf["sz"], x + lf["sz"], y + lf["sz"]],
                      fill=lf["col"] + (150,))
        else:
            _leaf(d, x, y, lf["sz"], lf["spin"] * t + lf["ph"], lf["col"])
    return Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")


def draw_character(img: Image.Image, t: float, mood: str, beat_accent: float) -> Image.Image:
    """A cute mascot that dances: bounce on the beat, squash-and-stretch, arm swing."""
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cx, cy = W // 2, int(H * 0.60)
    body_r = 150
    phase = math.tau * BEAT_HZ * t
    hop = abs(math.sin(phase / 2))                       # two hops per beat
    amp = 90 + 60 * beat_accent
    by = cy - hop * amp
    squash = 0.10 * math.cos(phase)                      # stretch at the bottom, squash at the top
    rx = body_r * (1 + squash)
    ry = body_r * (1 - squash)

    # contact shadow (shrinks as it hops)
    sh_w = body_r * (1.1 - 0.4 * hop)
    d.ellipse([cx - sh_w, cy + body_r * 0.9, cx + sh_w, cy + body_r * 1.15],
              fill=(0, 0, 0, int(90 - 50 * hop)))

    body_col = (255, 214, 120) if mood != "forest" else (170, 220, 140)
    # arms (swing with the beat)
    swing = math.sin(phase) * 0.9
    for side in (-1, 1):
        sx, sy = cx + side * rx * 0.85, by + ry * 0.1
        ex = sx + side * 90
        ey = sy + 70 * (0.4 + swing * side)
        d.line([(sx, sy), (ex, ey)], fill=body_col + (255,), width=34)
        d.ellipse([ex - 20, ey - 20, ex + 20, ey + 20], fill=body_col + (255,))
    # body
    d.ellipse([cx - rx, by - ry, cx + rx, by + ry], fill=body_col + (255,))
    d.ellipse([cx - rx * 0.7, by - ry * 0.9, cx + rx * 0.2, by], fill=(255, 240, 200, 70))
    # eyes + smile
    for side in (-1, 1):
        ex = cx + side * rx * 0.34
        d.ellipse([ex - 22, by - 40, ex + 22, by + 6], fill=(40, 34, 30, 255))
        d.ellipse([ex - 6, by - 34, ex + 8, by - 16], fill=(255, 255, 255, 255))
    d.arc([cx - 46, by + 8, cx + 46, by + 74], 20, 160, fill=(70, 50, 40, 255), width=8)
    return Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")


def caption(img: Image.Image, text: str) -> Image.Image:
    """The spoken line, wrapped, on a soft panel at the foot of the frame."""
    if not text:
        return img
    f = MS.font(CAP_FONT, 62)
    tmp = ImageDraw.Draw(img)
    lines = MS.wrap(tmp, text, f, int(W * 0.86))
    lh = 78
    block_h = lh * len(lines) + 56
    panel = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    pd = ImageDraw.Draw(panel)
    top = H - block_h - 120
    pd.rounded_rectangle([40, top, W - 40, top + block_h], radius=36, fill=(10, 12, 26, 170))
    y = top + 28
    for ln in lines:
        w = tmp.textlength(ln, font=f)
        pd.text(((W - w) / 2, y), ln, font=f, fill=(252, 250, 245, 255))
        y += lh
    return Image.alpha_composite(img.convert("RGBA"), panel).convert("RGB")


def beat_accent(t: float) -> float:
    """1.0 exactly on the beat, easing to 0 between -- drives the extra hop."""
    frac = (t * BEAT_HZ) % 1.0
    return max(0.0, 1.0 - frac * 3.0)


def profile_for(genre: str | None) -> dict:
    """The layer set for a story's genre. An unknown/absent genre gets the calm
    default, so a story never accidentally gets the dancing mascot."""
    return PROFILES.get((genre or "").strip().lower(), PROFILES[DEFAULT_GENRE])


def layers_for(seed: int, prof: dict) -> tuple[list[dict], list[dict]]:
    """Build the star + drift layers from a profile (counts/kinds/sizes)."""
    n_stars, _sp, s_hi = prof["stars"]
    stars = make_stars(seed, n=n_stars, size=(max(4, s_hi // 2), s_hi))
    n_drift, vy_lo, vy_hi, kind = prof["drift"]
    leaves = make_leaves(seed, n=n_drift, kind=kind, vy=(vy_lo, vy_hi))
    return stars, leaves


def frame_at(base: Image.Image, stars, leaves, mood: str, t: float, dur: float,
             animate: bool = True, prof: dict | None = None) -> Image.Image:
    """One composed frame. `animate=False` freezes the moving layers, so a guard
    can prove the motion comes from them and not from the encode."""
    prof = prof or PROFILES[DEFAULT_GENRE]
    fr = ken_burns(base, t, dur, speed=prof["motion"])
    if animate:
        spd = prof["stars"][1]
        fr = draw_stars(fr, stars, t, speed=spd)
        fr = draw_leaves(fr, leaves, t, speed=prof["motion"])
        if prof.get("character"):
            fr = draw_character(fr, t, mood, beat_accent(t))
    return fr


def render_frames(base: Image.Image, stars, leaves, mood: str, dur: float, out_dir: str,
                  prof: dict | None = None) -> int:
    n = int(math.ceil(dur * FPS))
    for i in range(n):
        t = i / FPS
        yield i, t, frame_at(base, stars, leaves, mood, t, dur, prof=prof)
    return n


def main() -> int:
    global FPS
    ap = argparse.ArgumentParser()
    ap.add_argument("--story", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--genre", default=None,
                    help="dharma|genx|knowledge -- picks the layer profile; the story's "
                         "`genre` field is used when this is omitted (default dharma)")
    ap.add_argument("--art", default=None, help="a still to animate (else painted)")
    ap.add_argument("--music", default=None, help="a bed; omit for voice only")
    ap.add_argument("--voice", default=None)
    ap.add_argument("--fps", type=int, default=FPS)
    args = ap.parse_args()
    FPS = args.fps

    with open(args.story, encoding="utf-8") as fh:
        story = json.load(fh)
    sid = str(story["id"])
    mood = story.get("mood", "night")
    genre = args.genre or story.get("genre") or DEFAULT_GENRE
    prof = profile_for(genre)
    d = os.path.join(args.out_dir, sid)
    os.makedirs(d, exist_ok=True)

    seq = [story["hook"], *story.get("lines", []), story.get("cta", "")]
    seq = [s for s in seq if s]
    rate = story.get("rate", RATE)
    voice_mp3 = os.path.join(d, "voice.mp3")
    if not os.path.exists(voice_mp3):
        asyncio.run(MS.speak(" ".join(seq), voice_mp3, args.voice or MS.VOICE, rate=rate))
    dur = MS.duration(voice_mp3)

    base = backdrop(mood, abs(hash(sid)) % 9999, args.art)
    base.save(os.path.join(d, "bg.jpg"), quality=92)
    seed = abs(hash(sid)) % 9999
    stars, leaves = layers_for(seed, prof)
    print(f"  genre={genre}: {len(stars)} stars, {len(leaves)} drift({prof['drift'][3]}), "
          f"character={prof.get('character') or 'none'}")

    # caption windows, proportional to each line's length (same rule as make_short)
    weights = [max(1, len(s)) for s in seq]
    tot = sum(weights)
    bounds, acc = [], 0.0
    for wgt in weights:
        acc += dur * wgt / tot
        bounds.append(acc)

    frames = os.path.join(d, "frames")
    os.makedirs(frames, exist_ok=True)
    n = 0
    prev = 0.0
    line_i = 0
    for i, t, fr in render_frames(base, stars, leaves, mood, dur, frames, prof=prof):
        while line_i < len(bounds) - 1 and t >= bounds[line_i]:
            line_i += 1
        fr = caption(fr, seq[line_i])
        fr.save(os.path.join(frames, f"f_{i:05d}.png"))
        n += 1

    silent = os.path.join(d, "silent.mp4")
    MS.run(["ffmpeg", "-y", "-framerate", str(FPS), "-i",
            os.path.join(frames, "f_%05d.png"), "-r", "30",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-pix_fmt", "yuv420p", "-color_range", "tv", "-colorspace", "bt709",
            "-color_primaries", "bt709", "-color_trc", "bt709", silent])

    mixed = os.path.join(d, "mix.wav")
    if args.music and os.path.exists(args.music):
        v_lufs = MS.measure_audio(voice_mp3) or -20.0
        vol = MS.bed_gain(args.music, v_lufs)
        MS.run(["ffmpeg", "-y", "-i", voice_mp3, "-stream_loop", "-1", "-i", args.music,
                "-filter_complex",
                f"[1:a]volume={vol:.4f}[m];[0:a][m]amix=inputs=2:duration=first:"
                "dropout_transition=0:normalize=0[a]",
                "-map", "[a]", "-ar", "48000", mixed])
    else:
        MS.run(["ffmpeg", "-y", "-i", voice_mp3, "-ar", "48000", mixed])
    norm = os.path.join(d, "norm.wav")
    MS.normalise(mixed, norm)

    out = os.path.join(d, f"motion_{sid}.mp4")
    MS.run(["ffmpeg", "-y", "-i", silent, "-i", norm, "-map", "0:v", "-map", "1:a",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", out])
    print(f"  {sid}: {MS.duration(out):.1f}s, {n} frames -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
