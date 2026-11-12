#!/usr/bin/env python3
"""The art fallback must be the branded gradient, never a random stock photo.

K's report (2026-11-12): the Shorts backdrop "looks strange, like it was pulled
from somewhere". It was: when the free AI generator is rate-limited, generate()
fell back to a random Wikimedia Commons photo unrelated to the script. A five-
advisor panel was unanimous that this reads as "cheap / pulled from nowhere".

This locks the chain: generator -> branded gradient, with the Commons photo gone.
The guard can FAIL: it patches the generator to fail and asserts the result is
NOT a commons photo, and it patches from_commons to raise so a re-introduced
Commons fallback would break the build.

    python3 scripts/test_cover_image_source.py
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import gen_cover_image as G  # noqa: E402

FAILS = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" -- {detail}" if detail and not ok else ""))
    if not ok:
        FAILS.append(name)


def main() -> int:
    real_poll = G.from_pollinations
    real_commons = G.from_commons

    print("a rate-limited generator falls back to the branded gradient, not a photo")
    G.from_pollinations = lambda *a, **k: None      # simulate the free API spent
    G.from_commons = lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("generate() called from_commons -- the random stock photo is back"))
    try:
        for style in ("dharma", "family", "genx"):
            data, src = G.generate(style, "calm night", 7, 1080, 1920)
            check(f"{style}: source is procedural, never commons", src == "procedural", src)
            check(f"{style}: produced a real JPEG",
                  bool(data) and data[:2] == b"\xff\xd8", f"{len(data or b'')} bytes")
    finally:
        G.from_pollinations = real_poll
        G.from_commons = real_commons

    print("the gradient is deterministic per seed and unique across seeds")
    a = G.from_procedural(11, "dharma", 1080, 1920)
    b = G.from_procedural(11, "dharma", 1080, 1920)
    c = G.from_procedural(12, "dharma", 1080, 1920)
    check("same seed -> identical bytes", a == b)
    check("different seed -> different bytes", a != c)
    check("the gradient is a real JPEG", a[:2] == b"\xff\xd8")

    print("from_commons still exists (a future on-theme source) but is out of the chain")
    check("from_commons is callable", callable(G.from_commons))

    print()
    if FAILS:
        print(f"FAIL: {len(FAILS)} check(s) failed: {FAILS}")
        return 1
    print("OK: the art fallback is the branded gradient, and Commons is out of the chain")
    return 0


if __name__ == "__main__":
    sys.exit(main())
