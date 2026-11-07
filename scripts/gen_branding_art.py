#!/usr/bin/env python3
"""Generate a channel banner and avatar with Pollinations (free, no key).

Measured 2026-11-07: `model=flux` answers 402 service-wide from this pod, while
`model=turbo` still returns a JPEG. The panel chose the concepts (see
docs/PANEL-2026-11-07-banner-CONSENSUS.md): a bright cozy living-room banner and
a steaming tea cup avatar, both bright with no people and no dark tones.

    python3 scripts/gen_branding_art.py --what banner
    python3 scripts/gen_branding_art.py --what avatar
    python3 scripts/gen_branding_art.py --what both
"""
from __future__ import annotations

import argparse
import os
import sys
import time
import urllib.parse
import urllib.request

P = "https://image.pollinations.ai/prompt/"
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "assets", "branding", "ch4", "gen")

JOBS = {
    "banner": (
        "cozy bright living room, warm morning sunlight through a large window, "
        "cream brown peach mustard palette, plush sofa, steaming tea cup, open book, "
        "potted plants, airy cheerful atmosphere, flat vector illustration, "
        "wide horizontal banner, clean empty center strip reserved for text, "
        "bright and airy, no text, no words, no people, no faces, no watermark",
        (2560, 1440), 11),
    "avatar": (
        "steaming ceramic tea cup with heart-shaped steam, cozy flat vector illustration, "
        "warm cream peach mustard tones, bright soft background, centered, minimal, "
        "no people, no faces, no text, no words, no watermark",
        (800, 800), 21),
}


def fetch(prompt: str, w: int, h: int, seed: int, model: str = "turbo",
          tries: int = 8) -> bytes | None:
    q = urllib.parse.quote(prompt)
    for attempt in range(tries):
        url = (f"{P}{q}?width={w}&height={h}&nologo=true&seed={seed}"
               f"&model={model}&referrer=ai-content-lab")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ai-content-lab/1.0"})
            with urllib.request.urlopen(req, timeout=150) as fh:
                data = fh.read()
            if len(data) > 5000 and data[:2] == b"\xff\xd8":
                return data
            print(f"   {attempt}: not a jpeg ({data[:40]!r})")
        except Exception as exc:  # noqa: BLE001 - retry with backoff
            print(f"   {attempt}: {str(exc)[:80]}")
        time.sleep(min(5 * (attempt + 1), 20))
    return None


def run(what: str) -> int:
    os.makedirs(OUT, exist_ok=True)
    for name in (["banner", "avatar"] if what == "both" else [what]):
        prompt, (w, h), seed = JOBS[name]
        print(f"== {name} {w}x{h}")
        data = fetch(prompt, w, h, seed)
        if not data:
            print(f"   {name}: FAILED (service cap)")
            continue
        path = os.path.join(OUT, f"{name}_raw.jpg")
        with open(path, "wb") as fh:
            fh.write(data)
        print(f"   wrote {path} ({len(data)//1024} KB)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--what", choices=("banner", "avatar", "both"), default="both")
    a = ap.parse_args()
    return run(a.what)


if __name__ == "__main__":
    sys.exit(main())
