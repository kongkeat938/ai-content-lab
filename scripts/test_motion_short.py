#!/usr/bin/env python3
"""The animated Short must MOVE, AND the look must MATCH the story (K, 2026-11-18).

K's rule: "the one you use has to look at the story too, not just be a cartoon".
So a dharma sleep clip must NOT get a dancing mascot -- it gets calm ambient motion
(twinkle + drifting petals). The lively mascot is only for the
curious knowledge ("why?") genre. An unknown genre gets the calm default.

Two things this guard measures, both of which can FAIL:

  1. every layer MOVES frame-to-frame, and the motion comes from the layers (a frozen
     composite is static);
  2. the profile MATCHES the genre -- dharma/genx carry NO character, knowledge does;
     an unknown genre falls back to calm.

    python3 scripts/test_motion_short.py     # exit 0 = moves + matches the story
"""
from __future__ import annotations

import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import make_motion_short as M  # noqa: E402
MS = M.MS

fails = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global fails
    print(f"  {'ok  ' if ok else 'FAIL'} {name}{(' -- ' + detail) if detail else ''}")
    if not ok:
        fails += 1


def _lapvar(im) -> float:
    a = np.asarray(im.convert("L"), "float")
    k = np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]], "float")
    from numpy.lib.stride_tricks import sliding_window_view
    return float((sliding_window_view(a, (3, 3)) * k).sum(axis=(2, 3)).var())


def _src(fn) -> str:
    import inspect
    return inspect.getsource(fn)


def diff(a, b) -> float:
    return float(np.abs(np.asarray(a, "float") - np.asarray(b, "float")).mean())


