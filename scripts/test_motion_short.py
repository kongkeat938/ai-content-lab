#!/usr/bin/env python3
"""The animated Short must MOVE, AND the look must MATCH the story (K, 2026-11-18).

K's rule: "the one you use has to look at the story too, not just be a cartoon".
So a dharma sleep clip must NOT get a dancing mascot -- it gets calm ambient motion
(twinkle + drifting petals + a breathing glow). The lively mascot is only for the
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


def diff(a, b) -> float:
    return float(np.abs(np.asarray(a, "float") - np.asarray(b, "float")).mean())


def main() -> int:
    dur = 8.0
    base = M.backdrop("night", 42, None)
    prof = M.profile_for("dharma")
    stars, leaves = M.layers_for(42, prof)

    f0 = M.frame_at(base, stars, leaves, "night", 0.0, dur, prof=prof)
    f1 = M.frame_at(base, stars, leaves, "night", 0.5, dur, prof=prof)

    # 1) the moving layers change between two instants.
    star0 = M.draw_stars(base, stars, 0.0, speed=prof["stars"][1])
    star1 = M.draw_stars(base, stars, 0.6, speed=prof["stars"][1])
    check("stars twinkle", diff(star0, star1) > 0.05, f"diff {diff(star0, star1):.3f}")

    leaf0 = M.draw_leaves(base, leaves, 0.0)
    leaf1 = M.draw_leaves(base, leaves, 0.6)
    check("drift moves (petals/leaves/motes)", diff(leaf0, leaf1) > 0.05,
          f"diff {diff(leaf0, leaf1):.3f}")

    br0 = M.draw_breath(base, 0.0)
    br1 = M.draw_breath(base, 1.0)
    check("the calm genres breathe (glow pulses)", diff(br0, br1) > 0.02,
          f"diff {diff(br0, br1):.3f}")

    # 2) the whole frame moves, and it is the layers doing it.
    anim = diff(f0, f1)
    fr0 = M.frame_at(base, stars, leaves, "night", 0.0, dur, animate=False, prof=prof)
    fr1 = M.frame_at(base, stars, leaves, "night", 0.5, dur, animate=False, prof=prof)
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
          dharm["drift"][3] == "petal", dharm["drift"][3])

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

    # 7) the speech is slower than the house rate (K: "slow the speaking pace down").
    check("this rail speaks slower than the house -15%", M.RATE.endswith("%")
          and int(M.RATE.strip("%")) < -15, f"RATE={M.RATE} vs house {MS.RATE}")

    print(f"\n{'all checks passed' if not fails else f'{fails} check(s) FAILED'}")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
