#!/usr/bin/env python3
"""Build a long-form knowledge video in the reference's look -- free tools only.

The owner showed a Google Veo clip (2026-11-17) as the target quality: a realistic
presenter, a big Thai question on the left, a Thai answer caption at the bottom.
Veo itself is not available to this key (404) and every generative-video API that
matches it is paid (Veo 3.1 ~$0.80, Kling ~$0.084/s, Wan ~$0.075/s on Krea). What
IS free and works here is: a photoreal AI still (pollinations, no key), a slow Ken
Burns push, Thai question/answer text, and a Thai voice. That is the reference's
format minus the moving presenter, and it renders on a CPU runner.

So this tool is the standard, built to the reference format. It ships two modes:

  * default  -- each beat is a photoreal still + slow zoom + Q/A text + voice.
  * hero     -- a beat may name a pre-rendered clip (`--hero-dir/NN.mp4`); the clip
                becomes that beat's base instead of the still, so the day a paid
                presenter model is wired in, its output drops straight in and the
                rest of the pipeline is unchanged.

Script JSON:
    {
      "title": "เกร็ดความรู้รอบตัว",
      "beats": [
        {"question": "ทำไมท้องฟ้า ถึงเป็นสีฟ้า?",
         "answer": "เพราะแสงแดดกระเจิงกับอากาศ",
         "image": "photorealistic sunbeams scattering in blue sky, national geographic"}
      ]
    }

    python3 scripts/make_qa_video.py --script s.json --out work/qa/video.mp4
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import subprocess
import sys
import time

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)
FONTS = os.path.join(ROOT, "assets", "fonts")
W, H, FPS = 1280, 720, 30
SR = 48000
VOICE = "th-TH-PremwadeeNeural"     # warm female read; the reference voice is female
VOICE_ALT = "th-TH-NiwatNeural"     # calm male narrator -- the fallback
# Measured 2026-11-17: a Thai question read on PremwadeeNeural intermittently
# answers 'NoAudioReceived' while the same text on NiwatNeural is fine, so the
# build must be able to fall back rather than fail the whole clip.
# Bangkok Thai; the panel's pick (2026-11-16) for a calm explanatory read.
RATE = "-6%"


def sh(cmd: list[str]) -> None:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.stderr.write("command failed: " + " ".join(cmd)[:300] + "\n")
        sys.stderr.write(r.stderr[-2000:] + "\n")
        raise SystemExit(1)


def dur(path: str) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", path], capture_output=True, text=True)
    return float(r.stdout.strip())


def probe(path: str) -> dict:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "stream=codec_type,width,height,color_range",
                        "-of", "json", path], capture_output=True, text=True)
    return json.loads(r.stdout or "{}")


def seed_of(text: str) -> int:
    return int(hashlib.md5(text.encode("utf-8")).hexdigest()[:6], 16)


def still(prompt: str, out: str, style: str, seed: int) -> None:
    """One photoreal still per beat, via the shared free generator (dedupes work)."""
    sh([sys.executable, os.path.join(HERE, "gen_cover_image.py"),
        "--out", out, "--prompt", prompt, "--style", style, "--seed", str(seed),
        "--width", str(W), "--height", str(H)])


def text_card(question: str, answer: str, out: str) -> None:
    """Question top-left, answer caption bottom-centre -- the reference layout.

    PIL draws the Thai text (the repo's Shorts already rely on it); libraqm gives
    correct Thai shaping. A soft dark band keeps the answer legible on any still.
    """
    card = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(card)
    fq = ImageFont.truetype(os.path.join(FONTS, "Kanit-Bold.ttf"), 60)
    fa = ImageFont.truetype(os.path.join(FONTS, "Prompt-SemiBold.ttf"), 40)

    def txt(xy, s, font, anchor):
        x, y = xy
        for dx, dy in ((-3, 0), (3, 0), (0, -3), (0, 3), (2, 2), (-2, -2)):
            d.text((x + dx, y + dy), s, font=font, fill=(0, 0, 0, 210), anchor=anchor)
        d.text((x, y), s, font=font, fill=(255, 255, 255, 255), anchor=anchor)

    if question:
        txt((64, 96), question, fq, "la")
    if answer:
        band = Image.new("RGBA", (W, 100), (0, 0, 0, 120))
        card.alpha_composite(band, (0, H - 156))
        txt((W // 2, H - 106), answer, fa, "ma")
    card.save(out)


async def _synth(text: str, out: str, voice: str, rate: str) -> None:
    import edge_tts
    c = edge_tts.Communicate(text, voice, rate=rate)
    with open(out, "wb") as f:
        async for chunk in c.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])


def voice(text: str, out: str, v: str, rate: str) -> None:
    """Synthesise one line, with a retry then a voice fallback.

    edge-tts drops the stream now and then ('NoAudioReceived'); measured 2026-11-17
    that this can be specific to (voice, text), so try the requested voice a few
    times, then the alternate voice, before giving up on the whole build."""
    for cand in (v, VOICE_ALT):
        for attempt in range(4):
            try:
                asyncio.run(_synth(text, out, cand, rate))
                if os.path.exists(out) and os.path.getsize(out) > 2000:
                    return
            except Exception:  # noqa: BLE001 - retry any transport hiccup
                pass
            time.sleep(2 * (attempt + 1))
    raise SystemExit(f"tts failed on both voices: {text[:40]!r}")


ENC = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
       "-pix_fmt", "yuv420p", "-r", str(FPS),
       "-color_range", "tv", "-colorspace", "bt709",
       "-color_primaries", "bt709", "-color_trc", "bt709",
       "-c:a", "aac", "-b:a", "160k", "-ar", str(SR), "-ac", "2"]


def scene_still(img: str, card: str, aud: str, out: str) -> None:
    """Slow Ken Burns push on a still, with the text overlay and the beat's voice."""
    d = dur(aud) + 0.6
    # Normalise to 16:9 first (the generator crops 6% off the bottom to drop the
    # watermark, so a still arrives slightly short), then upscale and slow-push.
    vf = (f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
          f"scale={int(W * 1.18)}:{int(H * 1.18)},"
          f"zoompan=z='1.0+0.0008*in':x='iw/2-(iw/zoom/2)':"
          f"y='ih/2-(ih/zoom/2)':d=1:s={W}x{H}:fps={FPS},setsar=1[bg];"
          f"[bg][1:v]overlay=0:0,format=yuv420p[v]")
    sh(["ffmpeg", "-y", "-loglevel", "error",
        "-loop", "1", "-t", f"{d:.3f}", "-i", img,
        "-i", card, "-i", aud,
        "-filter_complex", vf, "-map", "[v]", "-map", "2:a",
        *ENC, "-shortest", out])


def scene_hero(clip: str, card: str, aud: str, out: str) -> None:
    """A pre-rendered clip as the beat base (the paid-presenter drop-in slot)."""
    d = dur(aud) + 0.6
    vf = (f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,"
          f"crop={W}:{H},fps={FPS},setsar=1,"
          f"tpad=stop_mode=clone:stop_duration=2[bg];"
          f"[bg][1:v]overlay=0:0,format=yuv420p[v]")
    sh(["ffmpeg", "-y", "-loglevel", "error", "-i", clip,
        "-i", card, "-i", aud,
        "-filter_complex", vf, "-map", "[v]", "-map", "2:a",
        *ENC, "-t", f"{d:.3f}", out])


def concat(parts: list[str], out: str, work: str) -> None:
    lst = os.path.join(work, "concat.txt")
    with open(lst, "w") as f:
        for p in parts:
            f.write(f"file '{os.path.abspath(p)}'\n")
    sh(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
        "-i", lst, "-c", "copy", out])


