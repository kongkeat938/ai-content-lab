#!/usr/bin/env python3
"""The sample gate must be able to fail.

A 720x1280 silent clip is fed to verify(): if that passes, the gate is decoration
and the three published samples prove nothing.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import make_samples as ms  # noqa: E402

FAILED = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if cond else 'FAIL'} {name}" + (f" ({detail})" if detail else ""))
    if not cond:
        FAILED.append(name)


def main() -> int:
    try:
        ms.ffmpeg()
    except SystemExit:
        print("SKIP test_make_samples_gate (no ffmpeg)")
        return 0

    tmp = tempfile.mkdtemp()
    bad = os.path.join(tmp, "bad.mp4")
    subprocess.run([ms.ffmpeg(), "-y", "-v", "error", "-f", "lavfi", "-i",
                    "color=c=black:s=720x1280:d=5", "-c:v", "libx264", "-pix_fmt", "yuv420p", bad],
                   check=True, stdin=subprocess.DEVNULL)
    print("a bad file")
    check("720x1280 and silent is refused", ms.verify([bad]) == 1)
    m = ms.measure(bad)
    check("the measurement says why", (m["width"], m["height"]) == (720, 1280) and not m["has_audio"],
          f"{m['width']}x{m['height']} audio={m['has_audio']}")

    print("the published samples")
    media = os.path.join(ROOT, "docs", "portfolio", "media")
    names = ["sample_product_45s.mp4", "sample_promo_20s.mp4", "sample_still_30s.mp4"]
    present = [n for n in names if os.path.exists(os.path.join(media, n))]
    if len(present) == len(names):
        check("all three pass the gate", ms.verify([os.path.join(media, n) for n in names]) == 0)
    else:
        print(f"  note: {len(present)}/3 samples on disk; render with scripts/make_samples.py")

    shutil.rmtree(tmp, ignore_errors=True)
    print("\nPASS test_make_samples_gate" if not FAILED else f"\nFAIL test_make_samples_gate: {FAILED}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
