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
import video_grade as VG  # noqa: E402  (the ONE bright grade -- K: "ขอสดใส")

W, H = 1080, 1920
FPS = 15                       # enough for smooth drift/bounce, cheap to render
BEAT_HZ = 1.7                  # the dance tempo (light genres only)
CAP_FONT = "Prompt-SemiBold.ttf"
# K (2026-11-19): the caption sat at 90% of the height, right under the Shorts UI
# (title/channel/buttons), so it hid the picture on a phone. Put it above the middle.
CAPTION_CY = 0.34
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
    # ธรรมะก่อนนอน: serene but alive -- slow petals + drifting fireflies + a soft
    # sparkle. NO dancing character (K, 2026-11-18: "just the sparkle is enough").
    "dharma":    {"stars": (30, 0.5, 10), "fx": [("petal", 10), ("firefly", 9), ("spark", 7)],
                  "character": None, "motion": 0.6},
    # ปรัชญาชีวิต (GenX): reflective -- dust motes + a few floating hearts.
    "genx":      {"stars": (18, 0.4, 9), "fx": [("mote", 14), ("heart", 4), ("spark", 5)],
                  "character": None, "motion": 0.7},
    # เกร็ดความรู้ "ทำไม…?" (PCSEV): curious + friendly -- leaves, confetti, a mascot.
    "knowledge": {"stars": (40, 1.0, 12), "fx": [("leaf", 9), ("confetti", 10), ("spark", 6)],
                  "character": "mascot", "motion": 1.0},
    # ---- weather looks: a story picks one with `"fx": "rain"` (or a list) ----
    "rain":      {"stars": (10, 0.4, 8), "fx": [("rain", 90), ("bubble", 6)],
                  "character": None, "motion": 0.8},
    "snow":      {"stars": (16, 0.4, 8), "fx": [("snow", 70), ("spark", 6)],
                  "character": None, "motion": 0.7},
    "waterfall": {"stars": (12, 0.5, 8), "fx": [("waterfall", 110), ("mote", 10)],
                  "character": None, "motion": 0.7},
    "volcano":   {"stars": (14, 0.6, 9), "fx": [("lava", 46), ("ember", 30), ("ash", 34)],
                  "character": None, "motion": 0.9},
    "ocean":     {"stars": (12, 0.4, 8), "fx": [("bubble", 46), ("mote", 10)],
                  "character": None, "motion": 0.7},
    "celebrate": {"stars": (26, 0.9, 10), "fx": [("confetti", 44), ("heart", 10)],
                  "character": None, "motion": 1.0},
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
        return im.crop((left, top, left + W, top + H))

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
    return crop.resize((W, H), Image.LANCZOS)


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


# ---- particles: many kinds, one system (K, 2026-11-19) --------------------
# K: "ทำฟรุ้งฟริ้งเคลื่อนไหว ใช้เป็นฝน วงกลมเล็กๆ ใบไม้ร่วง หิมะ น้ำตก ภูเขาไฟ
# ระเบิด หรืออะไรก็ได้อีกเยอะ" -- one drifting petal was not enough. Every effect
# is now a particle: `mode` says how it moves (fall / rise / drift / burst) and
# `kind` says how it is drawn. A new effect = one entry here + one branch in
# `_draw_one`, so the set can keep growing without touching the render loop.
FALL, RISE, DRIFT, BURST = "fall", "rise", "drift", "burst"