# YouTube normalises toward -14 LUFS integrated; a clip that lands quieter is not
# boosted, so it just plays soft. The repo's make_audio.py uses the same target.
LOUD_I, LOUD_TP, LOUD_LRA = -14.0, -3.0, 11.0


def measure_loud(path: str) -> tuple[float, float]:
    """(integrated LUFS, true peak dBFS) of a file's audio."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path,
                        "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True)
    tail = r.stderr[r.stderr.rfind("Summary:"):]
    i = re.search(r"I:\s*(-?\d+\.\d+)\s*LUFS", tail)
    tp = re.search(r"Peak:\s*(-?\d+\.\d+)\s*dBFS", tail)
    return (float(i.group(1)) if i else float("nan"),
            float(tp.group(1)) if tp else float("nan"))


def finalize(out: str) -> None:
    """Two-pass EBU R128 to -14 LUFS, keeping the video stream untouched."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", out, "-af",
                        f"loudnorm=I={LOUD_I}:TP={LOUD_TP}:LRA={LOUD_LRA}"
                        ":print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True)
    m = re.search(r'\{[^{}]*"input_i"[^{}]*\}', r.stderr, re.S)
    if not m:
        print("  (loudnorm measurement failed; keeping original audio)")
        return
    s = json.loads(m.group(0))
    chain = (f"loudnorm=I={LOUD_I}:TP={LOUD_TP}:LRA={LOUD_LRA}"
             f":measured_I={s['input_i']}:measured_TP={s['input_tp']}"
             f":measured_LRA={s['input_lra']}:measured_thresh={s['input_thresh']}"
             f":offset={s['target_offset']}:linear=true")
    tmp = out + ".norm.mp4"
    sh(["ffmpeg", "-y", "-loglevel", "error", "-i", out, "-c:v", "copy",
        "-af", chain, "-c:a", "aac", "-b:a", "192k", "-ar", str(SR), "-ac", "2", tmp])
    os.replace(tmp, out)


