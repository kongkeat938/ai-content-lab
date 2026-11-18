#!/usr/bin/env python3
"""Stitch real calm b-roll clips into one long ambient video (K, 2026-11-18).

K asked for what a free GUI editor (CapCut/Canva/VN/Resolve) does: "join short
clips and calm atmosphere shots, add a 3-minute music bed". We are headless (no
display), so the same edit is done here with ffmpeg -- the exact operations K
described: place several clips one after another, loop them until the target
length, lay a music bed underneath, export.

The picture source is REAL footage (`fetch_broll.py`, Coverr, keyless, licence
allows commercial use), never an AI face: the panel already ruled (2026-11-17)
that a free model cannot make a believable human and real footage is what
"photoreal" means here.

    python3 scripts/make_ambient_video.py \
        --clips work/broll3/*.mp4 --music assets/music/bed-calm-soft-piano-wav.mp3 \
        --minutes 3 --out work/ambient/dharma_3min.mp4

Every clip is normalised to the SAME frame (1080x1920, 30 fps, yuv420p tv/bt709)
and the bed is pinned to the house loudness (-14 LUFS) by the shared `normalise`,
so the same short/long gates apply. A build with no usable clip FAILS rather than
writing a partial file.
"""
from __future__ import annotations

import argparse
import glob
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import make_short as MS  # noqa: E402  (house loudness: normalise / measure)

W, H, FPS = 1080, 1920, 30
TARGET_LUFS = -14.0


def run(cmd: list, **kw) -> None:
    subprocess.run(cmd, check=True, **kw)


def probe(path: str) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=width,height:format=duration", "-of", "json", path],
        capture_output=True, text=True, check=True).stdout
    import json
    d = json.loads(out)
    st = d["streams"][0]
    return {"w": int(st["width"]), "h": int(st["height"]),
            "dur": float(d["format"]["duration"])}


def is_usable(path: str) -> bool:
    """A clip must decode and carry a video stream of at least ~1 s."""
    try:
        p = probe(path)
    except Exception:
        return False
    return p["w"] > 0 and p["h"] > 0 and p["dur"] >= 1.0


def normalise_clip(src: str, out: str) -> None:
    """Crop-to-fill into 1080x1920, one fps, one colour space -- so any mix of
    source clips cuts together with no jump in size or colour."""
    vf = (f"scale={W}:{H}:force_original_aspect_ratio=increase,"
          f"crop={W}:{H},fps={FPS},format=yuv420p,"
          f"setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709:range=tv")
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-an", "-vf", vf,
         "-c:v", "libx264", "-crf", "18", "-preset", "medium",
         "-color_primaries", "bt709", "-color_trc", "bt709",
         "-colorspace", "bt709", "-pix_fmt", "yuv420p", out])


def loop_to_length(clip: str, seconds: float, out: str) -> None:
    """Loop one normalised clip until it covers `seconds` (K's 'copy/paste to loop')."""
    vf = "setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709:range=tv"
    run(["ffmpeg", "-y", "-loglevel", "error", "-stream_loop", "-1", "-i", clip,
         "-t", f"{seconds:.3f}", "-vf", vf,
         "-c:v", "libx264", "-crf", "18", "-preset", "medium",
         "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
         "-pix_fmt", "yuv420p", out])


def concat(parts: list, out: str) -> None:
    lst = out + ".txt"
    with open(lst, "w", encoding="utf-8") as fh:
        for p in parts:
            fh.write(f"file '{os.path.abspath(p)}'\n")
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
         "-i", lst, "-c", "copy", out])
    os.remove(lst)


def assemble(clips: list, music: str, seconds: float, work: str, out: str) -> None:
    """Cut the clips in rotation, loop them to `seconds`, lay the bed, export."""
    os.makedirs(work, exist_ok=True)
    norm = []
    for i, c in enumerate(clips):
        p = os.path.join(work, f"n{i:02d}.mp4")
        normalise_clip(c, p)
        norm.append(p)
    if not norm:
        raise SystemExit("no usable clip -- refusing to write a partial video")

    # one pass through the clips, then loop that pass until it covers the target
    cycle = os.path.join(work, "cycle.mp4")
    concat(norm, cycle)
    cyc_dur = probe(cycle)["dur"]
    pass_file = os.path.join(work, "pass.mp4")
    loop_to_length(cycle, max(seconds, cyc_dur), pass_file)

    # the music bed, trimmed to the picture, then mastered to the house loudness
    bed = os.path.join(work, "bed.wav")
    run(["ffmpeg", "-y", "-loglevel", "error", "-stream_loop", "-1", "-i", music,
         "-t", f"{seconds:.3f}", "-c:a", "pcm_s16le", bed])
    MS.normalise(bed, out + ".mix.wav")

    run(["ffmpeg", "-y", "-loglevel", "error", "-i", pass_file, "-i", out + ".mix.wav",
         "-t", f"{seconds:.3f}", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
         "-pix_fmt", "yuv420p", "-movflags", "+faststart", out])
    os.remove(out + ".mix.wav")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--clips", nargs="+", required=True)
    ap.add_argument("--music", required=True)
    ap.add_argument("--minutes", type=float, default=3.0)
    ap.add_argument("--out", required=True)
    ap.add_argument("--work", default=None)
    a = ap.parse_args()

    clips = []
    for pat in a.clips:
        clips.extend(sorted(glob.glob(pat)) if any(ch in pat for ch in "*?[") else [pat])
    usable = [c for c in clips if is_usable(c)]
    print(f"clips: {len(clips)} given, {len(usable)} usable")
    if not usable:
        raise SystemExit("no usable clip -- refusing to write a partial video")

    work = a.work or (os.path.splitext(a.out)[0] + "_work")
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    assemble(usable, a.music, a.minutes * 60.0, work, a.out)
    p = probe(a.out)
    print(f"{a.out}: {p['dur']:.1f}s {p['w']}x{p['h']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
