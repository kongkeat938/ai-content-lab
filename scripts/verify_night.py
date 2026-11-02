"""Verify a night compilation against the project's definition of done.

Prints the measured numbers and exits non-zero on a hard failure, so "it is
done" is a measurement rather than an assurance. The checks are the ones the
project already holds itself to: loudness, true peak, picture/audio length
agreement, colour range, and a bed that is present but never fights the voice.

Usage:
    python verify_night.py work/night_full/night.mp4
"""
import json
import os
import subprocess
import sys

import numpy as np

LUFS_MIN, LUFS_MAX = -16.0, -12.0
TP_MAX = -3.0
DUR_TOL = 1.0
BED_MIN_HEADROOM_DB = 6.0   # bed must sit at least this far under the voice
BED_MAX_HEADROOM_DB = 30.0  # ...but not so far it is inaudible


def probe(path: str) -> dict:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration:stream=codec_type,duration,color_range,width,height",
         "-of", "json", path], capture_output=True, text=True, check=True)
    return json.loads(r.stdout)


def measure(path: str) -> tuple:
    out = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", path,
         "-af", "ebur128=peak=true", "-f", "null", "-"],
        capture_output=True, text=True).stderr
    tail = out.split("Summary:")[-1]
    i = None
    p = None
    for line in tail.splitlines():
        if "I:" in line and "LUFS" in line:
            i = line.split("I:")[1].split("LUFS")[0].strip()
        if "Peak:" in line:
            p = line.split("Peak:")[1].split("dBFS")[0].strip()
    return i, p


def pcm(path: str, sr: int = 48000) -> np.ndarray:
    r = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(sr),
         "-f", "s16le", "-"], capture_output=True)
    return np.frombuffer(r.stdout, dtype="<i2").astype(np.float64) / 32768.0


def dbfs(x: np.ndarray) -> float:
    r = float(np.sqrt(np.mean(x ** 2)))
    return 20 * np.log10(r) if r > 0 else -120.0


def bed_headroom(video: str) -> float:
    """How far the bed sits under the voice, measured in the quietest moments.

    The voice-only track is not kept, so the check uses the mixed track: the
    quietest windows are, by construction, where only the bed plays.
    """
    sr = 48000
    x = pcm(video, sr)
    w = int(0.5 * sr)
    levels = [dbfs(x[i:i + w]) for i in range(0, len(x) - w, w)]
    levels = sorted(levels)
    if not levels:
        return float("nan")
    loud = np.percentile(levels, 90)   # the voice
    quiet = np.percentile(levels, 5)   # the bed alone
    return loud - quiet


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else "work/night_full/night.mp4"
    fails = []
    meta = probe(path)
    streams = {s["codec_type"]: s for s in meta["streams"]}
    vdur = float(streams["video"]["duration"])
    adur = float(streams["audio"]["duration"])

    lufs, tp = measure(path)
    print(f"duration      video {vdur:.3f}s  audio {adur:.3f}s")
    print(f"loudness      {lufs} LUFS   true peak {tp} dBFS")
    print(f"picture       {streams['video']['width']}x{streams['video']['height']}"
          f"  color_range={streams['video'].get('color_range')}")

    if abs(vdur - adur) > DUR_TOL:
        fails.append(f"video/audio length differ by {abs(vdur - adur):.2f}s")
    if lufs is None or not (LUFS_MIN <= float(lufs) <= LUFS_MAX):
        fails.append(f"loudness {lufs} outside {LUFS_MIN}..{LUFS_MAX} LUFS")
    if tp is None or float(tp) > TP_MAX:
        fails.append(f"true peak {tp} above {TP_MAX} dBFS")
    if streams["video"].get("color_range") not in ("tv", "limited"):
        fails.append(f"color_range is {streams['video'].get('color_range')}, expected tv")

    head = bed_headroom(path)
    print(f"bed headroom  {head:.1f} dB under the voice")
    if not (BED_MIN_HEADROOM_DB <= head <= BED_MAX_HEADROOM_DB):
        fails.append(f"bed headroom {head:.1f} dB outside "
                     f"{BED_MIN_HEADROOM_DB}..{BED_MAX_HEADROOM_DB}")

    print(json.dumps({"verdict": "pass" if not fails else "fail", "failures": fails}))
    for f in fails:
        print(f"  FAIL: {f}")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
