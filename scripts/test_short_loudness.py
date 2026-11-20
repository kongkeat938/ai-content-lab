#!/usr/bin/env python3
"""Guard the Shorts loudness target on BOTH paths (voice only, and with a bed).

Measured 2026-11-18: a bed-path Short was HELD by the upload gate at -12.3 LUFS
(target -14.0). Root cause: `normalise()` applied a fixed +2 dB after loudnorm
(`BED_GAIN_DB`), added 2026-11-07 when `bed_gain()` was a fixed 0.18 that left
the mix far below target. `bed_gain()` now places the bed ~11 LU under the voice,
so the mix already sits at voice level and the +2 dB double-counted -- the bed
path landed ~-12.8 LUFS while the no-bed path was correct at -14.1.

The fix makes `normalise()` pin the finished file to the target by measurement
(a closed-loop pass), so no fixed guess can drift when the mix changes. This test
builds a REAL mix with ffmpeg (a synthetic voice plus a bed, the same shape
build() produces) and asserts both paths land within the standard's tolerance.

    python3 scripts/test_short_loudness.py    # exit 0 = both paths on target
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import make_short as M  # noqa: E402
import short_standard as std  # noqa: E402

FAILS: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" -- {detail}" if detail and not ok else ""))
    if not ok:
        FAILS.append(name)


def run(cmd: list[str]) -> None:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit("cmd failed: " + " ".join(cmd) + "\n" + r.stderr[-1200:])


def loudness(path: str) -> tuple[float | None, float | None]:
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", path,
                        "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True)
    i = tp = None
    for line in r.stderr.splitlines():
        if "I:" in line and "LUFS" in line:
            i = float(line.split("I:")[1].split("LUFS")[0])
        if "Peak:" in line and "dBFS" in line:
            tp = float(line.split("Peak:")[1].split("dBFS")[0])
    return i, tp


def synth_voice(path: str, volume_db: float, dur: float = 20) -> None:
    run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
         "-f", "lavfi", "-i", f"anoisesrc=d={dur}:c=pink:r=48000",
         "-af", f"acompressor=threshold=-20dB:ratio=3,volume={volume_db}dB",
         "-ar", "48000", path])


def synth_bed(path: str, volume_db: float) -> None:
    run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
         "-f", "lavfi", "-i", f"sine=f=220:d=25:r=48000",
         "-af", f"volume={volume_db}dB", "-ar", "48000", path])


def mix_bed(voice: str, bed: str, out: str) -> None:
    """The exact amix shape build() uses, so the test measures the real path."""
    vol = M.bed_gain(bed, M.measure_audio(voice) or -20.0)
    run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
         "-i", voice, "-stream_loop", "-1", "-i", bed,
         "-filter_complex",
         f"[1:a]volume={vol:.4f}[m];[0:a][m]amix=inputs=2:duration=first:"
         "dropout_transition=0:normalize=0[a]",
         "-map", "[a]", "-ar", "48000", out])


def on_target(path: str) -> tuple[bool, str]:
    i, tp = loudness(path)
    ok_i = i is not None and abs(i - std.LOUD_I) <= std.LOUD_TOL
    ok_tp = tp is not None and abs(tp - std.LOUD_TP) <= std.TP_TOL
    return (ok_i and ok_tp), f"I={i} (want {std.LOUD_I}±{std.LOUD_TOL}), TP={tp} (want {std.LOUD_TP}±{std.TP_TOL})"


def gate_passes(path: str) -> tuple[bool, str]:
    """Run the REAL upload gate, so the fix is judged by the rule that HELD it."""
    from PIL import Image
    thumb = path + ".thumb.jpg"
    Image.new("RGB", (1080, 1920), (30, 40, 80)).save(thumb, quality=90)
    ok, reasons, metrics = std.verify_short(path, thumb)
    os.remove(thumb)
    return ok, f"{reasons} {metrics}"


def mux_short(wav: str, out: str) -> None:
    """Wrap a normalised wav under a real 1080x1920 clip, the shape the gate reads."""
    run(["ffmpeg", "-y", "-loglevel", "error",
         "-f", "lavfi", "-i", "testsrc2=size=1080x1920:rate=30:duration=6",
         "-i", wav, "-map", "0:v", "-map", "1:a", "-c:v", "libx264",
         "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-color_range", "tv",
         "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
         "-c:a", "aac", "-b:a", "192k", "-shortest", out])


def main() -> int:
    with tempfile.TemporaryDirectory() as d:
        voice = os.path.join(d, "voice.wav")
        bed = os.path.join(d, "bed.wav")
        synth_voice(voice, -18)
        synth_bed(bed, -24)

        # Path 1: no bed -- voice only.
        norm_v = os.path.join(d, "norm_voice.wav")
        M.normalise(voice, norm_v)
        ok, why = on_target(norm_v)
        check("no-bed path lands at the target", ok, why)

        # Path 2: with a bed -- the path that produced the held clip.
        mixed = os.path.join(d, "mix.wav")
        mix_bed(voice, bed, mixed)
        norm_m = os.path.join(d, "norm_bed.wav")
        M.normalise(mixed, norm_m)
        ok, why = on_target(norm_m)
        check("bed path lands at the target", ok, why)

        # Path 3: a SHORT clip at the true-peak ceiling. Measured 2026-11-19: a
        # 2.6 s read normalised to -16.1 LUFS with the peak already at -3.0, and a
        # loudnorm-only retry made it WORSE (-17.9) because there was no headroom.
        # The loop must still reach the target by taking the peaks down.
        short_voice = os.path.join(d, "short_voice.wav")
        synth_voice(short_voice, -14, dur=2.6)
        norm_s = os.path.join(d, "norm_short.wav")
        M.normalise(short_voice, norm_s)
        ok, why = on_target(norm_s)
        check("a 2.6 s clip at the peak ceiling still lands at the target", ok, why)

        # The end-to-end check: mux the normalised bed audio into a real Short and
        # run the SAME gate that HELD the -12.3 LUFS clip. It must now pass.
        short = os.path.join(d, "short.mp4")
        mux_short(norm_m, short)
        ok, why = gate_passes(short)
        check("the real upload gate passes the bed-path Short", ok, why)

        # The old defect: a fixed gain cannot pin the target -- it just pushes the
        # mix louder. Normalising the bed mix WITH a +2 dB boost lands ABOVE the
        # corrected result, which is why a fixed guess must not come back.
        old = os.path.join(d, "norm_bed_plus2.wav")
        run(["ffmpeg", "-y", "-i", mixed, "-af",
             f"acompressor=threshold={M.COMP_TH}:ratio={M.COMP_RATIO}:attack=3:release=120,"
             f"loudnorm=I={M.LUFS}:TP={M.TP}:LRA=11,volume=2dB,"
             f"alimiter=limit={M.TP}dB:level=disabled", "-ar", "48000",
             "-c:a", "pcm_s16le", old])
        i_old, _ = loudness(old)
        i_fix, _ = loudness(norm_m)
        check("a fixed +2 dB still pushes the bed mix above the target",
              i_old is not None and i_fix is not None and i_old > i_fix + 0.5,
              f"fixed={i_old} vs corrected={i_fix}")

    # Wiring: build() must not pass a fixed bed gain to normalise().
    src = open(os.path.join(HERE, "make_short.py"), encoding="utf-8").read()
    check("build() calls normalise() with no fixed gain",
          "normalise(mixed, norm)" in src)
    check("no BED_GAIN_DB constant remains", "BED_GAIN_DB" not in src)

    # The WAV ceiling must sit BELOW the upload gate by at least the AAC overshoot.
    # Without this the only guard on the ceiling is the probabilistic end-to-end
    # check above, which failed just 1 run in 10 -- a regression could slip through
    # nine runs out of ten. This check fails on the FIRST run instead.
    check("the WAV ceiling keeps an AAC margin under the upload gate",
          M.TP_WAV <= M.GATE_TP_CEIL - 0.3,
          f"TP_WAV={M.TP_WAV} gate_ceiling={M.GATE_TP_CEIL}")
    check("the WAV ceiling is derived from the gate, not a literal",
          M.GATE_TP_CEIL == std.LOUD_TP + std.TP_TOL,
          f"GATE_TP_CEIL={M.GATE_TP_CEIL} vs {std.LOUD_TP + std.TP_TOL}")
    check("normalise() targets the WAV ceiling", "TP={TP_WAV}" in src)

    print()
    if FAILS:
        print(f"FAILED: {len(FAILS)} check(s): {', '.join(FAILS)}")
        return 1
    print("OK: Shorts audio lands at the loudness target on both paths")
    return 0


if __name__ == "__main__":
    sys.exit(main())