def main() -> int:
    dur = 8.0
    base = M.backdrop("night", 42, None)
    prof = M.profile_for("dharma")
    stars, fx = M.layers_for(42, prof)

    # The canvas became 4K on 2026-11-23 while every size/velocity in the builder was
    # tuned on a 1080-wide frame. Unscaled, the design came out at half the intended
    # size and the motion fell under its thresholds (measured 2026-11-24: stars
    # 0.041 vs >0.05, whole frame 0.41 vs >0.5). This can FAIL: drop SCALE from a
    # constant and the number no longer matches the authored value.
    s = M.SCALE
    check("the design scales with the canvas", abs(s - M.W / 1080) < 1e-9,
          f"SCALE={s}")
    check("star size scales", M.make_stars(1, n=1)[0]["s"] >= 6 * s * 0.99,
          f"star {M.make_stars(1, n=1)[0]['s']:.1f} vs >= {6 * s * 0.99:.1f}")
    leaf_vy = M.KINDS["leaf"]["vy"][0]
    check("particle velocity scales", abs(leaf_vy - 90 * s) < 0.51,
          f"leaf vy {leaf_vy:.1f} vs {90 * s:.1f}")

    f0 = M.frame_at(base, stars, fx, "night", 0.0, dur, prof=prof)
    f1 = M.frame_at(base, stars, fx, "night", 0.5, dur, prof=prof)

    # 1) the moving layers change between two instants.
    star0 = M.draw_stars(base, stars, 0.0, speed=prof["stars"][1])
    star1 = M.draw_stars(base, stars, 0.6, speed=prof["stars"][1])
    check("stars twinkle", diff(star0, star1) > 0.05, f"diff {diff(star0, star1):.3f}")

    leaf0 = M.draw_fx(base, fx[0], 0.0)
    leaf1 = M.draw_fx(base, fx[0], 0.6)
    check("drift moves (petals/leaves/motes)", diff(leaf0, leaf1) > 0.05,
          f"diff {diff(leaf0, leaf1):.3f}")

    # K (2026-11-18): "just the sparkle is enough" -- the calm genres must carry NO
    # pulsing glow disc, and no layer may leave a drawn circle on the frame. This can
    # FAIL: re-adding a breath/glow layer to a calm profile trips it.
    check("the calm genres carry no pulsing glow layer",
          "breath" not in prof and not hasattr(M, "draw_breath"),
          f"profile keys {sorted(prof)}")

    # 2) the whole frame moves, and it is the layers doing it.
    anim = diff(f0, f1)
    fr0 = M.frame_at(base, stars, fx, "night", 0.0, dur, animate=False, prof=prof)
    fr1 = M.frame_at(base, stars, fx, "night", 0.5, dur, animate=False, prof=prof)
    frozen = diff(fr0, fr1)
    check("the whole frame moves", anim > 0.5, f"anim diff {anim:.2f}")
    check("motion comes from the layers, not the ken-burns only",
          anim > frozen * 1.5, f"anim {anim:.2f} vs frozen {frozen:.2f}")

    # 3) the LOOK matches the story (K's rule). This is the part that must FAIL if
    #    someone gives dharma the dancing mascot.
    dharm = M.profile_for("dharma")
    genx = M.profile_for("genx")
    know = M.profile_for("knowledge")
    check("dharma has NO dancing character", dharm["character"] is None,
          f"character={dharm['character']}")
    check("genx has NO dancing character", genx["character"] is None,
          f"character={genx['character']}")
    check("knowledge DOES get the mascot", know["character"] == "mascot",
          f"character={know['character']}")
    check("an unknown genre falls back to the calm default",
          M.profile_for("banana") is M.profile_for(M.DEFAULT_GENRE)
          and M.profile_for(None)["character"] is None)
    check("dharma drifts petals, not leaves",
          "petal" in [k for k, _n in dharm["fx"]], str(dharm["fx"]))

    # 4) the mascot really dances (the knowledge profile only).
    c0 = M.draw_character(base, 0.0, "night", M.beat_accent(0.0))
    c1 = M.draw_character(base, 0.35, "night", M.beat_accent(0.35))
    check("the mascot dances", diff(c0, c1) > 0.5, f"diff {diff(c0, c1):.3f}")

    # 5) every mood paints a distinct backdrop (so a story can pick a palette).
    moods = {m: np.asarray(M.backdrop(m, 7, None), "float").mean() for m in M.MOODS}
    check("each mood paints a backdrop", len(set(round(v, 1) for v in moods.values())) >= 3,
          str({k: round(v, 1) for k, v in moods.items()}))

    # 6) a sun/moon is present and bright (K, 2026-11-18: "make it a sun/moon image").
    sky = M.backdrop("night", 7, None).crop((int(M.W * 0.72) - 150, int(M.H * 0.15) - 150,
                                             int(M.W * 0.72) + 150, int(M.H * 0.15) + 150))
    sky_a = np.asarray(sky, "float")
    bright = float((sky_a.mean(axis=2) > 200).mean())
    check("the sky carries a bright sun/moon", bright > 0.25, f"bright fraction {bright:.2f}")
    day = np.asarray(M.backdrop("sunset", 7, None), "float").mean()
    night = np.asarray(M.backdrop("night", 7, None), "float").mean()
    check("the sun/moon differs by mood (warm sun vs pale moon)", abs(day - night) > 5,
          f"sunset {day:.1f} vs night {night:.1f}")

    # 7) K (2026-11-19): "ความละเอียดภาพไม่สวย ขุ่นมัวไม่เอา ขอสดใส" -- the picture must
    #    be SHARP. `backdrop()` used to blur the art by 1.5px, which threw away 85% of
    #    its detail (LapVar 6.8 -> 1.0). This can FAIL: re-adding any blur trips it.
    from PIL import Image as _I
    art = "/tmp/_guard_art.png"
    _I.new("RGB", (M.W, M.H), (90, 120, 150)).save(art)
    detail = _I.new("RGB", (M.W, M.H))
    px = detail.load()
    for yy in range(0, M.H, 4):
        for xx in range(0, M.W, 4):
            px[xx, yy] = (255, 255, 255)
    detail.save(art)
    check("backdrop() does NOT blur the art (K: no ขุ่นมัว)",
          _lapvar(M.backdrop("night", 3, art)) > _lapvar(_I.open(art)) * 0.9,
          f"lapvar {_lapvar(M.backdrop('night', 3, art)):.1f} vs source {_lapvar(_I.open(art)):.1f}")
    check("ken_burns resamples with lanczos, not bicubic",
          "LANCZOS" in _src(M.ken_burns) and "BICUBIC" not in _src(M.ken_burns))

    # 8) K (2026-11-19): the caption must sit in the UPPER-MIDDLE, not at the foot
    #    where the Shorts UI covers it. Measured from the pixels it actually paints.
    fr = M.frame_at(base, stars, fx, "night", 0.0, dur, prof=prof)
    capped = M.caption(fr, "หายใจเข้าลึก ๆ แล้วปล่อยออกช้า ๆ")
    _d = np.asarray(capped, "float") - np.asarray(fr, "float")
    rows = np.where(np.abs(_d).sum(axis=(1, 2)) > 50)[0]
    cy = (rows.min() + rows.max()) / 2 / M.H if len(rows) else 1.0
    check("caption sits above the middle (not under the Shorts UI)", cy < 0.5,
          f"caption centre at {cy:.0%} of height")
    check("caption stays clear of the bottom UI band", rows.max() / M.H < 0.72,
          f"lowest caption row at {rows.max() / M.H:.0%}")

    # 9) K (2026-11-19): "ฝน วงกลมเล็กๆ ใบไม้ร่วง หิมะ น้ำตก ภูเขาไฟระเบิด หรืออะไรก็ได้
    #    อีกเยอะ" -- the effect set must be RICH, and each effect must MOVE. This
    #    can FAIL: dropping back to one drifting kind trips the count check.
    check("many effect kinds exist (not just one)", len(M.KINDS) >= 10,
          f"{len(M.KINDS)} kinds: {sorted(M.KINDS)}")
    for want in ("rain", "snow", "leaf", "waterfall", "lava", "bubble", "heart", "confetti"):
        check(f"effect '{want}' is available", want in M.KINDS)
    moving = []
    for kind in sorted(M.KINDS):
        parts = M.make_particles(7, 12, kind, salt=1)
        a = M.draw_fx(base, parts, 0.0)
        b = M.draw_fx(base, parts, 0.45)
        moving.append((kind, diff(a, b)))
    still = [k for k, d in moving if d <= 0.02]
    check("every effect actually moves", not still,
          f"static: {still}" if still else f"{len(moving)} kinds move")
    # a profile must combine several effects, not one.
    thin = [g for g, p in M.PROFILES.items() if len(p["fx"]) < 2]
    check("every profile layers at least 2 effects", not thin, f"thin: {thin}" if thin else "all >= 2")

    # 7) the speech is slower than the house rate (K: "slow the speaking pace down").
    check("this rail speaks slower than the house -15%", M.RATE.endswith("%")
          and int(M.RATE.strip("%")) < -15, f"RATE={M.RATE} vs house {MS.RATE}")

    print(f"\n{'all checks passed' if not fails else f'{fails} check(s) FAILED'}")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
