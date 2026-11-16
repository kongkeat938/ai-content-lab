#!/usr/bin/env python3
"""Guards for the ch4 (knowledge genre) brand art. These must be able to FAIL.

K's rule: a bright background, dark type that contrasts (2026-11-07). After the
genre pivot to "เกร็ดความรู้รอบตัว" the old family art (warm living room + tea cup)
was stale, so the art is redrawn in a flat "knowledge" style. If the style is
removed from make_branding.py, or the committed art drifts dark, this fails.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = (ROOT / "scripts" / "make_branding.py").read_text(encoding="utf-8")
BRIGHT_MIN = 0.75   # K's bright-background rule; the old dark look fails this


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def mean_lum(path: Path) -> float:
    a = np.asarray(Image.open(path).convert("RGB")).astype(np.float32) / 255.0
    return float((0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]).mean())


def main() -> int:
    for name in ("knowledge_banner", "knowledge_avatar", "kn_bulb", "kn_background"):
        if not re.search(rf"def {name}\(", SCRIPT):
            fail(f"make_branding.py lost the {name} renderer (knowledge style removed?)")
    if '"knowledge"' not in SCRIPT:
        fail("make_branding.py no longer offers the 'knowledge' style")

    for f, w, h in (("banner_2560x1440.jpg", 2560, 1440), ("avatar_800x800.jpg", 800, 800)):
        p = ROOT / "assets" / "branding" / "ch4" / f
        if not p.exists():
            fail(f"missing {p}")
        im = Image.open(p)
        if im.size != (w, h):
            fail(f"{f} is {im.size}, expected {(w, h)}")
        lum = mean_lum(p)
        if lum < BRIGHT_MIN:
            fail(f"{f} mean luminance {lum:.2f} < {BRIGHT_MIN} -- the background is dark "
                 f"(K forbids dark backgrounds)")
        print(f"ok {f}: {im.size} mean_lum={lum:.2f}")

    print("OK: ch4 brand art is bright and the knowledge style is present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
