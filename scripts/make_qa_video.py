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
import shutil
import subprocess
import sys
import time

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import fetch_broll  # noqa: E402
FONTS = os.path.join(ROOT, "assets", "fonts")
W, H, FPS = 1920, 1080, 30
# Reject b-roll whose mean luma is below this: a dark clip makes the beat read
# muddy ('ขุ่นมัว'), the exact complaint the owner raised (measured 2026-11-17:
# a 'sleepy' clip landed at luma 70). Bright, airy footage is the 10/10 target.
MIN_BROLL_LUMA = 95.0
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


BRAND = "#FFB020"   # warm amber accent -- the reference's warm palette


def text_card(question: str, answer: str, out: str, brand: str = "") -> None:
    """FLOATING text: no dark boxes -- crisp white type with a stroke + soft shadow.

    Measured 2026-11-17, a 4/5 advisor panel and a vision rubric agreed the
    frosted-glass boxes read as 'PowerPoint / UI clutter' and that clean floating
    type reads more premium. So the question sits top-left and the answer is
    centred near the bottom, both as white Kanit with a heavy dark stroke (a
    stroke, not a box, keeps Thai legible over bright b-roll) plus a soft drop
    shadow for lift. Sizes are scaled for the 1080p render. The caller animates
    the whole card in (fade + rise).
    """
    card = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(card)
    fq = ImageFont.truetype(os.path.join(FONTS, "Kanit-Bold.ttf"), 88)
    fa = ImageFont.truetype(os.path.join(FONTS, "Kanit-SemiBold.ttf"), 58)
    fb = ImageFont.truetype(os.path.join(FONTS, "Kanit-SemiBold.ttf"), 34)

    def wrap(s, font, max_w):
        """Greedy wrap on spaces so the question reads as a compact stack, not one
        long line stretched across the frame (a vision grader flagged the single
        wide line, 2026-11-17)."""
        words, lines, cur = s.split(), [], ""
        for w in words:
            trial = f"{cur} {w}".strip()
            if cur and d.textlength(trial, font=font) > max_w:
                lines.append(cur)
                cur = w
            else:
                cur = trial
        if cur:
            lines.append(cur)
        return lines

    def txt(xy, s, font, anchor, stroke=8):
        x, y = xy
        shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow)
        sd.text((x + 5, y + 6), s, font=font, fill=(0, 0, 0, 150),
                anchor=anchor, stroke_width=stroke, stroke_fill=(0, 0, 0, 150))
        card.alpha_composite(shadow)
        d.text((x, y), s, font=font, fill=(255, 255, 255, 255), anchor=anchor,
               stroke_width=stroke, stroke_fill=(10, 12, 18, 235))

    if question:
        for i, line in enumerate(wrap(question, fq, int(W * 0.62))):
            txt((72, 120 + i * 108), line, fq, "la")

    if answer:
        # Wrap a long answer into a compact stack and sit it in the safe area,
        # clear of the bottom edge (a grader flagged the cramped margin and the
        # crowded single line, 2026-11-17).
        lines = wrap(answer, fa, int(W * 0.74))
        y0 = H - 200 - (len(lines) - 1) * 66
        for i, line in enumerate(lines):
            txt((W // 2, y0 + i * 66), line, fa, "mm", stroke=6)

    if brand:
        # A small, low-opacity corner bug -- present for identity but quiet, so it
        # does not read as the 'visual clutter' a grader flagged (2026-11-17).
        bug = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        bd = ImageDraw.Draw(bug)
        bd.text((W - 64, 70), brand, font=fb, fill=(255, 255, 255, 170), anchor="ra",
                stroke_width=4, stroke_fill=(10, 12, 18, 150))
        card.alpha_composite(bug)

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


# crf 18 at 1080p (measured 2026-11-17: a 4/5 panel wanted 15-20 Mbps so the
# cleaned-up picture is not re-smeared by compression; crf 20 at 720p was
# ~2 Mbps and read soft). veryfast keeps the render time sane.
ENC = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
       "-pix_fmt", "yuv420p", "-r", str(FPS),
       "-color_range", "tv", "-colorspace", "bt709",
       "-color_primaries", "bt709", "-color_trc", "bt709",
       "-c:a", "aac", "-b:a", "160k", "-ar", str(SR), "-ac", "2"]


def _card_anim() -> tuple[str, str]:
    """Card input chain + overlay x:y that fades and rises the text in.

    The reference feels edited, not assembled: its text arrives. A hard-cut static
    card was graded 'PowerPoint' (2026-11-17), so every beat animates the card in
    with a 0.5 s alpha fade and a small upward settle.
    """
    chain = "format=rgba,fade=t=in:st=0:d=0.5:alpha=1"
    xy = "x=0:y='if(lt(t,0.5),30*(1-t/0.5),0)'"
    return chain, xy


# A CLEAN warm grade applied to EVERY clip, so sky, beach and cat footage read as
# one story instead of a stock grab-bag. NO film grain, NO vignette: measured
# 2026-11-17 the owner rejected the old grade as "ไม่คมชัด ขุ่นมัว" (not sharp,
# muddy) and a vision grader agreed -- `noise=alls=4` + `vignette=PI/4.5` scored
# 2/10 ("smeared vaseline, digital noise, muddy vignette"), mean luma fell
# 171->123. Dropping both and adding `unsharp` lifted the same frame to 8/10
# sharpness, 9/10 brightness. `cas` (contrast-adaptive sharpen) then doubles the
# local detail (measured LapVar 37->90 on a hazy ocean frame) without losing
# brightness, which is what "คมชัด แจ่มใส" needs. Warmth stays mild for cohesion.
GRADE = ("colorbalance=rs=0.03:gs=0.01:bs=-0.03,"
         "eq=contrast=1.08:saturation=1.14:brightness=0.025,"
         "unsharp=5:5:0.6:3:3:0.0,cas=0.6")


def scene_still(img: str, card: str, aud: str, out: str) -> None:
    """Slow Ken Burns push on a still, with the animated text overlay and voice."""
    d = dur(aud) + 0.6
    chain, xy = _card_anim()
    # Normalise to 16:9 first (the generator crops 6% off the bottom to drop the
    # watermark, so a still arrives slightly short), then upscale and slow-push.
    vf = (f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
          f"scale={int(W * 1.18)}:{int(H * 1.18)},"
          f"zoompan=z='1.0+0.0008*in':x='iw/2-(iw/zoom/2)':"
          f"y='ih/2-(ih/zoom/2)':d=1:s={W}x{H}:fps={FPS},{GRADE},setsar=1[bg];"
          f"[1:v]{chain}[card];"
          f"[bg][card]overlay={xy},format=yuv420p[v]")
    sh(["ffmpeg", "-y", "-loglevel", "error",
        "-loop", "1", "-t", f"{d:.3f}", "-i", img,
        "-loop", "1", "-i", card, "-i", aud,
        "-filter_complex", vf, "-map", "[v]", "-map", "2:a",
        *ENC, "-shortest", out])


# The b-roll drift needs an upscale first to have crop room, and every upscale
# costs sharpness (measured 2026-11-17: native centre LapVar 119 vs 88 at 1.12x).
# So the zoom is kept small and both scales use lanczos (95.7 vs bicubic 87.6 at
# 1.12x) -- the guard test_qa_video.py #8 fails if this softens the picture.
BROLL_ZOOM = 1.06
BROLL_FLAGS = "lanczos"
# Per-clip brightness normalisation: stock clips vary a lot (measured 2026-11-17
# the 'cat' clip landed at luma 107 while the 'sky' clip was 176), and a dark beat
# reads as 'ขุ่นมัว' next to a bright one. So each clip is measured and gamma-lifted
# toward this target (capped, so a bright clip is left alone and highlights hold).
BROLL_LUMA_TARGET = 150.0
BROLL_GAMMA_MAX = 1.55


def broll_gamma(clip: str) -> float:
    """Gamma to lift `clip` toward BROLL_LUMA_TARGET, capped. Measured, not fixed."""
    lum = fetch_broll.mean_luma(clip)
    if lum >= BROLL_LUMA_TARGET:
        return 1.0
    g = 1.0 + (BROLL_LUMA_TARGET - lum) / 120.0
    return round(min(g, BROLL_GAMMA_MAX), 3)


def broll_chain(clip: str) -> str:
    """Background chain: fit to 16:9, small lanczos zoom, drift, normalise, grade."""
    zx, zy = int(W * BROLL_ZOOM), int(H * BROLL_ZOOM)
    dx, dy = int(W * (BROLL_ZOOM - 1) / 2), int(H * (BROLL_ZOOM - 1) / 2)
    g = broll_gamma(clip)
    norm = "" if g == 1.0 else f"eq=gamma={g},"
    return (f"scale={W}:{H}:force_original_aspect_ratio=increase:flags={BROLL_FLAGS},"
            f"crop={W}:{H},scale={zx}:{zy}:flags={BROLL_FLAGS},"
            f"crop={W}:{H}:x='{dx}+{dx}*sin(2*PI*t/23)':"
            f"y='{dy}+{dy}*cos(2*PI*t/29)',fps={FPS},{norm}{GRADE},setsar=1")


def scene_broll(clip: str, card: str, aud: str, out: str) -> None:
    """REAL b-roll as the beat base (the reference's actual look).

    A free generative model cannot make a believable human (measured 2026-11-17:
    pollinations 3-4/10, Gemini free image quota 0), so the standard uses free
    licence-clean real footage (fetch_broll.py -> Coverr). The clip is looped to
    the narration length, scaled/cropped to 16:9, brightness-normalised, graded to
    one look, and the animated Thai Q/A card is laid over it.
    """
    d = dur(aud) + 0.6
    chain, xy = _card_anim()
    vf = (f"[0:v]{broll_chain(clip)}[bg];"
          f"[1:v]{chain}[card];"
          f"[bg][card]overlay={xy},format=yuv420p[v]")
    sh(["ffmpeg", "-y", "-loglevel", "error", "-stream_loop", "-1", "-i", clip,
        "-loop", "1", "-i", card, "-i", aud,
        "-filter_complex", vf, "-map", "[v]", "-map", "2:a",
        *ENC, "-t", f"{d:.3f}", out])


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



def concat_xfade(parts: list[str], out: str, work: str, xf: float = 0.5) -> None:
    """Join the beats with a crossfade instead of a hard cut.

    A hard cut between two unrelated stock shots reads as assembled; the reference
    is edited. Every segment is the same 1280x720/30fps/yuv420p so an xfade chain
    (video) plus acrossfade (audio) is safe, at the cost of one re-encode.
    """
    if len(parts) == 1:
        shutil.copyfile(parts[0], out)
        return
    ds = [dur(p) for p in parts]
    inputs: list[str] = []
    for p in parts:
        inputs += ["-i", p]
    fc, off = [], ds[0] - xf
    vprev = "[0:v]"
    for i in range(1, len(parts)):
        lbl = f"[vx{i}]"
        fc.append(f"{vprev}[{i}:v]xfade=transition=fade:duration={xf}:"
                  f"offset={off:.3f}{lbl}")
        vprev = lbl
        off += ds[i] - xf
    aprev = "[0:a]"
    for i in range(1, len(parts)):
        lbl = f"[ax{i}]"
        fc.append(f"{aprev}[{i}:a]acrossfade=d={xf}:c1=tri:c2=tri{lbl}")
        aprev = lbl
    sh(["ffmpeg", "-y", "-loglevel", "error", *inputs,
        "-filter_complex", ";".join(fc), "-map", vprev, "-map", aprev,
        *ENC, "-movflags", "+faststart", out])


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
          rate: str, hero_dir: str | None, broll: bool = True,
          brand: str = "") -> None:
    spec = json.load(open(script_path, encoding="utf-8"))
    beats = spec["beats"]
    brand = brand or spec.get("brand") or spec.get("title", "")
    os.makedirs(work, exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    used: set = set()
    credits: list = []
    parts = []
    for i, b in enumerate(beats, 1):
        tag = f"{i:02d}"
        img = os.path.join(work, f"{tag}_still.jpg")
        clip = os.path.join(work, f"{tag}_broll.mp4")
        card = os.path.join(work, f"{tag}_card.png")
        aud = os.path.join(work, f"{tag}.mp3")
        seg = os.path.join(work, f"{tag}.mp4")
        spoken = " ".join(x for x in (b.get("question", ""), b.get("answer", "")) if x)
        text_card(b.get("question", ""), b.get("answer", ""), card, brand)
        voice(spoken, aud, voice_name, rate)
        hero = os.path.join(hero_dir, f"{tag}.mp4") if hero_dir else None

        got_clip = False
        if hero and os.path.exists(hero):
            clip = hero
            got_clip = True
        elif broll and os.path.exists(clip):
            # A cached clip from an earlier run is reused, not discarded -- the
            # old `not os.path.exists` guard skipped the fetch AND never set
            # got_clip, so a rebuild silently fell back to a still (measured
            # 2026-11-17: run 2 rendered 3 of 4 beats as stills).
            got_clip = True
        elif broll:
            q = b.get("broll") or b.get("image", "")
            hit = fetch_broll.pick_and_download(q, clip, avoid=used,
                                                min_luma=MIN_BROLL_LUMA) if q else None
            if hit:
                used.add(hit.get("id"))
                credits.append({"beat": tag, **fetch_broll.attribution(hit)})
                got_clip = True
            else:
                print(f"  beat {tag}: no usable b-roll for {q!r}; using a still",
                      file=sys.stderr)

        if got_clip:
            print(f"  beat {tag}: real b-roll ({dur(aud):.1f}s)")
            scene_broll(clip, card, aud, seg)
        else:
            if not os.path.exists(img):
                still(b.get("image", tag), img, style, seed_of(b.get("image", tag)))
            print(f"  beat {tag}: still ({dur(aud):.1f}s)")
            scene_still(img, card, aud, seg)
        parts.append(seg)

    xf = 0.5
    body = os.path.join(work, "_body.mp4")
    concat_xfade(parts, body, work, xf)
    finalize(body)
    os.replace(body, out)
    if credits:
        att = os.path.join(work, "attribution.json")
        json.dump(credits, open(att, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print(f"  b-roll credits -> {att} ({len(credits)} clips)")


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
    ap.add_argument("--brand", default="", help="channel bug text (defaults to the script title)")
    ap.add_argument("--voice", default=VOICE)
    ap.add_argument("--rate", default=RATE)
    ap.add_argument("--hero-dir", default=None,
                    help="dir of NN.mp4 clips; beat NN uses its clip instead of a still")
    ap.add_argument("--no-broll", action="store_true",
                    help="use AI stills only (the legacy path); b-roll is the default")
    ap.add_argument("--no-verify", action="store_true")
    a = ap.parse_args()
    work = a.work or os.path.join(os.path.dirname(os.path.abspath(a.out)), "qa_work")
    build(a.script, a.out, work, a.style, a.voice, a.rate, a.hero_dir,
          broll=not a.no_broll, brand=a.brand)
    return verify(a.out) if not a.no_verify else 0


if __name__ == "__main__":
    sys.exit(main())
