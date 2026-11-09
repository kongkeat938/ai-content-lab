#!/usr/bin/env python3
"""Guard the Shorts art and music wiring, and the owner's no-repeat rule.

The owner asked for a picture and a real bed on every Short, and then made it a
hard rule (2026-11-09): no two clips may share an image or a bed, ever, and the
synthesised "hum" must never come back. Measured the same day, the old wiring
broke both: pick_art over a 10-still pool gave each ch4 image to ~5 of 49 live
Shorts (ch2 to ~11 of 104), pick_bed gave every Short of a channel the same
mood-matched file, and the long-form rail looped a make_bed.py sine drone.

This checks the parts that break silently: every channel must name a style and a
music folder; a generated image must differ per clip and be stable on a rebuild;
a bed must differ per clip and be stable; and make_compilation must not fall back
to a synthesised drone.

    python3 scripts/test_short_art_music.py
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
import tempfile

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
    gc = load("gen_cover_image")
    mc = load("make_compilation")

    # 1. every channel names a style and a music folder and a mood.
    for slug, spec in ps.CHANNELS.items():
        for key in ("art_style", "music_dir", "mood"):
            if not spec.get(key):
                fails.append(f"{slug}: no {key}")

    # 2. a generated image differs per clip and is stable on a rebuild. Uses the
    #    offline procedural path so the guard needs no network.
    a = gc.from_procedural(11, "family", 320, 568)
    b = gc.from_procedural(12, "family", 320, 568)
    if hashlib.md5(a).hexdigest() == hashlib.md5(b).hexdigest():
        fails.append("two different seeds produced the same image")
    d = tempfile.mkdtemp()
    p1 = ms.unique_art(os.path.join(d, "s1"), "s1", "hook", "family", None, None)
    p2 = ms.unique_art(os.path.join(d, "s2"), "s2", "hook", "family", None, None)
    if p1 == p2:
        fails.append("unique_art gave two clips the same picture")
    if ms.unique_art(os.path.join(d, "s1"), "s1", "hook", "family", None, None) != p1:
        fails.append("unique_art is not stable on a rebuild")

    # 3. a bed differs per clip and is stable. A 6-bed library must not hand the
    #    same bed to two of the first six clips.
    md = os.path.join(ROOT, "assets", "music")
    led = os.path.join(tempfile.mkdtemp(), "bed_ledger.json")
    ids = ["51", "52", "53", "54", "55", "56"]
    picks = [ps.pick_bed(md, sid, "warm", led) for sid in ids]
    if any(p is None for p in picks):
        fails.append("pick_bed returned nothing")
    elif len(set(picks)) != len(ids):
        fails.append(f"pick_bed repeated a bed across six clips: {picks}")
    if ps.pick_bed(md, "51", "warm", led) != picks[0]:
        fails.append("pick_bed is not stable for one id")

    # 4. no synthesised drone: make_compilation must not import make_bed, and a
    #    bed-for with no real music must come back empty, never a hum.
    src = open(os.path.join(HERE, "make_compilation.py"), encoding="utf-8").read()
    if "import make_bed" in src:
        fails.append("make_compilation still imports make_bed (the forbidden drone)")
    beds = [p for p in mc.music_beds() if mc.is_music(p)]
    if not beds:
        fails.append("no validator-passing bed in assets/music")
    with open(os.path.join(md, "provenance.json")) as fh:
        mood_of = {b["file"]: b.get("mood") for b in json.load(fh).get("beds", [])}
    for slug, spec in ps.CHANNELS.items():
        if not any(mood_of.get(os.path.basename(p)) == spec["mood"] for p in beds):
            fails.append(f"{slug}: no bed for mood {spec['mood']}")

    if fails:
        for f in fails:
            print(f"FAIL: {f}", file=sys.stderr)
        return 1
    print("OK: unique art + bed per clip, stable, and no synthesised drone")
    return 0


if __name__ == "__main__":
    sys.exit(main())
