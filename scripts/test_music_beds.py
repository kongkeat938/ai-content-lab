#!/usr/bin/env python3
"""Prove every music bed in assets/music/ is music, not a test tone.

The owner's rule is "test the audio before using it" (2026-11-07). That rule
exists because the AERIS pack that was used first turned out to be six single
sine tones -- one partial each, no melody -- and every Short carried one. A
listener hears that immediately; a filename and a licence note do not reveal it.

The check is measured on the samples, not on metadata:

* tone_share -- the share of band energy in the single loudest frequency bin.
  A test tone piles a third of its energy into one bin; real music spreads it.
* partials -- the number of significant spectral peaks. A sine has one; an
  instrument or an ensemble has many.
* env_range -- how much the level moves over time. A held tone barely moves.

A bed passes when tone_share < 0.15, partials >= 5 and env_range > 0.6.
Measured 2026-11-07: all six AERIS beds fail (share 0.155-0.204, partials 3-4),
all six replacements pass (share 0.012-0.106, partials 6-101).

    python3 scripts/test_music_beds.py
"""
from __future__ import annotations

import glob
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MUSIC = os.path.join(ROOT, "assets", "music")


def load(path: str, secs: int = 8, sr: int = 8000) -> np.ndarray:
    raw = "/tmp/_bedcheck.raw"
    subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-t", str(secs),
                    "-ac", "1", "-ar", str(sr), "-f", "s16le", raw, "-y"], check=True)
    return np.frombuffer(open(raw, "rb").read(), dtype=np.int16).astype(np.float32)


def measure(path: str) -> dict:
    sr, n = 8000, 8192
    a = load(path)
    if len(a) < sr:
        raise ValueError(f"{path}: too short to measure")
    shares, parts, cents = [], [], []
    for i in range(0, len(a) - n, n):
        sp = np.abs(np.fft.rfft(a[i:i + n] * np.hanning(n))) + 1e-6
        fr = np.fft.rfftfreq(n, 1 / sr)
        band = (fr > 60) & (fr < 3500)
        sp2 = sp[band]
        shares.append(float(sp2.max() / sp2.sum()))
        pk = sp2[1:-1]
        loc = (pk[1:-1] > pk[:-2]) & (pk[1:-1] > pk[2:])
        parts.append(int((pk[1:-1][loc] > 0.08 * sp2.max()).sum()))
        cents.append(float((fr[band] * sp2).sum() / sp2.sum()))
    env = [float(np.abs(a[i:i + 400]).mean()) for i in range(0, len(a) - 400, 400)]
    m = {
        "tone_share": round(float(np.mean(shares)), 3),
        "partials": round(float(np.mean(parts)), 1),
        "env_range": round(float((max(env) - min(env)) / (np.mean(env) + 1e-9)), 2),
        "centroid": int(np.mean(cents)),
    }
    m["is_music"] = bool(m["tone_share"] < 0.15 and m["partials"] >= 5
                         and m["env_range"] > 0.6)
    return m


def main() -> int:
    beds = sorted(glob.glob(os.path.join(MUSIC, "bed-*.mp3")))
    if not beds:
        sys.exit("no beds in assets/music/")
    bad = 0
    for p in beds:
        m = measure(p)
        tag = "MUSIC" if m["is_music"] else "TONE!"
        print(f"{tag}  {os.path.basename(p):16} share={m['tone_share']:<6} "
              f"parts={m['partials']:<6} env={m['env_range']:<6} centroid={m['centroid']}Hz")
        bad += not m["is_music"]
    if bad:
        sys.exit(f"{bad} bed(s) are not music -- do not publish with them")
    print(f"OK: {len(beds)} beds measured as music, none is a test tone")
    return 0


if __name__ == "__main__":
    sys.exit(main())
