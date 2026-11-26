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

# K (2026-11-23): "ทำไมคุณภาพคลิปไม่ใช่ 4k" -- the long-form master is 4K, and the
# gate is told so, so a 720p or 1080p build fails instead of shipping quietly.
MIN_OUT_H = 2160
import kill_switch  # noqa: E402
import standard_clip as sc  # noqa: E402  (gen_scenes, narrate, music, mix, finish, ff, duration)

FADE = 1.0


def picture_graph(scene_paths, shot: float, dframes: int, title: str, subtitle: str):
    """One filter graph: every still -> Ken Burns shot -> crossfades -> titles.

    Measured 2026-11-26: three 4K encodes per clip (one per shot, one for the
    crossfade, one for the title) did not fit the runner -- two builds were
    killed at 150 min with the picture unfinished. Rendering the same frames in
    one pass costs a third of the time.
    """
    inputs = []
    for p in scene_paths:
        inputs += ["-loop", "1", "-t", f"{shot}", "-r", str(sc.FPS), "-i", p]
    fc = []
    for i in range(len(scene_paths)):
        fc.append(
            f"[{i}:v]scale=3840:3840:force_original_aspect_ratio=increase,"
            "crop=3840:2160,"
            f"zoompan=z='min(1+0.00030*on,1.15)':x='iw/2-(iw/zoom/2)':"
            f"y='ih/2-(ih/zoom/2)':d={dframes}:s={sc.W}x{sc.H}:fps={sc.FPS},"
            "eq=contrast=1.05:saturation=1.08:brightness=0.01,"
            f"unsharp=5:5:0.5:5:5:0.0,setpts=PTS-STARTPTS[v{i}]")
    prev = "v0"
    for i in range(1, len(scene_paths)):
        off = i * (shot - FADE)
        fc.append(f"[{prev}][v{i}]xfade=transition=fade:duration={FADE}:"
                  f"offset={off:.3f}[x{i}]")
        prev = f"x{i}"
    font = os.path.join(ROOT, "assets", "fonts", "Kanit-SemiBold.ttf")
    k = sc.H / 720
    fc.append(
        f"[{prev}]drawtext=fontfile={font}:text='{sc._esc(title)}':fontcolor=white@0.94:"
        f"fontsize={round(68 * k)}:x=(w-text_w)/2:y=h-{round(200 * k)}:"
        "alpha='if(lt(t,0.8),0,min(1,(t-0.8)/1.2))',"
        f"drawtext=fontfile={font}:text='{sc._esc(subtitle)}':fontcolor=white@0.80:"
        f"fontsize={round(40 * k)}:x=(w-text_w)/2:y=h-{round(112 * k)}:"
        "alpha='if(lt(t,1.8),0,min(1,(t-1.8)/1.2))',"
        "setparams=range=tv,format=yuv420p[vout]")
    return inputs, ";".join(fc)


def build(scene_paths, narr, music_wav, title, subtitle, out, tmp):
    total = sc.duration(narr)
    n = len(scene_paths)
    shot = (total + (n - 1) * FADE) / n
    df = int(shot * sc.FPS)
    inputs, graph = picture_graph(scene_paths, shot, df, title, subtitle)
    pic = os.path.join(tmp, "picture.mp4")
    sc.ff(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *inputs,
           "-filter_complex", graph, "-map", "[vout]",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "17", "-profile:v", "high",
           "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
           "-color_range", "tv", "-pix_fmt", "yuv420p", "-t", f"{total}", pic])
    mfull = os.path.join(tmp, "music_full.wav")
    sc.ff(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-stream_loop", "-1",
           "-i", music_wav, "-t", f"{total}", "-ar", "48000", "-ac", "2",
           "-c:a", "pcm_f32le", mfull])
    norm = sc.mix(narr, mfull, total, tmp)
    sc.ff(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", pic, "-i", norm,
           "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
           "-ar", "48000", "-shortest", "-movflags", "+faststart", out])


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

    rc = subprocess.run([sys.executable, os.path.join(HERE, "clip_standard.py"), a.out,
                         "--min-height", str(MIN_OUT_H)],
                        stdin=subprocess.DEVNULL).returncode
    print("clip_standard:", "PASS" if rc == 0 else "FAIL", flush=True)
    return rc


if __name__ == "__main__":
    sys.exit(main())