KINDS = {
    "leaf":      dict(mode=FALL, vy=(90, 170), vx=(-45, 45), sz=(26, 54), a=215, sway=40,
                      cols=[(120, 170, 90), (86, 140, 70), (200, 170, 70), (150, 190, 120)]),
    "petal":     dict(mode=FALL, vy=(26, 40), vx=(-20, 20), sz=(16, 34), a=205, sway=44,
                      cols=[(255, 224, 236), (250, 200, 216), (240, 214, 224)]),
    "snow":      dict(mode=FALL, vy=(45, 100), vx=(-18, 18), sz=(5, 15), a=230, sway=26,
                      cols=[(255, 255, 255), (238, 246, 255), (222, 236, 255)]),
    "rain":      dict(mode=FALL, vy=(950, 1500), vx=(-95, -45), sz=(30, 70), a=150, sway=4,
                      cols=[(198, 224, 255), (216, 236, 255)]),
    "ash":       dict(mode=FALL, vy=(38, 84), vx=(-26, 26), sz=(4, 11), a=175, sway=34,
                      cols=[(152, 152, 160), (120, 120, 128), (180, 180, 188)]),
    "confetti":  dict(mode=FALL, vy=(120, 250), vx=(-60, 60), sz=(10, 22), a=235, sway=30,
                      cols=[(255, 92, 120), (255, 196, 64), (84, 214, 152),
                            (96, 168, 255), (214, 120, 255)]),
    "mote":      dict(mode=FALL, vy=(16, 30), vx=(-14, 14), sz=(6, 16), a=155, sway=22,
                      cols=[(255, 244, 214), (250, 236, 200)]),
    "bubble":    dict(mode=RISE, vy=(50, 115), vx=(-20, 20), sz=(10, 26), a=195, sway=20,
                      cols=[(190, 232, 255), (214, 244, 255), (170, 214, 255)]),
    "ember":     dict(mode=RISE, vy=(60, 135), vx=(-26, 26), sz=(4, 11), a=238, sway=18,
                      glow=True,
                      cols=[(255, 196, 92), (255, 150, 54), (255, 232, 168)]),
    "firefly":   dict(mode=DRIFT, vy=(-16, 16), vx=(-16, 16), sz=(5, 12), a=235, sway=70,
                      glow=True,
                      cols=[(220, 255, 150), (180, 255, 120), (255, 246, 150)]),
    "spark":     dict(mode=DRIFT, vy=(-12, 12), vx=(-12, 12), sz=(8, 18), a=235, sway=12,
                      glow=True,
                      cols=[(255, 246, 200), (214, 236, 255), (255, 214, 236)]),
    "heart":     dict(mode=RISE, vy=(40, 95), vx=(-18, 18), sz=(14, 26), a=210, sway=26,
                      cols=[(255, 140, 170), (255, 180, 200), (255, 110, 150)]),
    "waterfall": dict(mode=FALL, vy=(1150, 1750), vx=(-12, 12), sz=(34, 96), a=145, sway=3,
                      band=(0.50, 0.11),
                      cols=[(226, 244, 255), (200, 230, 255), (255, 255, 255)]),
    "lava":      dict(mode=BURST, vy=(330, 640), vx=(-190, 190), sz=(5, 16), a=242, sway=0,
                      glow=True, origin=(0.50, 0.80), period=(1.4, 2.6),
                      cols=[(255, 168, 54), (255, 110, 40), (255, 222, 140)]),
}


# A sensible count per kind when a story names its own fx (dense kinds are cheap
# to draw but clutter a calm scene, so each gets its own default).
FX_COUNT = {"rain": 90, "waterfall": 110, "snow": 70, "confetti": 44, "lava": 46,
            "ember": 30, "ash": 34, "bubble": 46, "firefly": 9, "heart": 10,
            "leaf": 9, "petal": 10, "mote": 14, "spark": 7}


def make_particles(seed: int, n: int, kind: str, salt: int = 0) -> list[dict]:
    """`n` particles of one kind, spread over the frame and out of phase."""
    spec = KINDS[kind]
    rnd = random.Random(seed * 31 + salt * 7919 + sum(map(ord, kind)))
    if spec["mode"] == BURST:
        ox, oy = spec["origin"]
        return [{"kind": kind, "mode": BURST,
                 "x": W * ox + rnd.uniform(-40, 40), "y": H * oy,
                 "vx": rnd.uniform(*spec["vx"]), "vy": rnd.uniform(*spec["vy"]),
                 "g": rnd.uniform(620, 900), "sz": rnd.uniform(*spec["sz"]),
                 "ph": rnd.uniform(0, 1) * rnd.uniform(*spec["period"]),
                 "period": rnd.uniform(*spec["period"]), "a": spec["a"],
                 "sway": spec["sway"], "spin": rnd.uniform(-2.0, 2.0),
                 "glow": spec.get("glow", False), "col": rnd.choice(spec["cols"])}
                for _ in range(n)]
    lo, hi = spec["sz"]
    parts = []
    for _ in range(n):
        if "band" in spec:
            cx, half = spec["band"]
            x = rnd.uniform(W * (cx - half), W * (cx + half))
        else:
            x = rnd.uniform(-40, W + 40)
        parts.append({
            "kind": kind, "mode": spec["mode"], "x": x,
            "y": rnd.uniform(-H, H), "vy": rnd.uniform(*spec["vy"]),
            "vx": rnd.uniform(*spec["vx"]), "sz": rnd.uniform(lo, hi),
            "ph": rnd.uniform(0, math.tau), "spin": rnd.uniform(-1.8, 1.8),
            "sway": spec["sway"], "a": spec["a"], "glow": spec.get("glow", False),
            "col": rnd.choice(spec["cols"]),
        })
    return parts


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


