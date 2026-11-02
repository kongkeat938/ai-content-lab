"""Synthesise a free ambient sleep bed — no download, no licence, no network.

A long sleep compilation needs a continuous low bed under the narration, and
every free music source is either rate-limited (Openverse 20/min) or blocked by
the sandbox proxy. ffmpeg can only make a *fast* tremolo (its `f` parameter
floors at 0.1 Hz), which pulses instead of drifting. So the bed is generated
here from first principles: a soft minor chord whose partials each breathe at
their own slow rate.

The loop is seamless by construction. Every LFO frequency is an integer number
of cycles across the clip (k / seconds), so sample 0 and sample N meet exactly
and `aloop` can repeat it for hours without a click.

Usage:
    python make_bed.py --out bed.wav [--seconds 120] [--root 110] [--level -20]
"""
import argparse
import math
import os
import struct
import wave

import numpy as np

SR = 48000

# A minor add9 — calm, unresolved, no leading tone pulling anywhere.
# (ratio to root, relative amplitude, LFO cycles across the clip, stereo phase)
PARTIALS = [
    (1.0, 0.50, 1, 0.0),      # root
    (1.5, 0.30, 2, 0.25),     # fifth
    (2.0, 0.22, 3, 0.5),      # octave
    (2.378, 0.16, 4, 0.75),   # minor third, up an octave (C)
    (3.0, 0.10, 5, 0.1),      # fifth, two octaves up
    (4.756, 0.05, 7, 0.6),    # ninth (B), a whisper of shimmer
]


def build(seconds: float, root: float, level_db: float) -> np.ndarray:
    n = int(round(seconds * SR))
    t = np.arange(n) / SR
    left = np.zeros(n)
    right = np.zeros(n)
    for ratio, amp, cycles, phase in PARTIALS:
        f = root * ratio
        # Integer cycles across the clip -> the loop is click-free.
        lfo = 0.5 + 0.5 * np.sin(2 * np.pi * cycles * t / seconds + phase * 2 * np.pi)
        # A second, slower layer keeps the two channels from breathing in lockstep.
        lfo2 = 0.5 + 0.5 * np.sin(2 * np.pi * (cycles + 1) * t / seconds + phase * np.pi)
        tone = amp * lfo * np.sin(2 * np.pi * f * t)
        left += tone
        right += amp * lfo2 * np.sin(2 * np.pi * f * t + 0.35 * phase)

    # A breath of filtered noise, so the pad is not a pure synthesiser stack.
    rng = np.random.default_rng(7)
    noise = rng.standard_normal(n)
    k = 400  # ~120 Hz corner at 48 kHz — dull, room-like
    noise = np.convolve(noise, np.ones(k) / k, mode="same")
    breath = 0.06 * (0.5 + 0.5 * np.sin(2 * np.pi * 2 * t / seconds))
    left += noise * breath
    right += np.roll(noise, 97) * breath  # tiny inter-channel decorrelation

    stereo = np.stack([left, right], axis=1)
    peak = np.max(np.abs(stereo)) or 1.0
    stereo *= (10 ** (level_db / 20)) / peak
    return stereo


def write_wav(path: str, data: np.ndarray) -> None:
    pcm = np.clip(data, -1.0, 1.0)
    pcm = (pcm * 32767.0).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--seconds", type=float, default=120.0,
                    help="clip length; kept whole-cycle so it loops seamlessly")
    ap.add_argument("--root", type=float, default=110.0, help="root frequency (Hz)")
    ap.add_argument("--level", type=float, default=-20.0,
                    help="peak level in dBFS; the mixer sets the final balance")
    a = ap.parse_args()
    if os.path.exists(a.out):
        print(f"{a.out} exists; leaving it")
        return
    data = build(a.seconds, a.root, a.level)
    write_wav(a.out, data)
    rms = float(np.sqrt(np.mean(data ** 2)))
    print(f"wrote {a.out}: {a.seconds:.0f}s stereo, "
          f"peak {20 * math.log10(np.max(np.abs(data))):.1f} dBFS, "
          f"rms {20 * math.log10(rms):.1f} dBFS")


if __name__ == "__main__":
    main()
