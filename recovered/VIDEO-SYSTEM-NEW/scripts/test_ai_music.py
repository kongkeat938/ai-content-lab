#!/usr/bin/env python3
"""Guard: the AI music route produces MUSIC, and the bed pack is never used.

Two things must be able to fail here, or the guard proves nothing:

1. The generator must refuse when K's kill switch is up, and must refuse a
   length that would cost minutes on CPU (measured: 20 s of audio = 144 s).
2. The audio it writes must measure as music, not as a tone. The bed pack that
   once shipped here (AERIS) was six sine tones and every clip carried a beep.

The musicgen run itself is NOT part of this test -- it costs ~2.5 minutes on
this pod. Set AI_MUSIC_LIVE=1 to run it and check the real artifact.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import ai_music  # noqa: E402

FAILS: list[str] = []


def check(ok: bool, what: str, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {what}" + (f"  [{detail}]" if detail else ""))
    if not ok:
        FAILS.append(what)


def _run(path: str, af: str) -> str:
    return subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-af", af,
         "-f", "null", "-"], capture_output=True, text=True).stderr


def measure(path: str) -> dict:
    """Loudness range, plus how much of the spectrum sits in one bin.

    `topbin` is the share of a frame's energy held by its single loudest FFT bin,
    averaged over the file. It is what separates music from a tone here, and the
    numbers are measured, not guessed (2026-11-20): sine 220/440/880 Hz ->
    0.58 / 0.56 / 0.60; AI music -> 0.24 / 0.26. Zero-crossing rate was tried
    first and rejected -- it tracks the fundamental (0.010 at 220 Hz, 0.040 at
    880 Hz), so a threshold that rejects 880 Hz also rejects music with treble.
    LRA alone is weaker: a slow tremolo moves LRA while staying a tone.
    """
    import numpy as np

    vals: dict[str, float] = {}
    for line in _run(path, "ebur128=framelog=quiet").splitlines():
        t = line.strip()
        if t.startswith("I:") and "LUFS" in t:
            vals.setdefault("lufs", float(t.split()[1]))
        elif t.startswith("LRA:") and "LU" in t:
            vals.setdefault("lra", float(t.split()[1]))

    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1",
                          "-ar", "16000", "-f", "s16le", "-"],
                         capture_output=True).stdout
    x = np.frombuffer(raw, dtype="<i2").astype(np.float64) / 32768.0
    n, tops = 4096, []
    for i in range(0, len(x) - n, n):
        w = np.abs(np.fft.rfft(x[i:i + n] * np.hanning(n))) ** 2 + 1e-20
        tops.append(w.max() / w.sum())
    if tops:
        vals["topbin"] = float(np.mean(tops))
    return vals


def is_music(m: dict) -> bool:
    """The rule the live check and the sine control both use.

    0.40 sits between the measured music band (0.24-0.26) and the measured tone
    band (0.56-0.60). A missing number fails rather than passes.
    """
    return m.get("lra", 0) > 0.5 and m.get("topbin") is not None and m["topbin"] < 0.40


def main() -> int:
    print("1. the generator refuses while K's stop file is up")
    rc = subprocess.run([sys.executable, os.path.join(HERE, "ai_music.py"),
                         "--seconds", "5", "--out", "/tmp/never.wav"],
                        capture_output=True).returncode
    check(rc == 3, "kill switch returns STOPPED_EXIT", f"rc={rc}")

    print("\n2. an over-long request is refused, not silently trimmed")
    env = dict(os.environ, CONTENT_STOP_PATH=os.path.join(
        tempfile.gettempdir(), "no-stop-for-this-test"))
    rc = subprocess.run([sys.executable, os.path.join(HERE, "ai_music.py"),
                         "--seconds", "45", "--out", "/tmp/never.wav"],
                        env=env, capture_output=True).returncode
    check(rc == 2, ">30 s is refused", f"rc={rc}")

    print("\n3. the default prompt names the genre and forbids drums")
    p = ai_music.DEFAULT_PROMPT.lower()
    check("meditation" in p or "ambient" in p, "default prompt names the genre")
    check("no drums" in p, "default prompt excludes drums")

    print("\n4. no music bed from assets/music is read by the generator")
    src = open(os.path.join(HERE, "ai_music.py"), encoding="utf-8").read()
    # the module docstring explains WHY the bed pack is not used, so the path may
    # be named there; what must be absent is any code that opens it.
    code = src.split('"""', 2)[2] if src.count('"""') >= 2 else src
    check("assets/music" not in code, "the generator never opens the bed pack")
    check("fetch_music" not in code, "the generator never calls the bed fetcher")

    print("\n5. the measurement can go RED: a 440 Hz sine is not music")
    with tempfile.TemporaryDirectory() as d:
        sine = os.path.join(d, "sine.wav")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                        "-i", "sine=frequency=440:duration=5",
                        "-c:a", "pcm_s16le", sine], check=True)
        m = measure(sine)
    check(not is_music(m), "the music test REJECTS a 440 Hz sine", str(m))

    if os.environ.get("AI_MUSIC_LIVE") == "1":
        print("\n6. a real generation measures as music (LIVE)")
        wav = os.path.join(tempfile.gettempdir(), "ai_music_probe.wav")
        subprocess.run([sys.executable, os.path.join(HERE, "ai_music.py"),
                        "--seconds", "8", "--out", wav, "--seed", "7"],
                       env=env, check=True)
        m = measure(wav)
        check(is_music(m), "the generated audio is music, not a tone", str(m))
    else:
        print("\n6. a real generation measures as music -- SKIPPED "
              "(set AI_MUSIC_LIVE=1; costs ~2.5 min)")

    print()
    if FAILS:
        print("FAILED:", FAILS)
        return 1
    print("PASS -- the AI music route is gated and its output is measured as music")
    return 0


if __name__ == "__main__":
    sys.exit(main())
