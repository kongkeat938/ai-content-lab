#!/usr/bin/env python3
"""Guards for `scripts/generative_art.py`. Every check here can fail.

The failure this is written against: a generator that returns a blank canvas, a
single flat colour, or the *same* image as another generator. All three still
produce a valid PNG with a plausible file size, so only a measurement catches
them -- file size proves nothing.

Measured facts this encodes (pod, 4 cores, 1024 px, seed 3):
  * detail (mean |gradient|) separates a drawn image from flat noise;
  * a different generator name at the same seed must differ;
  * the same (gen, seed, size, palette) must be byte-identical -- that is what
    makes an edition sellable ("this seed made this file").
"""
from __future__ import annotations

import hashlib
import io
import os
import shutil
import sys
import tempfile

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import generative_art as ga  # noqa: E402

SIZE = 512
# Measured 2026-11-19 over all 10 generators x 8 palettes at 512 px, seed 3: the
# darkest real piece is moire/ink at 62. The bug this floor catches -- strokes on
# the darkest palette stop -- measured 19-35 and passed every other check here.
MIN_LUMA = 50.0
FAILS: list[str] = []


def check(cond: bool, msg: str) -> None:
    print(("  ok   " if cond else "  FAIL ") + msg)
    if not cond:
        FAILS.append(msg)


def sha(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return hashlib.sha256(buf.getvalue()).hexdigest()


def lum(img: Image.Image) -> np.ndarray:
    a = np.asarray(img.convert("RGB"), dtype=np.float32)
    return a @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)


