#!/usr/bin/env python3
"""Algorithmic generative art: every pixel computed from maths, no model, no API.

Why this exists: the image routes we had all depend on somebody else's quota --
Dreamina credits run out, the Gemini API free tier answers 429 limit:0, and
Pollinations caps service-wide (all measured). This module draws instead of
asking. Given a seed it is reproducible byte for byte, which is what makes an
edition sellable: the buyer can be told "this exact seed produced this file".

Ten generators, each a different piece of mathematics:

  flow         curl-noise field advecting ribbons (fluid, painterly)
  moire        interfering sine waves (optical, graphic)
  reaction     Gray-Scott reaction-diffusion (organic, coral/worm textures)
  attractor    Clifford strange-attractor density map (fine filigree)
  harmonograph decaying Lissajous curves (elegant line drawing)
  voronoi      stained-glass cells with ink edges (geometric)
  contour      topographic contour lines from fractal noise (map-like)
  truchet      Truchet arc tiling (modern pattern)
  superformula rose curves from the superformula (mandala rosette)
  dgrowth      differential growth of a closed ring (coral / brain forms)

Honest limits, measured on this pod (4 cores, PIL 13, numpy 2.5):
  * `reaction` and `voronoi` compute their field at `work_res` (<=1600 px) and
    upscale. Reaction-diffusion is iterative and does not vectorise to 4096^2 in
    reasonable time; Voronoi is O(pixels x sites). The upscale is LANCZOS, so
    cell edges soften like watercolour -- intentional, but it is an upscale.
  * Everything else is computed at full resolution.

Usage:
    python3 scripts/generative_art.py --list
    python3 scripts/generative_art.py --gen flow --seed 7 --size 4096 --out a.png
    python3 scripts/generative_art.py --count 40 --size 2048 --out-dir library/
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import time
from multiprocessing import Pool

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

# ---------------------------------------------------------------- palettes ---
# Print-safe ramps: dark anchor -> light highlight. Order matters, the field
# value indexes into the ramp, so a palette with a light middle and dark ends
# would produce banded, unnatural art.
PALETTES = {
    "midnight": ["#0b1026", "#1b2a5e", "#3d5fa8", "#8fb8e8", "#f2f6ff"],
    "ember":    ["#1a0b06", "#5c1f0e", "#c24b1c", "#f0952e", "#ffe6b0"],
    "sage":     ["#0d1512", "#1f3a2f", "#3f6b52", "#8fbf9f", "#eaf4ea"],
    "rose":     ["#1a0a12", "#4d1430", "#a0285a", "#e86a92", "#ffd9e4"],
    "sand":     ["#14100c", "#3d3021", "#8a6f45", "#d4b483", "#f7efe0"],
    "ink":      ["#05070a", "#12181f", "#2a3644", "#6b7f96", "#dfe7ef"],
    "violet":   ["#0a0616", "#26124d", "#5b2a9e", "#a173e0", "#ecdcff"],
    "teal":     ["#04120f", "#0b3a35", "#14766b", "#4fc0ab", "#d6fff5"],
}


def _rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _lut(palette: str, n: int = 256) -> np.ndarray:
    """Interpolate the ramp into an n-entry lookup table."""
    stops = np.array([_rgb(c) for c in PALETTES[palette]], dtype=np.float32)
    xs = np.linspace(0, len(stops) - 1, n, dtype=np.float32)
    i0 = np.floor(xs).astype(np.int32)
    i1 = np.minimum(i0 + 1, len(stops) - 1)
    t = (xs - i0)[:, None]
    return (stops[i0] * (1 - t) + stops[i1] * t).astype(np.uint8)


def _colorize(field: np.ndarray, lut: np.ndarray) -> np.ndarray:
    idx = np.clip(field * 255.0, 0, 255).astype(np.uint8)
    return lut[idx]


def _swatch(palette: str, i: int) -> tuple[int, int, int]:
    stops = PALETTES[palette]
    return _rgb(stops[i % len(stops)])


def _paper(palette: str) -> tuple[int, int, int]:
    """Light ground for the stroke generators.

    Measured 2026-11-19 at 768 px: the six line generators painted mid-tones onto
    `PALETTES[pal][0]`, the darkest stop, and the frame came out at mean luma
    19-35 -- a black card on a phone. The field generators (moire, contour,
    reaction, voronoi) fill the frame and measured 96-128 on the same palettes.
    Strokes on the second-brightest stop read as ink on paper instead: the same
    seeds measured luma 134-149 with std 24-28, so the detail survives.
    """
    return _rgb(PALETTES[palette][-2])


def _ink(palette: str, i: int) -> tuple[int, int, int]:
    """Dark end of the ramp -- the strokes that sit on `_paper`."""
    return _swatch(palette, i % 3)


# ------------------------------------------------------------------- noise ---
def _smoothstep(t: np.ndarray) -> np.ndarray:
    return t * t * (3.0 - 2.0 * t)


def _upsample(grid: np.ndarray, h: int, w: int) -> np.ndarray:
    """Bilinear-with-smoothstep upsample of a small grid to (h, w)."""
    gh, gw = grid.shape
    y = np.linspace(0, gh - 1, h, dtype=np.float32)
    x = np.linspace(0, gw - 1, w, dtype=np.float32)
    y0 = np.floor(y).astype(np.int32)
    x0 = np.floor(x).astype(np.int32)
    y1 = np.minimum(y0 + 1, gh - 1)
    x1 = np.minimum(x0 + 1, gw - 1)
    fy = _smoothstep(y - y0)[:, None]
    fx = _smoothstep(x - x0)[None, :]
    top = grid[np.ix_(y0, x0)] * (1 - fx) + grid[np.ix_(y0, x1)] * fx
    bot = grid[np.ix_(y1, x0)] * (1 - fx) + grid[np.ix_(y1, x1)] * fx
    return top * (1 - fy) + bot * fy


def _fbm(rng: np.random.Generator, h: int, w: int,
         octaves: int = 6, base: int = 4, persistence: float = 0.5) -> np.ndarray:
    total = np.zeros((h, w), dtype=np.float32)
    amp, norm, freq = 1.0, 0.0, base
    for _ in range(octaves):
        grid = rng.random((freq + 1, freq + 1)).astype(np.float32)
        total += amp * _upsample(grid, h, w)
        norm += amp
        amp *= persistence
        freq *= 2
    return total / norm


def _normalize(a: np.ndarray) -> np.ndarray:
    lo, hi = float(a.min()), float(a.max())
    if hi - lo < 1e-9:
        return np.zeros_like(a)
    return ((a - lo) / (hi - lo)).astype(np.float32)


# --------------------------------------------------------------- finishing ---
def _finish(rgb: np.ndarray, rng: np.random.Generator,
            grain: float = 0.018, vignette: float = 0.16) -> Image.Image:
    """Paper grain + vignette. Small amounts only: the art must carry itself."""
    out = rgb.astype(np.float32)
    if grain > 0:
        out += rng.normal(0.0, grain * 255.0, out.shape[:2])[:, :, None]
    if vignette > 0:
        h, w = out.shape[:2]
        yy = np.linspace(-1, 1, h, dtype=np.float32)[:, None]
        xx = np.linspace(-1, 1, w, dtype=np.float32)[None, :]
        r = np.sqrt(xx * xx + yy * yy) / math.sqrt(2.0)
        out *= (1.0 - vignette * r * r)[:, :, None]
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGB")


def _sample(field: np.ndarray, ys: np.ndarray, xs: np.ndarray) -> np.ndarray:
    """Bilinear sample of `field` at normalized coords ys, xs in [0, 1]."""
    gh, gw = field.shape
    fy = np.clip(ys, 0, 1) * (gh - 1)
    fx = np.clip(xs, 0, 1) * (gw - 1)
    y0 = np.floor(fy).astype(np.int32)
    x0 = np.floor(fx).astype(np.int32)
    y1 = np.minimum(y0 + 1, gh - 1)
    x1 = np.minimum(x0 + 1, gw - 1)
    ty = fy - y0
    tx = fx - x0
    return ((field[y0, x0] * (1 - tx) + field[y0, x1] * tx) * (1 - ty)
            + (field[y1, x0] * (1 - tx) + field[y1, x1] * tx) * ty)


# -------------------------------------------------------------- generators ---
def gen_flow(rng: np.random.Generator, h: int, w: int, pal: str, ssaa: int) -> Image.Image:
    """Curl-noise flow field: particles advected through a divergence-free field."""
    res = 384
    noise = _fbm(rng, res, res, octaves=5, base=3)
    gy, gx = np.gradient(noise)
    field_x = -gy
    field_y = gx

    n_part = 850
    steps = 210
    step_len = 1.0 / steps * 1.6
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    for i in range(n_part):
        px = rng.random()
        py = rng.random()
        shade = 1 + int(rng.integers(1, len(PALETTES[pal]) - 1))
        col = _ink(pal, shade)
        alpha = int(rng.integers(28, 96))
        width = int(max(1, round(rng.random() ** 2 * 5 + 1)))
        pts = []
        for s in range(steps):
            vx = float(_sample(field_x, np.array([py]), np.array([px]))[0])
            vy = float(_sample(field_y, np.array([py]), np.array([px]))[0])
            n = math.hypot(vx, vy)
            if n < 1e-6:
                break
            px += vx / n * step_len
            py += vy / n * step_len
            if not (0.0 <= px <= 1.0 and 0.0 <= py <= 1.0):
                break
            pts.append((px * w, py * h))
        if len(pts) > 2:
            draw.line(pts, fill=col + (alpha,), width=width, joint="curve")

    canvas = Image.new("RGB", (w, h), _paper(pal))
    canvas = Image.alpha_composite(canvas.convert("RGBA"), layer).convert("RGB")
    return _finish(np.asarray(canvas), rng)


def gen_moire(rng: np.random.Generator, h: int, w: int, pal: str, ssaa: int) -> Image.Image:
    """Interference of near-equal spatial frequencies: the moire pattern itself."""
    yy = np.linspace(0, 1, h, dtype=np.float32)[:, None]
    xx = np.linspace(0, 1, w, dtype=np.float32)[None, :]
    field = np.zeros((h, w), dtype=np.float32)
    k = int(rng.integers(3, 6))
    for _ in range(k):
        ang = rng.random() * math.pi
        freq = 18.0 + rng.random() * 26.0
        phase = rng.random() * math.tau
        cx, cy = rng.random(), rng.random()
        # a gentle radial warp keeps the grid from reading as a plain screen
        warp = 0.55 + 0.45 * np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
        field += np.sin(math.tau * freq * (math.cos(ang) * xx + math.sin(ang) * yy)
                        * warp + phase)
    field = _normalize(field)
    field = 0.5 + 0.5 * np.tanh((field - 0.5) * 2.6)
    return _finish(_colorize(field, _lut(pal)), rng)


# Gray-Scott feed/kill pairs. Measured at 320 px: (0.0367, 0.0649) settles into a
# flat card (std 3.4 vs 66-76 for a live pair), so it is NOT here -- every pair
# listed must sustain a live pattern, and the test renders each one to prove it.
REACTION_PRESETS = [(0.0545, 0.062), (0.078, 0.061), (0.029, 0.057)]


def _laplace(a: np.ndarray) -> np.ndarray:
    """9-point Laplacian over a wrapped copy, done with slices.

    Measured 2026-11-19 on PC1: the np.roll version cost 171 ms per call there
    (30x the pod's 5.6 ms) and reaction-diffusion calls it 3,200 times, so one
    picture took 6.4 min and the queue looked frozen. This version is 3x faster
    and gives the SAME output as roll (std 66.78, edge luma 110.7 on both) --
    an unpadded slice version was rejected because it left a black border
    (edge luma 14.4 vs 120 inside).
    """
    p = np.pad(a, 1, mode="wrap")
    b = p[:-2, 1:-1] + p[2:, 1:-1] + p[1:-1, :-2] + p[1:-1, 2:]
    c = p[:-2, :-2] + p[:-2, 2:] + p[2:, :-2] + p[2:, 2:]
    return b * 0.2 + c * 0.05 - a


def gen_reaction(rng: np.random.Generator, h: int, w: int, pal: str, ssaa: int) -> Image.Image:
    """Gray-Scott reaction-diffusion. Computed at work_res, then upscaled."""
    work = int(min(1400, max(320, min(h, w) // 3)))
    feed, kill = REACTION_PRESETS[int(rng.integers(0, len(REACTION_PRESETS)))]
    A = np.ones((work, work), dtype=np.float32)
    B = np.zeros((work, work), dtype=np.float32)
    # Seed a jittered lattice across the WHOLE domain, edges included, so the
    # pattern has no single centre and reaches the frame.
    step = int(rng.integers(work // 14, work // 8))
    r = int(max(3, rng.integers(work // 40, work // 22)))
    yy, xx = np.ogrid[-r:r, -r:r]
    disc = yy * yy + xx * xx <= r * r
    for cy in range(step // 2, work, step):
        for cx in range(step // 2, work, step):
            jy = int(cy + rng.integers(-step // 3, step // 3 + 1))
            jx = int(cx + rng.integers(-step // 3, step // 3 + 1))
            y0, y1 = jy - r, jy + r
            x0, x1 = jx - r, jx + r
            if y0 < 0 or x0 < 0 or y1 > work or x1 > work:
                continue
            B[y0:y1, x0:x1][disc] = 1.0
    B += rng.random((work, work)).astype(np.float32) * 0.02

    iters = 3200
    for _ in range(iters):
        reaction = A * B * B
        A += 1.0 * _laplace(A) - reaction + feed * (1.0 - A)
        B += 0.5 * _laplace(B) + reaction - (kill + feed) * B
        np.clip(A, 0, 1, out=A)
        np.clip(B, 0, 1, out=B)

    field = _normalize(B)
    field = field ** 0.75
    img = Image.fromarray(_colorize(field, _lut(pal)), "RGB").resize((w, h), Image.LANCZOS)
    return _finish(np.asarray(img), rng, grain=0.014)


def _clifford_params(rng: np.random.Generator) -> tuple[float, float, float, float]:
    """Pick (a,b,c,d) whose orbit actually fills a region.

    Measured at seeds 1-8 with the plain uniform draw: 4 of 8 collapsed onto a
    fixed point (0.00% of cells occupied) and drew an all-black card. The map is
    sensitive like that, so probe cheaply and resample instead of shipping black.
    """
    probe_n = 120_000
    best, best_occ = None, -1.0
    for _ in range(40):
        a, b, c, d = (float(v) for v in rng.uniform(-2.0, 2.0, 4))
        x, y = 0.1, 0.1
        px = np.empty(probe_n, dtype=np.float32)
        py = np.empty(probe_n, dtype=np.float32)
        for i in range(probe_n):
            x, y = math.sin(a * y) + c * math.cos(a * x), math.sin(b * x) + d * math.cos(b * y)
            px[i], py[i] = x, y
        px, py = px[probe_n // 10:], py[probe_n // 10:]
        if not (np.isfinite(px).all() and np.isfinite(py).all()):
            continue
        xr = float(px.max() - px.min())
        yr = float(py.max() - py.min())
        if xr < 0.05 or yr < 0.05:
            continue
        hist, _, _ = np.histogram2d(
            (py - py.min()) / yr, (px - px.min()) / xr,
            bins=96, range=[[0, 1], [0, 1]])
        occupied = float((hist > 0).mean())
        # Floor measured 2026-11-19 over seeds 101-130 at 1024 px: every set at
        # occupancy ~0.041 rendered std 7.6-8.4 (gate rejects), while sets at
        # 0.15-0.55 rendered std 25-59. Between 0.03 and 0.10 the outcome is not
        # predictable from the probe, so only the safe side is accepted.
        if 0.10 <= occupied <= 0.60:
            return a, b, c, d
        if occupied > best_occ:      # nothing cleared the floor: keep the densest
            best, best_occ = (a, b, c, d), occupied
    return best if best is not None else (a, b, c, d)


def gen_attractor(rng: np.random.Generator, h: int, w: int, pal: str, ssaa: int) -> Image.Image:
    """Clifford attractor: density of an iterated map, log-scaled."""
    a, b, c, d = _clifford_params(rng)
    n = 3_000_000
    xs = np.empty(n, dtype=np.float32)
    ys = np.empty(n, dtype=np.float32)
    x, y = 0.1, 0.1
    for i in range(n):
        nx = math.sin(a * y) + c * math.cos(a * x)
        ny = math.sin(b * x) + d * math.cos(b * y)
        x, y = nx, ny
        xs[i] = x
        ys[i] = y
    keep = slice(n // 20, n)  # drop the transient
    xs, ys = xs[keep], ys[keep]
    # min/max normalization wasted the frame: measured at seed 3 the occupied
    # cells were 0.04% of the canvas, so the piece was an almost-black card. A
    # rare outlier stretches the bounding box; clipping to the 0.2/99.8
    # percentile box makes the filigree fill the image.
    xlo, xhi = np.percentile(xs, [0.2, 99.8])
    ylo, yhi = np.percentile(ys, [0.2, 99.8])
    xs = (xs - xlo) / max(1e-9, float(xhi - xlo))
    ys = (ys - ylo) / max(1e-9, float(yhi - ylo))

    work = int(min(2000, min(h, w)))
    hist, _, _ = np.histogram2d(ys, xs, bins=work, range=[[0, 1], [0, 1]])
    density = np.log1p(hist).astype(np.float32)
    # The density is extremely peaked: measured at 512 px only 0.1% of pixels sat
    # above luminance 25, so plain normalization drew a black card. Stretch to the
    # 99.5th percentile and gamma-lift so the filigree actually reads.
    hi = float(np.percentile(density, 99.5)) or 1.0
    # Inverted on purpose: colouring the density directly painted the EMPTY area
    # with the dark stop and measured luma 29-31 (a black card). The orbit is the
    # ink, so the field is flipped -- dense cells -> dark, bare cells -> paper.
    field = 1.0 - np.clip(density / hi, 0, 1) ** 0.45
    img = Image.fromarray(_colorize(field, _lut(pal)), "RGB")
    # Clamp: at size 512 this works out below 1 px and the blur stops smoothing
    # the density speckle it exists for.
    img = img.filter(ImageFilter.GaussianBlur(radius=max(0.6, work / 900.0)))
    img = img.resize((w, h), Image.LANCZOS)
    return _finish(np.asarray(img), rng, grain=0.012)


def _stroke(width_px: int, ssaa: int, weight: float) -> int:
    """Line width in supersampled pixels, tied to the OUTPUT size.

    A constant width is what made the line generators fail at 2048: measured
    coverage fell to 3.6-10% of the frame because a 2 px stroke is invisible on
    a 2048 px canvas. Tying it to the canvas edge keeps the look consistent.
    """
    return max(1, int(round(ssaa * weight * width_px / 1024.0 * 2.0)))


def gen_harmonograph(rng: np.random.Generator, h: int, w: int, pal: str, ssaa: int) -> Image.Image:
    """Harmonograph: a Lissajous figure with exponential damping."""
    s = max(1, ssaa)
    W, H = w * s, h * s
    img = Image.new("RGB", (W, H), _paper(pal))
    draw = ImageDraw.Draw(img, "RGBA")
    t = np.linspace(0, 1, 26000, dtype=np.float32)
    strokes = int(rng.integers(3, 6))
    for k in range(strokes):
        fx, fy = rng.uniform(1.0, 6.0), rng.uniform(1.0, 6.0)
        px, py = rng.random() * math.tau, rng.random() * math.tau
        dx, dy = rng.uniform(1.5, 5.0), rng.uniform(1.5, 5.0)
        decay = np.exp(-dx * t)
        decay2 = np.exp(-dy * t)
        X = 0.5 + 0.47 * np.sin(math.tau * fx * t + px) * decay
        Y = 0.5 + 0.47 * np.sin(math.tau * fy * t + py) * decay2
        # rotate each stroke so the family fans out instead of stacking
        th = rng.random() * math.pi
        Xr = 0.5 + (X - 0.5) * math.cos(th) - (Y - 0.5) * math.sin(th)
        Yr = 0.5 + (X - 0.5) * math.sin(th) + (Y - 0.5) * math.cos(th)
        col = _ink(pal, int(rng.integers(0, 3)))
        pts = list(zip((Xr * W).tolist(), (Yr * H).tolist()))
        draw.line(pts, fill=col + (120,), width=_stroke(w, s, 1.6), joint="curve")
    if s > 1:
        img = img.resize((w, h), Image.LANCZOS)
    return _finish(np.asarray(img), rng)


def gen_voronoi(rng: np.random.Generator, h: int, w: int, pal: str, ssaa: int) -> Image.Image:
    """Stained glass: nearest-site cells with ink edges. Field at work_res."""
    work = int(min(1300, min(h, w)))
    n_sites = int(rng.integers(60, 170))
    sites = np.column_stack([rng.random(n_sites) * work, rng.random(n_sites) * work])
    labels = np.empty((work, work), dtype=np.int32)
    chunk = 24
    xs = np.arange(work, dtype=np.float32)[None, :, None]
    for y0 in range(0, work, chunk):
        y1 = min(y0 + chunk, work)
        ys = np.arange(y0, y1, dtype=np.float32)[:, None, None]
        dist = (ys - sites[:, 0]) ** 2 + (xs - sites[:, 1]) ** 2
        labels[y0:y1] = dist.argmin(axis=2)

    lut = _lut(pal)
    shade = rng.random(n_sites).astype(np.float32)
    shade = 0.25 + 0.7 * shade
    field = shade[labels]
    rgb = _colorize(field, lut)

    edge = np.zeros((work, work), dtype=bool)
    edge[:-1, :] |= labels[:-1, :] != labels[1:, :]
    edge[:, :-1] |= labels[:, :-1] != labels[:, 1:]
    ink = _rgb(PALETTES[pal][0])
    rgb[edge] = ink

    img = Image.fromarray(rgb, "RGB").resize((w, h), Image.LANCZOS)
    return _finish(np.asarray(img), rng)


def gen_contour(rng: np.random.Generator, h: int, w: int, pal: str, ssaa: int) -> Image.Image:
    """Topographic contours: fractal noise cut into level lines."""
    field = _fbm(rng, h, w, octaves=7, base=3, persistence=0.55)
    field = _normalize(field)
    levels = int(rng.integers(16, 40))
    v = field * levels
    frac = np.abs(v - np.round(v))
    line = frac < float(rng.uniform(0.035, 0.075))
    lut = _lut(pal)
    rgb = _colorize(field, lut)
    rgb[line] = _rgb(PALETTES[pal][-1])
    return _finish(rgb, rng)


def gen_truchet(rng: np.random.Generator, h: int, w: int, pal: str, ssaa: int) -> Image.Image:
    """Truchet tiling: arcs in each cell, orientation chosen per cell."""
    s = max(1, ssaa)
    W, H = w * s, h * s
    img = Image.new("RGB", (W, H), _paper(pal))
    draw = ImageDraw.Draw(img)
    cells = int(rng.integers(6, 20))
    cw, ch = W / cells, H / cells
    widths = [1 + int(rng.integers(2, 5)) for _ in range(3)]
    cols = [_ink(pal, int(rng.integers(0, 3))) for _ in range(3)]
    for gy in range(cells):
        for gx in range(cells):
            x0, y0 = gx * cw, gy * cw
            pick = int(rng.integers(0, 4))
            col = cols[int(rng.integers(0, 3))]
            lw = widths[int(rng.integers(0, 3))]
            if pick == 0:
                draw.arc([x0 - cw, y0, x0 + cw, y0 + 2 * ch], 270, 360, fill=col, width=lw)
                draw.arc([x0, y0 - ch, x0 + 2 * cw, y0 + ch], 180, 270, fill=col, width=lw)
            elif pick == 1:
                draw.arc([x0 - cw, y0, x0 + cw, y0 + 2 * ch], 0, 90, fill=col, width=lw)
                draw.arc([x0, y0 - ch, x0 + 2 * cw, y0 + ch], 90, 180, fill=col, width=lw)
            elif pick == 2:
                draw.arc([x0, y0, x0 + 2 * cw, y0 + 2 * ch], 180, 270, fill=col, width=lw)
                draw.arc([x0 - cw, y0 - ch, x0 + cw, y0 + ch], 0, 90, fill=col, width=lw)
            else:
                draw.arc([x0, y0, x0 + 2 * cw, y0 + 2 * ch], 90, 180, fill=col, width=lw)
                draw.arc([x0 - cw, y0 - ch, x0 + cw, y0 + ch], 270, 360, fill=col, width=lw)
    if s > 1:
        img = img.resize((w, h), Image.LANCZOS)
    return _finish(np.asarray(img), rng)


def _superformula(phi: np.ndarray, m: float, n1: float, n2: float, n3: float) -> np.ndarray:
    t1 = np.abs(np.cos(m * phi / 4.0)) ** n2
    t2 = np.abs(np.sin(m * phi / 4.0)) ** n3
    return (t1 + t2) ** (-1.0 / n1)


def gen_superformula(rng: np.random.Generator, h: int, w: int, pal: str, ssaa: int) -> Image.Image:
    """Mandala rosette: nested superformula curves, each rotated and recoloured."""
    s = max(1, ssaa)
    W, H = w * s, h * s
    img = Image.new("RGB", (W, H), _paper(pal))
    draw = ImageDraw.Draw(img, "RGBA")
    rings = int(rng.integers(6, 13))
    for k in range(rings):
        m = float(rng.integers(4, 14)) + float(rng.integers(0, 2)) * 0.5
        n1 = rng.uniform(0.3, 1.6)
        n2 = rng.uniform(0.3, 1.6)
        n3 = rng.uniform(0.3, 1.6)
        scale = 0.46 * (1.0 - k / (rings + 1.0)) ** 1.15
        rot = rng.random() * math.tau
        phi = np.linspace(0, math.tau, 2200, dtype=np.float32)
        r = _superformula(phi, m, n1, n2, n3)
        r = r / max(1e-6, float(r.max())) * scale
        X = 0.5 + r * np.cos(phi + rot)
        Y = 0.5 + r * np.sin(phi + rot)
        col = _ink(pal, k)
        pts = list(zip((X * W).tolist(), (Y * H).tolist()))
        draw.line(pts + [pts[0]], fill=col + (110,), width=_stroke(w, s, 2.2), joint="curve")
    if s > 1:
        img = img.resize((w, h), Image.LANCZOS)
    return _finish(np.asarray(img), rng)


def gen_dgrowth(rng: np.random.Generator, h: int, w: int, pal: str, ssaa: int) -> Image.Image:
    """Differential growth: a ring grows, nodes repel, the outline folds in on itself."""
    s = max(1, ssaa)
    W, H = w * s, h * s
    n = 120
    ang = np.linspace(0, math.tau, n, endpoint=False)
    # One ring alone measured 4.7% frame coverage at 2048 -- a thin scribble.
    # Three nested rings at different starting radii grow into each other and
    # give the piece body without changing the mechanism.
    rings = [0.11, 0.20, 0.29]
    rad = rings[int(rng.integers(0, len(rings)))]
    nodes = np.column_stack([0.5 + rad * np.cos(ang), 0.5 + rad * np.sin(ang)])
    repulse = 0.0035
    max_nodes = 1600

    for _ in range(220):
        if len(nodes) < max_nodes:
            # split every edge longer than the current mean spacing
            nxt = np.roll(nodes, -1, axis=0)
            seg = np.linalg.norm(nxt - nodes, axis=1)
            if seg.mean() > 0:
                long = seg > seg.mean() * 1.12
                if long.any():
                    mids = (nodes[long] + nxt[long]) * 0.5
                    nodes = np.insert(nodes, np.where(long)[0] + 1, mids, axis=0)
        # neighbour repulsion within a small window along the curve
        k = 8
        force = np.zeros_like(nodes)
        for off in range(1, k + 1):
            diff = nodes - np.roll(nodes, off, axis=0)
            d = np.linalg.norm(diff, axis=1) + 1e-6
            force += diff / d[:, None] * (repulse / d)[:, None]
        nodes = nodes + force * 0.5
        nodes = np.clip(nodes, 0.02, 0.98)

    img = Image.new("RGB", (W, H), _paper(pal))
    draw = ImageDraw.Draw(img, "RGBA")
    for band in range(5):
        off = band * 0.009
        pts = [((x + off) * W, (y + off) * H) for x, y in nodes]
        col = _ink(pal, band)
        draw.line(pts + [pts[0]], fill=col + (150,), width=_stroke(w, s, 2.6), joint="curve")
    if s > 1:
        img = img.resize((w, h), Image.LANCZOS)
    return _finish(np.asarray(img), rng)


GENERATORS = {
    "flow": gen_flow,
    "moire": gen_moire,
    "reaction": gen_reaction,
    "attractor": gen_attractor,
    "harmonograph": gen_harmonograph,
    "voronoi": gen_voronoi,
    "contour": gen_contour,
    "truchet": gen_truchet,
    "superformula": gen_superformula,
    "dgrowth": gen_dgrowth,
}


# -------------------------------------------------------------------- core ---
def generate(name: str, seed: int, size: int, palette: str, ssaa: int = 0) -> Image.Image:
    """Render one piece. Same (name, seed, size, palette) -> identical bytes."""
    if name not in GENERATORS:
        raise SystemExit(f"unknown generator {name!r}; pick from {sorted(GENERATORS)}")
    if palette not in PALETTES:
        raise SystemExit(f"unknown palette {palette!r}; pick from {sorted(PALETTES)}")
    if ssaa <= 0:
        ssaa = 2 if size <= 2048 else 1
    rng = np.random.default_rng(seed)
    return GENERATORS[name](rng, size, size, palette, ssaa)


def metrics(img: Image.Image) -> dict:
    """Measurable quality facts. The test asserts on these, so they can fail."""
    a = np.asarray(img.convert("RGB"), dtype=np.float32)
    lum = a @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    gy, gx = np.gradient(lum[::4, ::4])
    detail = float(np.mean(np.abs(gx)) + np.mean(np.abs(gy)))
    bg = np.median(lum)
    ink = float(np.mean(np.abs(lum - bg) > 6.0))
    return {
        "width": img.width,
        "height": img.height,
        "mode": img.mode,
        "std": round(float(lum.std()), 3),
        "detail": round(detail, 4),
        "ink": round(ink, 4),
        # `std` says "not blank", not "bright enough to sit under text". A whole
        # palette (ink/midnight) renders a legible picture at mean luma 17-25,
        # which reads as a black card on a phone. Measured over the 2048 library:
        # median 23.9, 213/363 below 40.
        "luma": round(float(lum.mean()), 2),
    }


# A piece below these is not written. Measured over 20 real 2048 renders: the
# weakest generator (dgrowth, one thin ring) scored std 7.0 and covered 8.8% of
# the frame -- a near-black card. A batch must FAIL such a render, not ship it.
MIN_STD = 8.0
MIN_DETAIL = 1.0


def _render_job(job: dict) -> dict:
    t0 = time.time()
    try:
        img = generate(job["gen"], job["seed"], job["size"], job["palette"])
    except Exception as exc:  # noqa: BLE001 - one bad seed must not kill the pool
        return {"file": os.path.basename(job["path"]), "gen": job["gen"],
                "seed": job["seed"], "palette": job["palette"],
                "seconds": round(time.time() - t0, 2),
                "rejected": f"generator raised {type(exc).__name__}: {exc}"}
    m = metrics(img)
    m.update({"file": os.path.basename(job["path"]), "gen": job["gen"],
              "seed": job["seed"], "palette": job["palette"],
              "seconds": round(time.time() - t0, 2)})
    if m["std"] < MIN_STD or m["detail"] < MIN_DETAIL:
        m["rejected"] = (f"std {m['std']} < {MIN_STD} or detail {m['detail']} "
                         f"< {MIN_DETAIL}")
        return m
    path = job["path"]
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    # Write to a per-process temp then rename. Measured 2026-11-19 (Gemini review):
    # `img.save(path)` writes in place, so a render killed mid-write left a
    # truncated PNG, and `--skip-existing` then treated that partial file as done
    # forever -- the library silently kept a broken piece. os.replace is atomic, so
    # a reader only ever sees a complete file.
    tmp = f"{path}.{os.getpid()}.part"
    try:
        img.save(tmp, "PNG", optimize=True)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    with open(path, "rb") as fh:
        m["sha256"] = hashlib.sha256(fh.read()).hexdigest()
    return m


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--list", action="store_true", help="list generators and palettes")
    ap.add_argument("--gen", help="generator name")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--size", type=int, default=2048, help="square edge in pixels")
    ap.add_argument("--palette", default="midnight")
    ap.add_argument("--ssaa", type=int, default=0, help="0 = auto")
    ap.add_argument("--out", help="output PNG path (single render)")
    ap.add_argument("--count", type=int, default=0, help="render a batch of N")
    ap.add_argument("--out-dir", default="art_library")
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--skip-existing", action="store_true",
                    help="leave pieces already on disk alone, so a restarted batch "
                         "resumes where it stopped instead of re-rendering them")
    args = ap.parse_args()

    if args.list:
        print("generators:", ", ".join(sorted(GENERATORS)))
        print("palettes:  ", ", ".join(sorted(PALETTES)))
        return 0

    if args.count:
        names = sorted(GENERATORS)
        pals = sorted(PALETTES)
        jobs = []
        for i in range(args.count):
            gen = names[i % len(names)]
            pal = pals[(i // len(names)) % len(pals)]
            seed = args.seed + i
            fname = f"{gen}-{pal}-{seed:05d}.png"
            path = os.path.join(args.out_dir, fname)
            # A long batch is restarted often (a fix, a reboot). Skipping pieces
            # already on disk means a restart resumes instead of redoing hours
            # of work -- measured 2026-11-19, a restart had to keep 85 pictures.
            if args.skip_existing and os.path.exists(path):
                continue
            jobs.append({"gen": gen, "seed": seed, "size": args.size,
                         "palette": pal, "path": path})
        os.makedirs(args.out_dir, exist_ok=True)
        t0 = time.time()
        with Pool(args.jobs) as pool:
            results = pool.map(_render_job, jobs)
        manifest = os.path.join(args.out_dir, "manifest.json")
        existing = []
        if os.path.exists(manifest):
            with open(manifest, encoding="utf-8") as fh:
                existing = json.load(fh).get("items", [])
        kept = [r for r in results if "rejected" not in r]
        dropped = [r for r in results if "rejected" in r]
        merged = {r["file"]: r for r in existing}
        merged.update({r["file"]: r for r in kept})
        items = [merged[k] for k in sorted(merged)]
        with open(manifest, "w", encoding="utf-8") as fh:
            json.dump({"size": args.size, "items": items}, fh, indent=1, ensure_ascii=False)
        dt = time.time() - t0
        print(f"rendered {len(kept)}/{len(results)} in {dt:.1f}s "
              f"({len(kept) / max(dt, 1e-6):.2f} img/s), manifest -> {manifest}")
        for r in dropped:
            print(f"  REJECTED {r['file']}: {r['rejected']}")
        return 0 if not dropped else 1

    if not args.gen or not args.out:
        ap.error("--gen and --out are required for a single render (or use --count)")
    m = _render_job({"gen": args.gen, "seed": args.seed, "size": args.size,
                     "palette": args.palette, "path": args.out})
    print(json.dumps(m, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
