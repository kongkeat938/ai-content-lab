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
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import make_poster  # noqa: E402

W, H = 1920, 1080
FPS = 25


def run(cmd: list) -> None:
    subprocess.run(cmd, check=True, capture_output=True)


def duration(path: str) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", path], capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


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
        run(["ffmpeg", "-y", "-loglevel", "error", "-stream_loop", "-1",
             "-i", loop, "-i", audio,
             "-map", "0:v", "-map", "1:a", "-t", f"{adur:.3f}", "-shortest",
             "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
             "-movflags", "+faststart", out])
        info = {"out": out, "duration_sec": round(duration(out), 2),
                "video": f"{W}x{H}", "fps": FPS,
                "loop_seconds": loop_seconds,
                "audio_duration_sec": round(adur, 2)}
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