def build(script_path: str, out: str, work: str, style: str, voice_name: str,
          rate: str, hero_dir: str | None) -> None:
    spec = json.load(open(script_path, encoding="utf-8"))
    beats = spec["beats"]
    os.makedirs(work, exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    parts = []
    for i, b in enumerate(beats, 1):
        tag = f"{i:02d}"
        img = os.path.join(work, f"{tag}_still.jpg")
        card = os.path.join(work, f"{tag}_card.png")
        aud = os.path.join(work, f"{tag}.mp3")
        seg = os.path.join(work, f"{tag}.mp4")
        spoken = " ".join(x for x in (b.get("question", ""), b.get("answer", "")) if x)
        if not os.path.exists(img):
            still(b["image"], img, style, seed_of(b.get("image", tag)))
        text_card(b.get("question", ""), b.get("answer", ""), card)
        voice(spoken, aud, voice_name, rate)
        hero = os.path.join(hero_dir, f"{tag}.mp4") if hero_dir else None
        if hero and os.path.exists(hero):
            print(f"  beat {tag}: hero clip {hero}")
            scene_hero(hero, card, aud, seg)
        else:
            print(f"  beat {tag}: still ({dur(aud):.1f}s)")
            scene_still(img, card, aud, seg)
        parts.append(seg)
    concat(parts, out, work)
    finalize(out)


def verify(out: str) -> int:
    info = probe(out)
    vs = [s for s in info.get("streams", []) if s["codec_type"] == "video"]
    aud = [s for s in info.get("streams", []) if s["codec_type"] == "audio"]
    ok = True
    print(f"\nVERIFY {out}")
    print(f"  duration : {dur(out):.2f} s")
    if vs:
        v = vs[0]
        print(f"  video    : {v.get('width')}x{v.get('height')} range={v.get('color_range')}")
        if (v.get("width"), v.get("height")) != (W, H):
            print("  FAIL: not 1280x720"); ok = False
        if v.get("color_range") != "tv":
            print("  FAIL: color_range must be tv (verify_night requires it)"); ok = False
    else:
        print("  FAIL: no video stream"); ok = False
    if not aud:
        print("  FAIL: no audio stream"); ok = False
    else:
        i, tp = measure_loud(out)
        print(f"  audio    : {i:.1f} LUFS, true peak {tp:.1f} dBFS")
        if not (LOUD_I - 1.5 <= i <= LOUD_I + 1.5):
            print(f"  FAIL: loudness {i:.1f} LUFS is off the {LOUD_I} target"); ok = False
        if tp > LOUD_TP + 0.5:
            print(f"  FAIL: true peak {tp:.1f} dBFS exceeds {LOUD_TP}"); ok = False
    print("  RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--script", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--work", default="")
    ap.add_argument("--style", default="knowledge")
    ap.add_argument("--voice", default=VOICE)
    ap.add_argument("--rate", default=RATE)
    ap.add_argument("--hero-dir", default=None,
                    help="dir of NN.mp4 clips; beat NN uses its clip instead of a still")
    ap.add_argument("--no-verify", action="store_true")
    a = ap.parse_args()
    work = a.work or os.path.join(os.path.dirname(os.path.abspath(a.out)), "qa_work")
    build(a.script, a.out, work, a.style, a.voice, a.rate, a.hero_dir)
    return verify(a.out) if not a.no_verify else 0


if __name__ == "__main__":
    sys.exit(main())
