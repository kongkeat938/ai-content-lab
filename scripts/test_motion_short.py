#!/usr/bin/env python3
"""The animated Short must actually MOVE, layer by layer.

K asked (2026-11-18) for a still that comes alive: twinkling stars, leaves on the
wind, a character that dances to the music. The failure mode this guards is the
one K is complaining about -- a clip that LOOKS animated in the editor but is a
slide-show on the feed. So this renders real frames from make_motion_short and
measures that each layer changes between frames, and that the motion comes from
the layers (a frozen composite is static).

It can FAIL: `frame_at(..., animate=False)` is the frozen frame; if the moving
layers were no-ops the animated and frozen sequences would be identical and the
"layers move" checks would read ~0.

    python3 scripts/test_motion_short.py     # exit 0 = every layer moves
"""
from __future__ import annotations

import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import make_motion_short as M  # noqa: E402

fails = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global fails
    print(f"  {'ok  ' if ok else 'FAIL'} {name}{(' -- ' + detail) if detail else ''}")
    if not ok:
        fails += 1


def diff(a, b) -> float:
    return float(np.abs(np.asarray(a, "float") - np.asarray(b, "float")).mean())


def main() -> int:
    dur = 8.0
    base = M.backdrop("night", 42, None)
    stars, leaves = M.make_stars(42), M.make_leaves(42)

    f0 = M.frame_at(base, stars, leaves, "night", 0.0, dur)
    f1 = M.frame_at(base, stars, leaves, "night", 0.5, dur)

    # 1) stars twinkle: the star layer alone changes between two instants.
    star0 = M.draw_stars(base, stars, 0.0)
    star1 = M.draw_stars(base, stars, 0.6)
    check("stars twinkle", diff(star0, star1) > 0.05, f"diff {diff(star0, star1):.3f}")

    # 2) leaves flutter: the leaf layer moves between two instants.
    leaf0 = M.draw_leaves(base, leaves, 0.0)
    leaf1 = M.draw_leaves(base, leaves, 0.6)
    check("leaves flutter", diff(leaf0, leaf1) > 0.05, f"diff {diff(leaf0, leaf1):.3f}")

    # 3) the character dances: the mascot region changes between two instants.
    c0 = M.draw_character(base, 0.0, "night", M.beat_accent(0.0))
    c1 = M.draw_character(base, 0.35, "night", M.beat_accent(0.35))
    check("character dances", diff(c0, c1) > 0.5, f"diff {diff(c0, c1):.3f}")

    # 4) the whole frame moves, and it is the layers doing it: the frozen
    #    composite is far more static than the animated one.
    anim = diff(f0, f1)
    fr0 = M.frame_at(base, stars, leaves, "night", 0.0, dur, animate=False)
    fr1 = M.frame_at(base, stars, leaves, "night", 0.5, dur, animate=False)
    frozen = diff(fr0, fr1)
    check("the whole frame moves", anim > 1.0, f"anim diff {anim:.2f}")
    check("motion comes from the layers, not the ken-burns only",
          anim > frozen * 1.5, f"anim {anim:.2f} vs frozen {frozen:.2f}")

    # 5) every mood paints a distinct backdrop (so a story can pick a palette).
    moods = {m: np.asarray(M.backdrop(m, 7, None), "float").mean() for m in M.MOODS}
    check("each mood paints a backdrop", len(set(round(v, 1) for v in moods.values())) >= 3,
          str({k: round(v, 1) for k, v in moods.items()}))

    print(f"\n{'all checks passed' if not fails else f'{fails} check(s) FAILED'}")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
