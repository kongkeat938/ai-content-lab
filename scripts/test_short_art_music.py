#!/usr/bin/env python3
"""Guard the Shorts art and music wiring.

The owner asked for a picture and a real bed on every Short. This checks the
parts that are easy to break silently: every channel must point at an art folder,
a music folder and a mood; make_short must pick the same picture for a clip on
every rebuild; and publish_shorts must match the bed to the channel's mood. A
regression here costs a run, and the symptom is a flat-colour, silent video.

    python3 scripts/test_short_art_music.py
"""
from __future__ import annotations

import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, f"{name}.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    fails = []

    ms = load("make_short")
    ps = load("publish_shorts")

    # 1. every channel names an art folder, a music folder and a mood.
    for slug, spec in ps.CHANNELS.items():
        for key in ("art", "music_dir", "mood"):
            if not spec.get(key):
                fails.append(f"{slug}: no {key}")

    # 2. a clip keeps its picture across rebuilds, and two clips differ.
    art = os.path.join(ROOT, "assets", "art", "ch2")
    a1 = ms.pick_art(art, "01")
    if a1 != ms.pick_art(art, "01"):
        fails.append("pick_art is not stable for one id")
    if a1 == ms.pick_art(art, "02"):
        fails.append("pick_art gives the same picture to two ids")

    # 3. the bed matches the channel's mood, and is stable for one id.
    md = os.path.join(ROOT, "assets", "music")
    if os.path.exists(os.path.join(md, "provenance.json")):
        for slug, spec in ps.CHANNELS.items():
            bed = ps.pick_bed(md, "01", spec["mood"])
            if not bed:
                fails.append(f"{slug}: no bed for mood {spec['mood']}")
            elif f"/{spec['mood']}-" not in bed.replace(os.sep, "/"):
                fails.append(f"{slug}: bed {os.path.basename(bed)} is not mood {spec['mood']}")
            elif bed != ps.pick_bed(md, "01", spec["mood"]):
                fails.append(f"{slug}: pick_bed is not stable")
    else:
        print("note: assets/music/provenance.json absent, skipping mood check")

    if fails:
        for f in fails:
            print(f"FAIL: {f}", file=sys.stderr)
        return 1
    print("OK: every channel has art + mood-matched music; picks are stable")
    return 0


if __name__ == "__main__":
    sys.exit(main())