def main() -> int:
    print("1) every generator draws something (not flat, not blank)")
    rendered: dict[str, Image.Image] = {}
    for name in sorted(ga.GENERATORS):
        img = ga.generate(name, seed=3, size=SIZE, palette="midnight")
        rendered[name] = img
        m = ga.metrics(img)
        # A flat fill has std ~0 and detail ~0. A blank PNG would be all one colour.
        check(m["std"] > 4.0, f"{name}: tonal range std={m['std']} > 4.0")
        check(m["detail"] > 0.05, f"{name}: visible detail={m['detail']} > 0.05")
        check(m["ink"] > 0.05, f"{name}: covers the canvas ink={m['ink']} > 0.05")
        check(img.size == (SIZE, SIZE), f"{name}: size {img.size} == {(SIZE, SIZE)}")
        # A piece can pass every average above while 79% of it is flat background
        # (measured: `reaction` at seed 11 covered 21% of the canvas). Quartile
        # spread catches that: it needs ink in every quarter of the frame.
        l = lum(img)
        q = np.array_split(l, 4, axis=0)
        q = [np.array_split(part, 4, axis=1) for part in q]
        flat = [np.std(cell) < 2.0 for row in q for cell in row]
        check(not any(flat), f"{name}: no quarter of the frame is blank ({sum(flat)}/16 flat)")

    print("2) generators are not copies of each other")
    digests = {n: sha(i) for n, i in rendered.items()}
    check(len(set(digests.values())) == len(digests),
          f"{len(set(digests.values()))} distinct images from {len(digests)} generators")

    print("3) same seed reproduces the same bytes; a new seed does not")
    a = sha(ga.generate("contour", seed=3, size=SIZE, palette="midnight"))
    b = sha(ga.generate("contour", seed=3, size=SIZE, palette="midnight"))
    c = sha(ga.generate("contour", seed=4, size=SIZE, palette="midnight"))
    check(a == b, "seed 3 twice -> identical bytes")
    check(a != c, "seed 3 vs seed 4 -> different bytes")

    print("4) the palette actually reaches the pixels")
    warm = lum(ga.generate("contour", seed=3, size=SIZE, palette="ember")).mean()
    cool = lum(ga.generate("contour", seed=3, size=SIZE, palette="teal")).mean()
    check(abs(warm - cool) > 1.0, f"ember vs teal mean luminance differ ({warm:.1f} vs {cool:.1f})")

    print("5) every generator is bright enough to sit under Thai text")
    # The failure this guards: six line generators painted mid-tones onto the
    # darkest palette stop and measured mean luma 19-35 -- a black card on a
    # phone, while still passing std/detail/ink above. Swept over the real
    # generators, not a hardcoded list, and checked on two palettes so a fix
    # that only works for the lightest one still fails.
    for palette in ("midnight", "sand"):
        for name in sorted(ga.GENERATORS):
            luma = ga.metrics(ga.generate(name, seed=3, size=SIZE,
                                          palette=palette))["luma"]
            check(luma >= MIN_LUMA,
                  f"{name}/{palette}: mean luma {luma:.1f} >= {MIN_LUMA}")

    print("6) no generator leaves a dark frame around a bright interior")
    # Measured 2026-11-19: a faster unpadded Laplacian for reaction-diffusion
    # left the border at luma 14 while the middle sat at 120 -- invisible in any
    # single number, but a black ring on every card. Two conditions, because the
    # step ratio alone did NOT catch it at the test's 512 px (2.13x vs a 2.5x
    # limit): the rim must also clear the same brightness floor as the whole
    # card, and it must not be a cliff against the ring just inside it. dgrowth
    # fades smoothly (rim 145, step 0.68x) which is the look we want.
    for name in sorted(ga.GENERATORS):
        a = lum(ga.generate(name, seed=3, size=SIZE, palette="sand"))
        rim = float(np.concatenate([a[:4].ravel(), a[-4:].ravel(),
                                    a[:, :4].ravel(), a[:, -4:].ravel()]).mean())
        near = float(np.concatenate([a[8:16].ravel(), a[-16:-8].ravel(),
                                     a[8:-8, 8:16].ravel(),
                                     a[8:-8, -16:-8].ravel()]).mean())
        step = near / max(rim, 1.0)
        check(rim >= MIN_LUMA, f"{name}: rim luma {rim:.0f} >= {MIN_LUMA}")
        check(step <= 2.5, f"{name}: rim {rim:.0f} vs just inside {near:.0f} "
                           f"(step {step:.2f}x <= 2.5x)")

    print("7) an unknown name fails loudly instead of drawing nothing")
    # Catch Exception, not SystemExit alone: if the source ever switches from
    # SystemExit to ValueError, a narrow except would crash the guard instead of
    # reporting a failed check, and a crash is easy to mistake for a pass.
    for bad in (("not-a-generator", "midnight"), ("flow", "not-a-palette")):
        try:
            ga.generate(bad[0], seed=1, size=64, palette=bad[1])
            check(False, f"unknown {bad} raised an error")
        except SystemExit:
            check(True, f"unknown {bad} raised SystemExit")
        except Exception as exc:  # noqa: BLE001 - any loud failure is acceptable
            check(True, f"unknown {bad} raised {type(exc).__name__} (loud)")

    print("7) every reaction-diffusion preset listed is alive (swept, not hardcoded)")
    # The bug this guards: a feed/kill pair can settle into a near-uniform field
    # and paint a flat card. Measured: (0.0367, 0.0649) gives std 3.4 while a live
    # pair gives 66-76, so `std` separates them; `ink` does NOT (the flat card
    # scored 0.97 ink because `_finish` grain sits either side of the median).
    # Sweeping the constant means adding a dead pair cannot slip past.
    saved = ga.REACTION_PRESETS
    try:
        for feed, kill in saved:
            ga.REACTION_PRESETS = [(feed, kill)]
            img = ga.generate("reaction", seed=1, size=320, palette="midnight")
            m = ga.metrics(img)
            check(m["std"] > 12.0, f"preset ({feed}, {kill}) alive: std={m['std']} > 12.0")
    finally:
        ga.REACTION_PRESETS = saved

    print("8) a dead preset is caught (the guard above can fail)")
    ga.REACTION_PRESETS = [(0.0367, 0.0649)]
    try:
        dead = ga.generate("reaction", seed=1, size=320, palette="midnight")
        m = ga.metrics(dead)
        check(m["std"] <= 12.0, f"dead preset (0.0367, 0.0649) scores std={m['std']} <= 12.0")
    finally:
        ga.REACTION_PRESETS = saved

    print("9) a killed render never leaves a partial PNG that --skip-existing trusts")
    # Measured 2026-11-19 (Gemini review): img.save(path) wrote in place, so a
    # render interrupted mid-write left a truncated PNG, and --skip-existing then
    # accepted that partial file as finished forever. Two things must hold: a
    # failed save leaves NO file at the destination, and no .part is left behind.
    tmpdir = tempfile.mkdtemp()
    try:
        victim = os.path.join(tmpdir, "piece.png")
        real_save = ga.Image.Image.save

        def exploding_save(self, fp, *a, **kw):
            with open(fp, "wb") as fh:      # simulate a write cut short
                fh.write(b"\x89PNG\r\n\x1a\n truncated")
            raise OSError("simulated crash mid-write")

        ga.Image.Image.save = exploding_save
        try:
            try:
                ga._render_job({"gen": "contour", "seed": 1, "size": SIZE,
                               "palette": "midnight", "path": victim})
            except Exception:  # noqa: BLE001 - the crash is the point
                pass
        finally:
            ga.Image.Image.save = real_save
        check(not os.path.exists(victim),
              "a crashed render leaves no file at the destination path")
        leftovers = [f for f in os.listdir(tmpdir) if f.endswith(".part")]
        check(not leftovers,
              f"and no .part scratch file is left behind (found {leftovers})")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    print()
    if FAILS:
        print(f"FAILED {len(FAILS)} check(s):")
        for f in FAILS:
            print("  -", f)
        return 1
    print(f"PASS: {len(ga.GENERATORS)} generators, all checks held")
    return 0


if __name__ == "__main__":
    sys.exit(main())
