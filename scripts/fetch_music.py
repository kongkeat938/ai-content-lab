#!/usr/bin/env python3
"""Fetch real CC0 instrumental music beds from Openverse, and prove each is music.

The pack that stood here first (AERIS) turned out to be six single sine tones,
not music: every Short carried a beep. So this script does not trust a filename
or a licence note -- it measures every download with the same test the validator
uses (scripts/test_music_beds.py) and refuses a bed that is not music.

Openverse's audio index fronts Freesound; filtering to `license=cc0` keeps the
download free of attribution conditions (credit is still written to
provenance.json and shown on the page). The bed is trimmed to a loopable length
and levelled well under the voice, so the mix stage only nudges it.

    python3 scripts/fetch_music.py --out-dir assets/music
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request

API = "https://api.openverse.org/v1/audio/"
UA = {"User-Agent": "ai-content-lab/1.0 (free-content pipeline; contact: kongkeat938)"}
# One query per mood. A bed is instrumental by construction: a vocal bed fights
# the narration for the ear (panel advice, 2026-11-07).
MOODS = {
    "calm": "calm ambient music",
    "warm": "acoustic guitar instrumental",
    "sad": "sad piano instrumental",
    "hopeful": "positive background music",
    "mystic": "mystic ambient music",
    "epic": "epic cinematic music",
}


def _validator():
    """Load measure() from the committed validator so the test is never copied."""
    here = os.path.dirname(os.path.abspath(__file__))
    spec = importlib.util.spec_from_file_location(
        "test_music_beds", os.path.join(here, "test_music_beds.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.measure


def search(query: str, min_sec: int = 60, page: int = 8) -> list:
    q = urllib.parse.urlencode({"q": query, "license": "cc0", "page_size": page,
                                "duration_min": min_sec, "duration_max": 600})
    req = urllib.request.Request(f"{API}?{q}", headers=UA)
    return json.load(urllib.request.urlopen(req, timeout=25)).get("results", [])


def to_bed(src: str, out: str, seconds: float = 50.0) -> bool:
    """Trim to a loopable bed at a level that sits under a narration.

    -22 LUFS is well below the voice, so the mix stage only nudges it; the fades
    stop the loop point clicking when the bed repeats under a longer clip.
    """
    af = (f"atrim=start=8:duration={seconds},asetpts=PTS-STARTPTS,"
          f"afade=t=in:d=1.5,afade=t=out:st={seconds - 2}:d=2,"
          "loudnorm=I=-22:TP=-4:LRA=11")
    r = subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                        "-i", src, "-af", af, "-ar", "48000", "-ac", "2",
                        "-b:a", "96k", out], capture_output=True, text=True)
    if r.returncode != 0:
        print(f"    ffmpeg failed: {r.stderr[-140:]}", file=sys.stderr)
        return False
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default="assets/music")
    ap.add_argument("--seconds", type=float, default=50.0)
    args = ap.parse_args()
    measure = _validator()

    os.makedirs(args.out_dir, exist_ok=True)
    tmp = os.path.join(args.out_dir, "_tmp")
    os.makedirs(tmp, exist_ok=True)

    beds, n = [], 0
    for mood, query in MOODS.items():
        print(f"== {mood}: {query}")
        for r in search(query):
            url = r.get("url")
            if not url:
                continue
            raw = os.path.join(tmp, f"{mood}.mp3")
            try:
                with open(raw, "wb") as fh:
                    fh.write(urllib.request.urlopen(
                        urllib.request.Request(url, headers=UA), timeout=60).read())
            except Exception as e:  # noqa: BLE001
                print(f"   download failed: {str(e)[:70]}", file=sys.stderr)
                continue
            dest = os.path.join(args.out_dir, f"bed-{mood}.mp3")
            if not to_bed(raw, dest, args.seconds):
                continue
            try:
                m = measure(dest)
            except Exception as e:  # noqa: BLE001
                print(f"   measure failed: {str(e)[:70]}", file=sys.stderr)
                continue
            if not m["is_music"]:
                print(f"   skip (not music): share={m['tone_share']} parts={m['partials']}")
                continue
            beds.append({"file": os.path.basename(dest), "id": f"bed-{mood}", "mood": mood,
                         "title": r.get("title"), "creator": r.get("creator"),
                         "source": r.get("foreign_landing_url"), "license": "CC0-1.0"})
            print(f"   OK share={m['tone_share']} parts={m['partials']} | {str(r.get('title'))[:40]}")
            n += 1
            break
        raw = os.path.join(tmp, f"{mood}.mp3")
        if os.path.exists(raw):
            os.remove(raw)

    with open(os.path.join(args.out_dir, "provenance.json"), "w", encoding="utf-8") as fh:
        json.dump({"pack": "Openverse / Freesound CC0", "license": "CC0-1.0",
                   "note": "Every bed measured as music before use -- see "
                           "scripts/test_music_beds.py.",
                   "credit": "See each bed's creator (CC0-1.0, Openverse/Freesound)",
                   "beds": beds}, fh, ensure_ascii=False, indent=2)
    print(f"total beds: {n}/{len(MOODS)} -> {args.out_dir}")
    return 0 if n == len(MOODS) else 1


if __name__ == "__main__":
    sys.exit(main())
