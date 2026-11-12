"""Turn a long narration track into a calm 1080p video with a looping cover.

A sleep compilation is listened to, not watched, so the picture must be steady
and cheap to encode: one graded cover card with a very slow drift, looped under
the whole track. Rendering a 90-minute zoompan frame by frame would take hours
and gain nothing, so the drift is encoded once as a short loop and repeated with
`-stream_loop`.

Usage:
    python make_night_video.py --audio compilation.mp3 --image cover.jpg \
        --out video.mp4 [--title "..."] [--loop-seconds 60]
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import make_poster  # noqa: E402

W, H = 1920, 1080
FPS = 25
TP_CEILING = -3.0   # the project's true-peak gate (see verify_night)
TP_MARGIN = 0.1     # leave this much room so the next lossy pass cannot cross it
TP_TRIES = 3


def run(cmd: list) -> None:
    subprocess.run(cmd, check=True, capture_output=True)


def duration(path: str) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", path], capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def true_peak(path: str) -> float:
    """Measure the true peak of a file's audio, in dBFS.

    Read from the *finished* file, not the intermediate: AAC overshoots the
    mp3 it was encoded from, so the mp3's own measurement does not describe
    what ships.
    """
    out = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", path,
         "-map", "0:a:0", "-af", "ebur128=peak=true", "-f", "null", "-"],
        capture_output=True, text=True).stderr
    tail = out.split("Summary:")[-1]
    m = re.search(r"Peak:\s*(-?\d+\.\d+)\s*dBFS", tail)
    return float(m.group(1)) if m else float("nan")


def build(audio: str, image: str, out: str, title: str, loop_seconds: float,
          cover: str = None) -> dict:
    tmp = tempfile.mkdtemp(prefix="nightvid_")
    try:
        card = cover or os.path.join(tmp, "cover.jpg")
        if cover is None:
            make_poster.build(image, card, title, "", 6, "", "")
        # A very slow push-in, 1.00 -> 1.035 across the loop. d=1 with an
        # explicit fps filter keeps the clip exactly loop_seconds long; a larger
        # d multiplies frames because the input is -loop 1.
        frames = int(loop_seconds * FPS)
        zoom = (f"scale={int(W * 1.08)}:{int(H * 1.08)},"
                f"zoompan=z='1.0+0.035*on/{frames}':d=1:"
                f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
                f"s={W}x{H}:fps={FPS}")
        loop = os.path.join(tmp, "loop.mp4")
        run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-i", card,
             "-vf", f"fps={FPS},{zoom},format=yuv420p",
             "-t", f"{loop_seconds:.3f}", "-r", str(FPS),
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
             "-color_range", "tv", "-colorspace", "bt709",
             "-color_primaries", "bt709", "-color_trc", "bt709",
             "-pix_fmt", "yuv420p", loop])

        # `-stream_loop -1` makes the video input endless, and `-shortest` only
        # stops on a stream that *ends* -- so the output ran to 322 s against a
        # 257 s track. An explicit -t is what actually bounds it.
        adur = duration(audio)

        def encode(dst: str, gain_db: float = 0.0) -> None:
            # A clean loop is the strongest watch-time lever measured on these
            # channels: the top videos all show averageViewPercentage > 100%.
            # The bed fades in from silence, so fading the tail out to silence
            # makes end->start seamless and a replay continuous, instead of the
            # hard stop that gives a listener a reason to swipe away.
            # The fade-IN is only 1 s: the spoken hook is the panel's #1 retention
            # lever and a 4 s fade buried its first syllables (measured 2026-11-12:
            # 71% leave a 120-min file within 2 min). A 120-min file is rarely
            # replayed, so the loop seam does not need a long fade-in.
            fo = max(0.0, adur - 8.0)
            chain = f"afade=t=in:st=0:d=1,afade=t=out:st={fo:.3f}:d=8"
            af = f"volume={gain_db:.2f}dB,{chain}" if gain_db else chain
            run(["ffmpeg", "-y", "-loglevel", "error", "-stream_loop", "-1",
                 "-i", loop, "-i", audio,
                 "-map", "0:v", "-map", "1:a", "-t", f"{adur:.3f}", "-shortest",
                 "-af", af,
                 "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                 "-movflags", "+faststart", dst])

        # The mp3 was mastered to TP<=-3.0, but the AAC pass that the video
        # needs overshoots it (measured -2.9). Measure the finished file and
        # re-encode lower until the gate holds, rather than trusting the mp3.
        ceiling = TP_CEILING - TP_MARGIN
        gain = 0.0
        for attempt in range(TP_TRIES):
            encode(out, gain)
            peak = true_peak(out)
            if not (peak > ceiling):
                break
            gain += (ceiling - peak)
            print(f"  true peak {peak:.2f} > {ceiling:.2f} dBFS; "
                  f"re-encoding at {gain:+.2f} dB", file=sys.stderr)

        info = {"out": out, "duration_sec": round(duration(out), 2),
                "video": f"{W}x{H}", "fps": FPS,
                "loop_seconds": loop_seconds,
                "audio_duration_sec": round(adur, 2),
                "true_peak_dbfs": peak, "audio_gain_db": round(gain, 2)}
        json.dump(info, open(out + ".info.json", "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
        return info
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--audio", required=True)
    ap.add_argument("--image", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--title", default="")
    ap.add_argument("--cover", default=None, help="pre-built cover jpg (skips poster build)")
    ap.add_argument("--loop-seconds", type=float, default=60.0)
    a = ap.parse_args()
    info = build(a.audio, a.image, a.out, a.title, a.loop_seconds, a.cover)
    print(json.dumps(info, ensure_ascii=False))


if __name__ == "__main__":
    main()
