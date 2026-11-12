#!/usr/bin/env python3
"""Generate one unique on-theme image per video, with no paid service.

K's rule (2026-11-06): no two videos may share an image. The rail broke that two
ways -- `build_night.py` used a single default background for every build, and the
thumbnail pass drew the video's own frame, so it inherited the same picture. This
makes a fresh image per video instead.

Free path, measured from the pod 2026-11-06:
  * Pollinations text-to-image, no key. It rate-limits per IP: roughly half of the
    calls answer 402 FREE_LIMIT, but a retry with backoff gets through (measured
    4/8 first-try, and every video eventually succeeded). This is the primary.
  * Wikimedia Commons, no key, as the fallback when Pollinations is spent. Subjects
    are hit-or-miss, so it is only the safety net, not the first choice.
  * The Gemini image models answer 429 quota 0 on the free key, so they are not used.

    python3 scripts/gen_cover_image.py --style dharma --seed 7 \
        --prompt "calm night, soft candle, misty mountains" --out art.jpg

Each image is seeded, so a re-run of the same video regenerates the same picture
rather than a different one -- the ledger then stays meaningful.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

UA = "ai-content-lab/1.0 (free-content pipeline; contact: kongkeat938)"
POLL = "https://image.pollinations.ai/prompt/"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"

# Two house styles, so the art matches the channel. The negative cues keep the
# generator away from faces-with-text and cluttered scenes a thumbnail cannot use.
STYLES = {
    "dharma": ("serene Thai Buddhist night scene, soft moonlight, mist, candle, "
               "calm minimal illustration, muted indigo and gold, no text, no words, "
               "no watermark, painterly, centered subject"),
    "family": ("warm Thai family home at evening, soft golden lamp light, cozy "
               "illustration, gentle nostalgic mood, muted warm colours, no text, "
               "no words, no watermark, painterly, centered subject"),
    "genx": ("quiet reflective scene for a grown-up reader, soft morning light "
             "through a window, a single chair or a cup of tea, calm muted earthy "
             "palette, minimal illustration, no text, no words, no watermark, "
             "painterly, centered subject"),
}


def _get(url: str, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as fh:
        return fh.read()


def _strip_watermark(data: bytes) -> bytes:
    """Pollinations stamps 'pollinations.ai' in the bottom-right corner even with
    nologo=true (measured 2026-11-06: bright text at x 87-99%, y 95.5-98%). Crop
    the bottom band off so the art that reaches the thumbnail is clean."""
    from PIL import Image
    im = Image.open(io.BytesIO(data)).convert("RGB")
    w, h = im.size
    im = im.crop((0, 0, w, int(h * 0.94)))  # drop the watermark band
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=92)
    return buf.getvalue()


def from_pollinations(prompt: str, seed: int, w: int, h: int, tries: int = 8) -> bytes | None:
    """Pollinations rate-limits per IP; back off and retry rather than give up."""
    q = urllib.parse.quote(prompt)
    for t in range(tries):
        url = (f"{POLL}{q}?width={w}&height={h}&nologo=true&seed={seed}"
               f"&referrer=ai-content-lab")
        try:
            data = _get(url)
            if len(data) > 5000 and data[:2] == b"\xff\xd8":  # a real JPEG
                return _strip_watermark(data)
        except urllib.error.HTTPError as e:
            if e.code not in (402, 429, 500, 502, 503, 504):
                return None
        except Exception:  # noqa: BLE001 - keep trying
            pass
        time.sleep(min(2 ** t, 20))
    return None


def from_commons(query: str, w: int, h: int, seed: int = 0) -> bytes | None:
    """Fallback: a real photo under a commercial-use licence.

    seed selects among the results, so two clips with a similar prompt do not both
    fall back to the identical photo (the owner's no-repeat rule). Every result is
    licence-checked: a monetised video cannot carry an NC/ND image, and the API
    does not filter for us."""
    params = urllib.parse.urlencode({
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": f"filetype:bitmap {query}", "gsrnamespace": "6",
        "gsrlimit": "20", "prop": "imageinfo",
        "iiprop": "url|extmetadata", "iiurlwidth": str(max(w, 1280)),
    })
    try:
        d = json.loads(_get(f"{COMMONS_API}?{params}", timeout=40))
    except Exception:  # noqa: BLE001
        return None
    pages = [p for p in d.get("query", {}).get("pages", {}).values()
             if _commons_license_ok(p.get("imageinfo", [{}])[0])]
    if not pages:
        return None
    pages = pages[seed % len(pages):] + pages[:seed % len(pages)]
    # prefer landscape, licence-safe results
    for p in pages:
        info = p.get("imageinfo", [{}])[0]
        url = info.get("thumburl") or info.get("url")
        if not url:
            continue
        try:
            data = _get(url, timeout=60)
            if len(data) > 5000:
                return data
        except Exception:  # noqa: BLE001
            continue
    return None


# Commons licences safe for a monetisable video: public domain or attribution-only.
_COMMONS_OK = ("cc0", "public domain", "pdm", "cc by", "cc-by", "attribution")
_COMMONS_BAD = ("nc", "nd", "noncommercial", "gfdl", "sampling", "-sa", "share-alike")


def _commons_license_ok(info: dict) -> bool:
    meta = info.get("extmetadata", {})
    short = str(meta.get("LicenseShortName", {}).get("value", "")).lower()
    terms = str(meta.get("UsageTerms", {}).get("value", "")).lower()
    text = f"{short} {terms}"
    if not short and not terms:
        return False
    if any(t in text for t in _COMMONS_BAD):
        return False
    return any(t in text for t in _COMMONS_OK)


def from_procedural(seed: int, style: str, w: int, h: int) -> bytes:
    """Last-resort art that never fails: a seeded abstract in the channel palette.

    Pollinations rate-limits and Commons is hit-or-miss, so a scheduled job must
    still end with an image. This draws a deterministic gradient plus soft light
    blobs, seeded by the video, so it is unique per video and stable on a re-run.
    """
    import math
    import random
    from PIL import Image, ImageDraw, ImageFilter

    rnd = random.Random(seed)
    palettes = {
        "dharma": [(14, 18, 46), (26, 34, 74), (52, 44, 92), (120, 96, 60)],
        "family": [(60, 34, 22), (110, 62, 34), (176, 120, 62), (232, 196, 132)],
        "genx": [(28, 27, 26), (58, 54, 48), (120, 104, 80), (214, 196, 160)],
    }
    cols = palettes.get(style, palettes["dharma"])
    im = Image.new("RGB", (w, h), cols[0])
    d = ImageDraw.Draw(im)
    # vertical gradient between the two darkest tones
    for y in range(h):
        t = y / h
        c = tuple(int(cols[0][i] * (1 - t) + cols[1][i] * t) for i in range(3))
        d.line([(0, y), (w, y)], fill=c)
    # seeded light blobs -> soft glow, no text
    glow = Image.new("L", (w, h), 0)
    gd = ImageDraw.Draw(glow)
    for _ in range(rnd.randint(3, 6)):
        cx, cy = rnd.randint(0, w), rnd.randint(0, h)
        r = rnd.randint(w // 8, w // 3)
        gd.ellipse([cx - r, cy - r, cx + r, cy + r], fill=rnd.randint(60, 140))
    glow = glow.filter(ImageFilter.GaussianBlur(w // 12))
    im = Image.composite(Image.new("RGB", (w, h), cols[3]), im, glow)
    # a seeded horizon line for structure
    hy = rnd.randint(int(h * 0.55), int(h * 0.75))
    d.rectangle([0, hy, w, h], fill=cols[2])
    im = im.filter(ImageFilter.GaussianBlur(1.2))
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def generate(style: str, prompt: str, seed: int, w: int, h: int) -> tuple[bytes | None, str]:
    """Pick one image for a video: the AI generator, else the branded gradient.

    A random Wikimedia photo is deliberately NOT used as a fallback (2026-11-12):
    a five-advisor panel was unanimous that an off-theme stock photo reads as
    "cheap / pulled from nowhere" and breaks the calm mood, while a branded
    gradient reads as a design choice. So a rate-limited generator now lands on
    from_procedural() -- a seeded gradient in the channel palette -- instead of a
    random photo. from_commons() is kept for a future on-theme licensed source but
    is no longer in the chain.
    """
    style_cues = STYLES.get(style, "")
    full = f"{prompt}, {style_cues}" if prompt else style_cues
    data = from_pollinations(full, seed, w, h)
    if data:
        return data, "pollinations"
    return from_procedural(seed, style, w, h), "procedural"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("--prompt", default="", help="subject, in English, no text")
    ap.add_argument("--style", default="dharma", choices=list(STYLES))
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=720)
    a = ap.parse_args()

    data, src = generate(a.style, a.prompt, a.seed, a.width, a.height)
    if not data:
        print("no image available", file=sys.stderr)
        return 1
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "wb") as fh:
        fh.write(data)
    print(f"{a.out} ({len(data)//1024} KB, {src}, md5 {hashlib.md5(data).hexdigest()[:8]})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
