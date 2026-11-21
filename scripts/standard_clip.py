#!/usr/bin/env python3
"""One approved-standard clip from a spec (content/standard/<channel>_NN.json).

The exact recipe K approved (2026-11-20), now a repeatable rail:
  5 SD-Turbo scenes -> RealESRGAN x4 (2560) -> 720p Ken-Burns shots (4.6 s,
  1.0 s crossfades) -> Thai narration (edge-tts) + MusicGen music -> two-pass
  -14 LUFS master -> clip_standard gate. Any missing piece fails loudly.

    CONTENT_STOP_PATH=/tmp/nostop python3 scripts/standard_clip.py \
        --spec content/standard/dharma_01.json --out /tmp/out/dharma_01.mp4
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import clip_standard  # the gate
import kill_switch
import make_short  # Thai voice (edge-tts)

W, H, FPS = 1280, 720, 25
SHOT, FADE = 4.6, 1.0
WEIGHTS = "/tmp/RealESRGAN_x4plus.pth"
WEIGHTS_URL = ("https://github.com/xinntao/Real-ESRGAN/releases/download/"
               "v0.1.0/RealESRGAN_x4plus.pth")


def ff(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, stdin=subprocess.DEVNULL)


def duration(path: str) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", path],
        capture_output=True, text=True, stdin=subprocess.DEVNULL).stdout.strip()
    return float(out)


def gen_scenes(prompts: list[str], outdir: str) -> list[str]:
    import numpy as np
    import torch
    from diffusers import AutoPipelineForText2Image
    from PIL import Image
    from spandrel import ModelLoader

    torch.set_num_threads(4)
    if not os.path.exists(WEIGHTS):
        import urllib.request
        urllib.request.urlretrieve(WEIGHTS_URL, WEIGHTS)
    pipe = AutoPipelineForText2Image.from_pretrained(
        "stabilityai/sd-turbo", torch_dtype=torch.float32, safety_checker=None)
    pipe.set_progress_bar_config(disable=True)
    up = ModelLoader().load_from_file(WEIGHTS).model.eval()
    paths = []
    for i, prompt in enumerate(prompts):
        img = pipe(prompt=prompt, num_inference_steps=4, guidance_scale=0.0,
                   width=640, height=640).images[0]
        x = torch.from_numpy(
            np.asarray(img.convert("RGB")).astype("float32") / 255.0
        ).permute(2, 0, 1)[None]
        with torch.no_grad():
            y = up(x)
        arr = (y[0].clamp(0, 1).permute(1, 2, 0).numpy() * 255.0).round().astype("uint8")
        pth = os.path.join(outdir, f"s{i:02d}.png")
        Image.fromarray(arr).save(pth)
        paths.append(pth)
        print(f"scene {i + 1}/{len(prompts)} -> {pth}", flush=True)
    return paths


def narrate(lines: list[str], out: str) -> None:
    asyncio.run(make_short.speak("\n".join(lines).strip(), out))


def music(out: str, seconds: float) -> None:
    import torch
    import scipy.io.wavfile as wavfile
    from transformers import AutoProcessor, MusicgenForConditionalGeneration

    torch.set_num_threads(4)
    proc = AutoProcessor.from_pretrained("facebook/musicgen-small")
    model = MusicgenForConditionalGeneration.from_pretrained("facebook/musicgen-small")
    inputs = proc(text=["calm ambient meditation, soft warm pads, no drums, slow, peaceful"],
                  return_tensors="pt", padding=True)
    with torch.no_grad():
        audio = model.generate(**inputs, max_new_tokens=int(seconds * 50),
                               do_sample=True, guidance_scale=3.0)
    rate = model.config.audio_encoder.sampling_rate
    wavfile.write(out, rate, audio[0, 0].numpy())


def shots(paths: list[str], tmp: str) -> list[str]:
    dframes = int(SHOT * FPS)
    outs = []
    for i, p in enumerate(paths):
        sp = os.path.join(tmp, f"shot{i}.mp4")
        vf = ("scale=3840:3840:force_original_aspect_ratio=increase,crop=3840:2160,"
              f"zoompan=z='min(1+0.00040*on,1.18)':x='iw/2-(iw/zoom/2)':"
              f"y='ih/2-(ih/zoom/2)':d={dframes}:s={W}x{H}:fps={FPS},"
              "eq=contrast=1.05:saturation=1.08:brightness=0.01,"
              "unsharp=5:5:0.5:5:5:0.0,setparams=range=tv,format=yuv420p")
        ff(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-loop", "1",
            "-i", p, "-t", str(SHOT), "-r", str(FPS), "-vf", vf,
            "-c:v", "libx264", "-preset", "medium", "-crf", "16", "-profile:v", "high",
            "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
            "-color_range", "tv", sp])
        outs.append(sp)
    return outs


def xfade(shots_list: list[str], out: str) -> None:
    inputs = []
    for s in shots_list:
        inputs += ["-i", s]
    fc, prev = [], "0:v"
    for i in range(1, len(shots_list)):
        lab = f"x{i}"
        off = i * (SHOT - FADE)
        fc.append(f"[{prev}][{i}:v]xfade=transition=fade:duration={FADE}:offset={off:.3f}[{lab}]")
        prev = lab
    ff(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *inputs,
        "-filter_complex", ";".join(fc), "-map", f"[{prev}]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-profile:v", "high",
        "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
        "-color_range", "tv", "-pix_fmt", "yuv420p", out])


def mix(narr: str, music_wav: str, total: float, tmp: str) -> str:
    mixwav = os.path.join(tmp, "mix.wav")
    fade_out = max(total - 2.5, 0)
    fc = (f"[0:a]adelay=900|900,apad,volume=1.0[voice];"
          f"[1:a]volume=0.34,atrim=0:{total},asetpts=N/SR/TB,"
          f"afade=t=in:st=0:d=2,afade=t=out:st={fade_out}:d=2.5[music];"
          "[voice][music]amix=inputs=2:duration=longest:dropout_transition=0[mix]")
    ff(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", narr, "-i", music_wav,
        "-filter_complex", fc, "-map", "[mix]", "-t", str(total), "-ar", "48000",
        "-ac", "2", "-c:a", "pcm_f32le", mixwav])
    probe = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", mixwav, "-af",
         "loudnorm=I=-14:TP=-2.0:LRA=11:print_format=json", "-f", "null", "-"],
        capture_output=True, text=True, stdin=subprocess.DEVNULL)
    d = json.loads(re.search(r'\{[^{}]*"input_i"[^{}]*\}', probe.stderr, re.S).group(0))
    ln = (f"loudnorm=I=-14:TP=-2.0:LRA=11:measured_I={d['input_i']}"
          f":measured_TP={d['input_tp']}:measured_LRA={d['input_lra']}"
          f":measured_thresh={d['input_thresh']}:offset={d['target_offset']}:linear=true")
    norm = os.path.join(tmp, "mix_norm.wav")
    ff(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", mixwav, "-af", ln,
        "-ar", "48000", "-ac", "2", "-c:a", "pcm_f32le", norm])
    return norm


def _esc(t: str) -> str:
    return t.replace("\\", "\\\\").replace("'", "\\'").replace(":", "\\:")


def finish(picture: str, norm: str, title: str, subtitle: str, out: str, tmp: str) -> None:
    font = os.path.join(ROOT, "assets", "fonts", "Kanit-SemiBold.ttf")
    vf = (f"drawtext=fontfile={font}:text='{_esc(title)}':fontcolor=white@0.94:"
          "fontsize=68:x=(w-text_w)/2:y=h-200:"
          "alpha='if(lt(t,0.8),0,min(1,(t-0.8)/1.2))',"
          f"drawtext=fontfile={font}:text='{_esc(subtitle)}':fontcolor=white@0.80:"
          "fontsize=40:x=(w-text_w)/2:y=h-112:"
          "alpha='if(lt(t,1.8),0,min(1,(t-1.8)/1.2))',"
          "setparams=range=tv,format=yuv420p")
    pt = os.path.join(tmp, "picture_text.mp4")
    ff(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", picture, "-vf", vf,
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-profile:v", "high",
        "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
        "-color_range", "tv", pt])
    ff(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", pt, "-i", norm,
        "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-ar", "48000", "-shortest", "-movflags", "+faststart", out])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    kill_switch.require_running("standard_clip")

    spec = json.load(open(a.spec, encoding="utf-8"))
    prompts = spec["prompts"]
    lines = spec["narration"]
    if len(prompts) < 3:
        sys.exit("spec needs at least 3 scene prompts")
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        paths = gen_scenes(prompts, tmp)
        narr = os.path.join(tmp, "narr.mp3")
        narrate(lines, narr)
        mus = os.path.join(tmp, "music.wav")
        music(mus, 20)
        pic = os.path.join(tmp, "picture.mp4")
        xfade(shots(paths, tmp), pic)
        total = duration(pic)
        print(f"picture {total:.3f}s", flush=True)
        norm = mix(narr, mus, total, tmp)
        finish(pic, norm, spec.get("title", ""), spec.get("subtitle", ""), a.out, tmp)

    rc = subprocess.run([sys.executable, os.path.join(HERE, "clip_standard.py"), a.out],
                        stdin=subprocess.DEVNULL).returncode
    print("clip_standard:", "PASS" if rc == 0 else "FAIL", flush=True)
    return rc


if __name__ == "__main__":
    sys.exit(main())
