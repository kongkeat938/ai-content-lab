#!/usr/bin/env python3
"""Fetch real instrumental music beds from the AERIS Music free pack.

The owner supplies this pack (CC0-1.0) and asks for its real music under the
Shorts instead of a synthesised pad. Its `beds/` are instrumental with no
vocals, which is what a bed under a spoken Thai narration needs -- a vocal bed
fights the voice for the ear (panel advice, 2026-11-07).

The index lives on GitHub, so the pod and CI can both read it. This script reads
the index, downloads the instrumental beds, and writes the mood of each one
beside it so the publish rail can match a bed to the mood of a clip.

    python3 scripts/fetch_music.py --out-dir assets/music
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.request

RAW = ("https://raw.githubusercontent.com/aerismusic8-alt/"
       "aeris-drive-automation/main/share/aeris-music")
UA = {"User-Agent": "ai-content-lab/1.0 (free-content pipeline; contact: kongkeat938)"}


def get(url: str, timeout: int = 60) -> bytes:
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA),
                                  timeout=timeout).read()


def to_bed(src: str, out: str, seconds: float) -> bool:
    """Trim to a loopable bed at a level that sits under a narration.

    -22 LUFS is well below the voice, so the mix stage only nudges it; the fades
    stop the loop point clicking when the bed repeats under a longer clip.
    """
    af = (f"atrim=start=6:duration={seconds},asetpts=PTS-STARTPTS,"
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
    ap.add_argument("--catalog", default=f"{RAW}/catalog.json")
    ap.add_argument("--seconds", type=float, default=45.0)
    ap.add_argument("--with-songs", action="store_true",
                    help="also fetch the full songs (vocal; off by default)")
    args = ap.parse_args()

    cat = json.loads(get(args.catalog))
    print(f"pack: {cat.get('pack')}  license: {cat.get('license')}")
    os.makedirs(args.out_dir, exist_ok=True)
    tmp = os.path.join(args.out_dir, "_tmp")
    os.makedirs(tmp, exist_ok=True)

    items = [(b["id"], b["mood"], b["file"]) for b in cat.get("beds", [])]
    if args.with_songs:
        items += [(s["id"], s["mood"], s["instrumental"]) for s in cat.get("songs", [])
                  if s.get("instrumental")]
    prov, n = [], 0
    for bid, mood, rel in items:
        url = f"{RAW}/{rel}"
        raw = os.path.join(tmp, os.path.basename(rel))
        try:
            with open(raw, "wb") as fh:
                fh.write(get(url, timeout=180))
        except Exception as e:  # noqa: BLE001
            print(f"  {bid}: download failed: {str(e)[:70]}", file=sys.stderr)
            continue
        dest = os.path.join(args.out_dir, f"{mood}-{bid}.mp3")
        if to_bed(raw, dest, args.seconds):
            prov.append({"file": os.path.basename(dest), "id": bid, "mood": mood,
                         "license": cat.get("license"),
                         "credit": cat.get("credit"), "source": url})
            n += 1
            print(f"  {bid:16} mood={mood:8} -> {os.path.basename(dest)}")
        os.remove(raw)

    with open(os.path.join(args.out_dir, "provenance.json"), "w", encoding="utf-8") as fh:
        json.dump({"pack": cat.get("pack"), "license": cat.get("license"),
                   "credit": cat.get("credit"), "beds": prov}, fh,
                  ensure_ascii=False, indent=2)
    print(f"total beds: {n} -> {args.out_dir}")
    return 0 if n else 1


if __name__ == "__main__":
    sys.exit(main())
