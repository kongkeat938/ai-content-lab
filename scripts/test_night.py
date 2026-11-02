"""Guard the long-form rail: the gates must reject, not just accept.

Each case builds a tiny (a few seconds) artifact with ffmpeg and asserts the
*intended* gate fires. A test that only checks the happy path proves nothing --
the duration bug this rail shipped with (a `-stream_loop` video running past a
`-shortest` audio) passed every check until one measured the streams.

    python3 scripts/test_night.py
"""
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from contextlib import redirect_stdout

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import make_audio  # noqa: E402
import make_bed  # noqa: E402
import make_compilation  # noqa: E402
import make_night_video  # noqa: E402
import verify_night  # noqa: E402

FAILS = []


def check(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'} {name}{(' -- ' + detail) if detail else ''}")
    if not cond:
        FAILS.append(name)


def make_voice(path: str) -> None:
    """A narration-shaped signal: speech bursts separated by real silence.

    A continuous tone would make the bed-headroom gate meaningless (no quiet
    window to measure the bed in) and would not master to target, so the fixture
    has to look like the thing the rail actually produces.
    """
    burst = "sine=frequency=200:duration=1.5,volume=0.25"
    quiet = "anullsrc=r=48000:cl=stereo:d=1.0"
    args = []
    for f in (burst, quiet, burst, quiet, burst):
        args += ["-f", "lavfi", "-i", f]
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", *args,
         "-filter_complex", "[0:a][1:a][2:a][3:a][4:a]concat=n=5:v=0:a=1[o]",
         "-map", "[o]", "-ar", "48000", "-ac", "2", path], check=True)
    # Master to the YouTube target, exactly as the rail does.
    raw = path + ".raw.wav"
    os.rename(path, raw)
    make_audio.loudnorm2(raw, path)
    os.remove(raw)


def make_card(path: str) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
         "-i", "color=c=navy:s=320x180:d=1", "-frames:v", "1", path], check=True)


def run_verify(path: str) -> tuple:
    argv = sys.argv
    buf = io.StringIO()
    try:
        sys.argv = ["verify_night.py", path]
        with redirect_stdout(buf):
            rc = verify_night.main()
    finally:
        sys.argv = argv
    return rc, buf.getvalue()


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="test_night_")
    try:
        print("bed loop is seamless")
        d = make_bed.build(30.0, 110.0, -20.0)
        step = float(np.abs(np.diff(d[:, 0])).max())
        seam = float(abs(d[0, 0] - d[-1, 0]))
        check("seam within a normal step", seam <= step * 1.5,
              f"seam={seam:.5f} step={step:.5f}")

        print("sequence_to_length reaches the target")
        tone = os.path.join(tmp, "t.mp3")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                        "-i", "sine=frequency=220:duration=6", tone], check=True)
        seq, cycles = make_compilation.sequence_to_length([tone] * 3, 45.0)
        check("cycles chosen to reach 45s", cycles == 3, f"cycles={cycles}")
        check("list long enough", len(seq) == cycles * 3)

        print("a correctly mastered build passes the verifier")
        voice = os.path.join(tmp, "voice.wav")
        make_voice(voice)
        seed = os.path.join(tmp, "bed_seed.wav")
        make_bed.write_wav(seed, make_bed.build(12.0, 110.0, -20.0))
        bed = os.path.join(tmp, "bed.wav")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-stream_loop", "-1",
                        "-i", seed, "-t", f"{make_audio.duration(voice):.3f}",
                        "-ar", "48000", "-ac", "2", bed], check=True)
        mixed = os.path.join(tmp, "mixed.wav")
        make_compilation.mix(voice, bed, mixed)
        mastered = os.path.join(tmp, "mastered.mp3")
        make_audio.loudnorm2(mixed, mastered)

        card = os.path.join(tmp, "card.jpg")
        make_card(card)
        good = os.path.join(tmp, "good.mp4")
        make_night_video.build(mastered, card, good, "", 3.0, cover=card)
        rc, out = run_verify(good)
        check("verifier accepts a good file", rc == 0, f"exit={rc}\n{out}")

        print("a video longer than its audio is rejected for that reason")
        bad = os.path.join(tmp, "bad.mp4")
        # Reproduce the original defect: endless video, no explicit -t.
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-stream_loop", "-1",
             "-i", good, "-i", mastered, "-map", "0:v", "-map", "1:a", "-shortest",
             "-c:v", "copy", "-c:a", "aac", bad], check=True)
        rc, out = run_verify(bad)
        check("verifier rejects the length mismatch",
              rc == 1 and "length differ" in out, f"exit={rc}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print(json.dumps({"verdict": "pass" if not FAILS else "fail",
                      "failures": FAILS}))
    return 0 if not FAILS else 1


if __name__ == "__main__":
    sys.exit(main())
