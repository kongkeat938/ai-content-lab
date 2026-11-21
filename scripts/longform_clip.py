#!/usr/bin/env python3
"""Long-form clip at the approved standard -- the watch-hours lever for YPP.

Same visual/audio standard as the approved demo, but built to run long: N AI
scenes (SD-Turbo -> RealESRGAN) shown as slow Ken-Burns shots with crossfades,
under a long Thai narration + looped MusicGen bed, 720p, two-pass -14 LUFS, and
gated by clip_standard. Shorts exist only to funnel viewers here.

    CONTENT_STOP_PATH=/tmp/nostop python3 scripts/longform_clip.py \
        --spec content/standard/dharma_long_01.json --out /tmp/out/dharma_long_01.mp4
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import clip_standard  # noqa: E402
import kill_switch  # noqa: E402
import standard_clip as sc  # noqa: E402  (gen_scenes, narrate, music, mix, finish, ff, duration)

FADE = 1.0


def build(scene_paths, narr, music_wav, title, subtitle, out, tmp):
    total = sc.duration(narr)
    n = len(scene_paths)
    shot = (total + (n - 1) * FADE) / n
    df = int(shot * sc.FPS)
    shots = []
    for i, p in enumerate(scene_paths):
        sp = os.path.join(tmp, f"shot{i}.mp4")
        vf = ("scale=3840:3840:force_original_aspect_ratio=increase,crop=3840:2160,"
              f"zoompan=z='min(1+0.00030*on,1.15)':x='iw/2-(iw/zoom/2)':"
              f"y='ih/2-(ih/zoom/2)':d={df}:s={sc.W}x{sc.H}:fps={sc.FPS},"
              "eq=contrast=1.05:saturation=1.08:brightness=0.01,"
              "unsharp=5:5:0.5:5:5:0.0,setparams=range=tv,format=yuv420p")
        sc.ff(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-loop", "1",
               "-i", p, "-t", f"{shot}", "-r", str(sc.FPS), "-vf", vf,
               "-c:v", "libx264", "-preset", "medium", "-crf", "16", "-profile:v", "high",
               "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
               "-color_range", "tv", sp])
        shots.append(sp)
    inputs = []
    for s in shots:
        inputs += ["-i", s]
    fc, prev = [], "0:v"
    for i in range(1, n):
        lab = f"x{i}"
        off = i * (shot - FADE)
        fc.append(f"[{prev}][{i}:v]xfade=transition=fade:duration={FADE}:offset={off:.3f}[{lab}]")
        prev = lab
    pic = os.path.join(tmp, "picture.mp4")
    sc.ff(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *inputs,
           "-filter_complex", ";".join(fc), "-map", f"[{prev}]",
           "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-profile:v", "high",
           "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
           "-color_range", "tv", "-pix_fmt", "yuv420p", pic])
    mfull = os.path.join(tmp, "music_full.wav")
    sc.ff(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-stream_loop", "-1",
           "-i", music_wav, "-t", f"{total}", "-ar", "48000", "-ac", "2",
           "-c:a", "pcm_f32le", mfull])
    norm = sc.mix(narr, mfull, total, tmp)
    sc.finish(pic, norm, title, subtitle, out, tmp)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    kill_switch.require_running("longform_clip")

    spec = json.load(open(a.spec, encoding="utf-8"))
    prompts = spec["prompts"]
    lines = spec["narration"]
    if len(prompts) < 2 or not lines:
        sys.exit("spec needs >=2 scene prompts and narration")
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        paths = sc.gen_scenes(prompts, tmp)
        narr = os.path.join(tmp, "narr.mp3")
        sc.narrate(lines, narr)
        print(f"narration {sc.duration(narr):.1f}s", flush=True)
        mus = os.path.join(tmp, "music.wav")
        sc.music(mus, 30)
        build(paths, narr, mus, spec.get("title", ""), spec.get("subtitle", ""), a.out, tmp)

    rc = subprocess.run([sys.executable, os.path.join(HERE, "clip_standard.py"), a.out],
                        stdin=subprocess.DEVNULL).returncode
    print("clip_standard:", "PASS" if rc == 0 else "FAIL", flush=True)
    return rc


if __name__ == "__main__":
    sys.exit(main())