def _heart(d: ImageDraw.ImageDraw, x: float, y: float, sz: float, col, a: int) -> None:
    r = sz * 0.5
    d.ellipse([x - r, y - r, x, y], fill=col + (a,))
    d.ellipse([x, y - r, x + r, y], fill=col + (a,))
    d.polygon([(x - r, y - r * 0.2), (x + r, y - r * 0.2), (x, y + r * 1.05)],
              fill=col + (a,))


def _draw_one(d: ImageDraw.ImageDraw, p: dict, x: float, y: float, t: float,
              fade: float | None) -> None:
    """Draw one particle at (x, y). `fade` (0..1) is the burst life; None = steady."""
    k, col, sz = p["kind"], p["col"], p["sz"]
    a = int(p["a"] * (1.0 - fade)) if fade is not None else p["a"]
    if a <= 0:
        return
    if k == "leaf":
        _leaf(d, x, y, sz, p["spin"] * t + p["ph"], col)
    elif k == "petal":
        _petal(d, x, y, sz, p["spin"] * t + p["ph"], col)
    elif k == "snow":
        d.ellipse([x - sz, y - sz, x + sz, y + sz], fill=col + (a // 2,))
        d.ellipse([x - sz * 0.55, y - sz * 0.55, x + sz * 0.55, y + sz * 0.55],
                  fill=(255, 255, 255, a))
    elif k == "rain":
        d.line([(x, y), (x - sz * 0.30, y + sz)], fill=col + (a,), width=3)
    elif k == "waterfall":
        d.line([(x, y), (x, y + sz)], fill=col + (a,), width=4)
        d.line([(x + 3, y + sz * 0.3), (x + 3, y + sz)], fill=col + (a // 2,), width=2)
    elif k == "ash":
        d.ellipse([x - sz, y - sz * 0.7, x + sz, y + sz * 0.7], fill=col + (a,))
    elif k == "confetti":
        ca, sa = math.cos(p["spin"] * t + p["ph"]), math.sin(p["spin"] * t + p["ph"])
        w, h = sz, sz * 0.55
        rot = [(x + px * ca - py * sa, y + px * sa + py * ca)
               for px, py in [(-w, -h), (w, -h), (w, h), (-w, h)]]
        d.polygon(rot, fill=col + (a,))
    elif k == "mote":
        d.ellipse([x - sz, y - sz, x + sz, y + sz], fill=col + (a,))
    elif k == "bubble":
        d.ellipse([x - sz, y - sz, x + sz, y + sz], outline=col + (a,), width=3)
        d.ellipse([x - sz * 0.55, y - sz * 0.55, x - sz * 0.15, y - sz * 0.15],
                  fill=(255, 255, 255, min(255, a + 30)))
    elif k == "ember":
        d.ellipse([x - sz * 1.6, y - sz * 1.6, x + sz * 1.6, y + sz * 1.6],
                  fill=col + (a // 4,))
        d.ellipse([x - sz, y - sz, x + sz, y + sz], fill=col + (a,))
        d.ellipse([x - sz * 0.45, y - sz * 0.45, x + sz * 0.45, y + sz * 0.45],
                  fill=(255, 252, 226, a))
    elif k == "firefly":
        tw = 0.45 + 0.55 * math.sin(math.tau * 0.7 * t + p["ph"])
        aa = int(a * tw)
        d.ellipse([x - sz * 2.2, y - sz * 2.2, x + sz * 2.2, y + sz * 2.2],
                  fill=col + (aa // 5,))
        d.ellipse([x - sz, y - sz, x + sz, y + sz], fill=col + (aa,))
        d.ellipse([x - sz * 0.4, y - sz * 0.4, x + sz * 0.4, y + sz * 0.4],
                  fill=(255, 255, 220, aa))
    elif k == "spark":
        tw = 0.5 + 0.5 * math.sin(math.tau * 1.3 * t + p["ph"])
        _star(d, x, y, sz * (0.6 + 0.6 * tw), int(a * (0.4 + 0.6 * tw)), col)
    elif k == "heart":
        _heart(d, x, y, sz, col, a)
    elif k == "lava":
        d.ellipse([x - sz * 1.7, y - sz * 1.7, x + sz * 1.7, y + sz * 1.7],
                  fill=col + (a // 4,))
        d.ellipse([x - sz, y - sz, x + sz, y + sz], fill=col + (a,))
        d.ellipse([x - sz * 0.4, y - sz * 0.4, x + sz * 0.4, y + sz * 0.4],
                  fill=(255, 250, 220, a))


def _particle_pos(p: dict, t: float, speed: float) -> tuple[float, float, float | None]:
    """Where a particle is at time `t`, plus its burst life (None when steady)."""
    if p["mode"] == FALL:
        y = (p["y"] + p["vy"] * speed * t) % (H + 240) - 120
        x = p["x"] + p["vx"] * speed * t + math.sin(t * 1.1 * speed + p["ph"]) * p["sway"]
    elif p["mode"] == RISE:
        y = (p["y"] - p["vy"] * speed * t) % (H + 240) - 120
        x = p["x"] + p["vx"] * speed * t + math.sin(t * 1.3 * speed + p["ph"]) * p["sway"]
    elif p["mode"] == DRIFT:
        x = (p["x"] + p["vx"] * speed * t
             + math.sin(t * 0.9 * speed + p["ph"]) * p["sway"]) % W
        y = (p["y"] + p["vy"] * speed * t
             + math.cos(t * 0.7 * speed + p["ph"] * 1.7) * p["sway"]) % H
    else:                                              # BURST: a ballistic arc
        per = p["period"]
        u = ((t * speed + p["ph"]) % per) / per
        x = p["x"] + p["vx"] * u * per
        y = p["y"] - p["vy"] * u * per + 0.5 * p["g"] * (u * per) ** 2
        return x, y, u
    return x, y, None


def draw_fx(img: Image.Image, parts: list[dict], t: float,
            speed: float = 1.0) -> Image.Image:
    """Composite every particle onto the frame; glow kinds get a soft halo."""
    if not parts:
        return img
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d, gd = ImageDraw.Draw(layer), ImageDraw.Draw(glow)
    used_glow = False
    for p in parts:
        x, y, fade = _particle_pos(p, t, speed)
        if x < -160 or x > W + 160 or y < -240 or y > H + 240:
            continue
        if p.get("glow"):
            used_glow = True
            _draw_one(gd, p, x, y, t, fade)
        else:
            _draw_one(d, p, x, y, t, fade)
    out = Image.alpha_composite(img.convert("RGBA"), layer)
    if used_glow:
        out = Image.alpha_composite(out, glow.filter(ImageFilter.GaussianBlur(6)))
        out = Image.alpha_composite(out, glow)
    return out.convert("RGB")


def make_leaves(seed: int, n: int = 12, kind: str = "leaf",
                vy: tuple = (40, 90)) -> list[dict]:
    """Kept for callers/tests that ask for one drifting kind by name."""
    return make_particles(seed, n, kind, salt=2)


def draw_leaves(img: Image.Image, leaves: list[dict], t: float,
                speed: float = 1.0) -> Image.Image:
    return draw_fx(img, leaves, t, speed=speed)


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
    """The spoken line, wrapped, on a soft panel in the UPPER-MIDDLE of the frame.

    K (2026-11-19): "คำบรรยายเอาไว้ช่วงบนมากลาง มันบังเวลาดูในมือถือ" -- a caption at
    the foot sits under the Shorts UI (title, channel, buttons), so the text is put
    above the middle where nothing overlaps it. The block is centred on CAPTION_CY.
    """
    if not text:
        return img
    f = MS.font(CAP_FONT, 62)
    tmp = ImageDraw.Draw(img)
    lines = MS.wrap(tmp, text, f, int(W * 0.86))
    lh = 78
    block_h = lh * len(lines) + 56
    panel = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    pd = ImageDraw.Draw(panel)
    top = max(70, int(H * CAPTION_CY) - block_h // 2)
    pd.rounded_rectangle([40, top, W - 40, top + block_h], radius=36, fill=(8, 10, 22, 150))
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


def layers_for(seed: int, prof: dict) -> tuple[list[dict], list[list[dict]]]:
    """Build the star layer + one particle layer per effect in the profile."""
    n_stars, _sp, s_hi = prof["stars"]
    stars = make_stars(seed, n=n_stars, size=(max(4, s_hi // 2), s_hi))
    fx = [make_particles(seed, n, kind, salt=i)
          for i, (kind, n) in enumerate(prof["fx"])]
    return stars, fx


def frame_at(base: Image.Image, stars, fx, mood: str, t: float, dur: float,
             animate: bool = True, prof: dict | None = None) -> Image.Image:
    """One composed frame. `animate=False` freezes the moving layers, so a guard
    can prove the motion comes from them and not from the encode."""
    prof = prof or PROFILES[DEFAULT_GENRE]
    fr = ken_burns(base, t, dur, speed=prof["motion"])
    if animate:
        spd = prof["stars"][1]
        fr = draw_stars(fr, stars, t, speed=spd)
        for parts in fx:
            fr = draw_fx(fr, parts, t, speed=prof["motion"])
        if prof.get("character"):
            fr = draw_character(fr, t, mood, beat_accent(t))
    return fr


def render_frames(base: Image.Image, stars, fx, mood: str, dur: float, out_dir: str,
                  prof: dict | None = None) -> int:
    n = int(math.ceil(dur * FPS))
    for i in range(n):
        t = i / FPS
        yield i, t, frame_at(base, stars, fx, mood, t, dur, prof=prof)
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
    # A story may name its own weather instead of a genre: "fx": "snow", or a list
    # ["snow", "spark"] -> the same particle kinds, without a canned profile.
    fx_spec = story.get("fx")
    if fx_spec:
        kinds = [fx_spec] if isinstance(fx_spec, str) else list(fx_spec)
        prof = dict(prof, fx=[(k, FX_COUNT.get(k, 24)) for k in kinds])
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
    stars, fx = layers_for(seed, prof)
    print(f"  genre={genre}: {len(stars)} stars, fx="
          f"{[(k, len(p)) for (k, _n), p in zip(prof['fx'], fx)]}, "
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
    for i, t, fr in render_frames(base, stars, fx, mood, dur, frames, prof=prof):
        while line_i < len(bounds) - 1 and t >= bounds[line_i]:
            line_i += 1
        fr = caption(fr, seq[line_i])
        fr.save(os.path.join(frames, f"f_{i:05d}.png"))
        n += 1

    # The grade is the house one (video_grade.GRADE) -- ONE source. K (2026-11-19):
    # "ความละเอียดภาพไม่สวย ขุ่นมัวไม่เอา ขอสดใส" -- so the render is sharpened
    # (unsharp + cas) and lifted in contrast/saturation on the way out, not left flat.
    silent = os.path.join(d, "silent.mp4")
    MS.run(["ffmpeg", "-y", "-framerate", str(FPS), "-i",
            os.path.join(frames, "f_%05d.png"), "-r", "30",
            "-vf", VG.GRADE,
            "-c:v", "libx264", "-preset", "slow", "-crf", "18",
            "-pix_fmt", "yuv420p", "-color_range", "tv", "-colorspace", "bt709",
            "-color_primaries", "bt709", "-color_trc", "bt709",
            "-x264-params", "colorprim=bt709:transfer=bt709:colormatrix=bt709", silent])

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
