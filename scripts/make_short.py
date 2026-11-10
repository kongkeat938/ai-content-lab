#!/usr/bin/env python3
"""Build a vertical Short (1080x1920) from a script: voice, captions, and a slow
ken-burns backdrop -- free tools only.

Shorts are the reach engine: they get shown to people who do not know the
channel, and each one points at a long video. The long video is what collects the
watch hours the Partner Programme counts, so the funnel is Short -> long, and
this script makes the Short.

    python3 scripts/make_short.py --scripts content/ch2_shorts/scripts.json \
        --out-dir work/ch2_shorts --index 01

Input shape (written by Gemini, see content/ch2_shorts/scripts.json):
    {"id": "01", "hook": "...", "lines": ["...", ...], "cta": "..."}

The hook is spoken first and shown big; the CTA is appended as the last line, so
every Short ends asking for the follow. Numbers must already be Thai words --
edge-tts has no Thai number dictionary and would read a digit wrong.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import os
import subprocess
import sys

import edge_tts
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)
FONTS = os.path.join(ROOT, "assets", "fonts")
VOICE = "th-TH-NiwatNeural"      # calm male narrator, the channel's voice
# The changed voice a withheld channel comes back with (2026-11-10). A five-advisor
# panel was unanimous that kongkeat's feed stop came from the same voice + template
# repeated 17-22 times a day; the recovery has to sound different, so a stalled
# channel's probe clip uses this instead of VOICE. Female, so the change is audible.
VOICE_ALT = "th-TH-PremwadeeNeural"
# A slower read: the niche's winners run about a minute, and a slow read holds a
# sleepy listener better than a clipped one.
RATE = "-15%"
W, H = 1080, 1920
GOLD = (245, 199, 90)
WHITE = (250, 250, 252)
# House targets (see docs/RECIPE.md): -14 LUFS integrated, true peak <= -3 dBFS.
LUFS, TP = -14, -3.0
COMP_TH, COMP_RATIO = "-24dB", 6
# A bed eats the headroom loudnorm needs to reach -14 LUFS in linear mode, so the
# bed path adds this much gain before the limiter. Measured 2026-11-07.
BED_GAIN_DB = 2.0
# How far under the voice the bed sits. Measured 2026-11-09: the old fixed 0.18
# (-14.9 dB) put a -22 LUFS bed at -36.9 LUFS -- ~16 LU below the voice, i.e.
# effectively silent, which is why the owner could not hear the music at all.
# Target the bed ~11 LU under the voice, computed from each file's own loudness so
# a quiet bed and a loud bed land the same. Clamped so a very quiet file is not
# blown up into hiss.
BED_UNDER_VOICE_DB = 11.0
BED_GAIN_MIN, BED_GAIN_MAX = 0.05, 0.60
# Where a mid-clip CTA sits, as a fraction of the story lines. 0.6 lands it just
# past the peak but before the wind-down, which is where a five-advisor panel put
# it for ch4 (2026-11-09). See build().
CTA_MID_RATIO = 0.6


def bed_gain(music: str, voice_lufs: float) -> float:
    bed_lufs = measure_audio(music)
    if bed_lufs is None:
        return 0.18
    gain = 10 ** ((voice_lufs - BED_UNDER_VOICE_DB - bed_lufs) / 20.0)
    return max(BED_GAIN_MIN, min(BED_GAIN_MAX, gain))


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(os.path.join(FONTS, name), size)


def run(cmd: list) -> None:
    subprocess.run(cmd, check=True, capture_output=True)


def measure_audio(path: str) -> float | None:
    """Integrated loudness (LUFS) of a file, or None if it cannot be read."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path,
                        "-af", "ebur128=framelog=quiet", "-f", "null", "-"],
                       capture_output=True, text=True)
    for line in r.stderr.splitlines():
        if "I:" in line and "LUFS" in line:
            try:
                return float(line.split("I:")[1].split("LUFS")[0].strip())
            except ValueError:
                return None
    return None


async def speak(text: str, out: str, voice: str = VOICE) -> None:
    """Synthesise the line, retrying a dropped connection.

    edge-tts occasionally returns NoAudioReceived on a line that works on the
    next try (observed in CI on 2026-11-03, which failed a whole build). It is a
    transient socket fault, not bad input, so retry rather than lose the clip.
    """
    last = None
    for attempt in range(4):
        try:
            await edge_tts.Communicate(text, voice, rate=RATE).save(out)
            if os.path.exists(out) and os.path.getsize(out) > 0:
                return
            last = "empty file"
        except Exception as exc:            # noqa: BLE001 -- the point is to swallow any TTS fault
            last = exc
        await asyncio.sleep(2 * (attempt + 1))
    raise RuntimeError(f"TTS failed after 4 tries: {last}")


def duration(path: str) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", path], capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def backdrop(out: str, art: str | None) -> None:
    """A calm 1080x1920 frame. Uses channel art when given, else a gradient.

    The owner asked for a brighter frame (2026-11-07): the earlier cut softened
    and darkened the photo so hard that the screen read as black on a phone, and
    measured, 7 of the 30 art stills are dark to begin with (mean luminance 22-58
    against 114-189 for the rest). So the photo is auto-levelled to a target
    brightness first -- a fixed multiplier cannot lift a dark still without
    blowing out a bright one -- then lightly softened and scrimmed from the
    bottom only, so the image stays visible while captions sit on a dark strip.
    """
    from PIL import ImageEnhance, ImageFilter
    TARGET = 120.0
    if art and os.path.exists(art):
        im = Image.open(art).convert("RGB")
        r = max(W / im.width, H / im.height)
        im = im.resize((int(im.width * r), int(im.height * r)), Image.LANCZOS)
        left = (im.width - W) // 2
        top = (im.height - H) // 2
        im = im.crop((left, top, left + W, top + H))
        im = im.filter(ImageFilter.GaussianBlur(2))
        lum = im.convert("L")
        mean = sum(lum.histogram()[i] * i for i in range(256)) / (W * H)
        if mean < TARGET:
            # Gamma lifts the shadows of a dark still without clipping a bright
            # one the way a straight brightness multiply does.
            gamma = 1.0 + min(1.2, (TARGET - mean) / TARGET * 1.6)
            lut = [min(255, int(255 * (i / 255) ** (1 / gamma))) for i in range(256)]
            im = im.point(lut * 3)
        im = ImageEnhance.Brightness(im).enhance(1.08)
        im = ImageEnhance.Color(im).enhance(1.15)
    else:
        im = Image.new("RGB", (W, H), (26, 40, 72))
    # A short bottom scrim so captions read, leaving the top two-thirds bright.
    scrim = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(scrim)
    for y in range(H):
        v = 0
        if y > H * 0.55:
            v = int(150 * ((y - H * 0.55) / (H * 0.45)) ** 1.2)
        d.line([(0, y), (W, y)], fill=v)
    im = Image.composite(Image.new("RGB", (W, H), (8, 12, 24)), im, scrim)
    im.save(out, quality=95)


def wrap(draw: ImageDraw.ImageDraw, text: str, f: ImageFont.FreeTypeFont,
         max_w: int) -> list[str]:
    """Thai has no spaces between words, so break by measuring character runs."""
    lines, cur = [], ""
    for ch in text:
        trial = cur + ch
        if draw.textlength(trial, font=f) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = ch
    if cur:
        lines.append(cur)
    return lines


def caption_image(text: str, out: str, big: bool = False) -> None:
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    size = 96 if big else 78
    f = font("Kanit-Bold.ttf", size)
    lines = wrap(d, text, f, W - 160)
    lh = int(size * 1.35)
    total = lh * len(lines)
    y = int(H * 0.66) if not big else int(H * 0.42)
    y = min(y, H - 340 - total)
    for i, ln in enumerate(lines):
        tw = d.textlength(ln, font=f)
        x = (W - tw) / 2
        d.text((x, y + i * lh), ln, font=f, fill=GOLD if big else WHITE,
               stroke_width=6, stroke_fill=(0, 0, 0, 235))
    im.save(out)


def normalise(src: str, out: str, gain_db: float = 0.0) -> None:
    """Two-pass loudnorm to -14 LUFS with a hard ceiling at -3 dBFS.

    A single-pass loudnorm does not honour the true-peak target reliably: measured
    on the first GenX Short it landed at -1.3 dBTP, over the -3 dBFS the channel
    is required to keep. The two-pass form measures first, then applies the
    measured values, and alimiter is a final guarantee rather than a hope.

    gain_db is applied after loudnorm, before the limiter. With a music bed mixed
    in, loudnorm's linear mode cannot reach -14 without breaking the ceiling (the
    bed eats the headroom), so the bed path adds +2 dB and lets alimiter hold the
    peak. Measured 2026-11-07: bed path -15.5 -> -14.2 LUFS, TP -2.98 dBTP.
    """
    # acompressor first: a bare narrator read has ~18 dB of crest factor, so
    # loudnorm alone cannot reach -14 LUFS without the true peak breaking -3 dBFS.
    # Measured on the first GenX Short, this chain lands at -14.x LUFS / -3.0 dBTP.
    chain = (f"acompressor=threshold={COMP_TH}:ratio={COMP_RATIO}:attack=3:release=120,"
             f"loudnorm=I={LUFS}:TP={TP}:LRA=11")
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", src,
                        "-af", chain + ":print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True)
    tail = r.stderr[r.stderr.rfind("{"):]
    tail = tail[:tail.rfind("}") + 1]
    m = json.loads(tail)
    gain = f",volume={gain_db}dB" if gain_db else ""
    run(["ffmpeg", "-y", "-i", src, "-af",
         f"{chain}:measured_I={m['input_i']}:measured_TP={m['input_tp']}"
         f":measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}"
         f":offset={m['target_offset']}:linear=true{gain},"
         f"alimiter=limit={TP}dB:level=disabled",
         "-ar", "48000", "-c:a", "pcm_s16le", out])


def spoken_sequence(script: dict, cta_mid: bool = False) -> list[str]:
    """The caption/voice order: hook, story lines, and the CTA.

    Default keeps the CTA last. `cta_mid` drops it in after the story's peak
    (CTA_MID_RATIO through the lines) -- the ch4 experiment. Kept separate from
    build() so the placement is unit-tested without running ffmpeg.
    """
    seq = [script["hook"], *script["lines"]]
    if cta_mid:
        pos = 1 + round(len(script["lines"]) * CTA_MID_RATIO)
        seq.insert(min(pos, len(seq)), script["cta"])
    else:
        seq.append(script["cta"])
    return seq


def build(script: dict, out_dir: str, art: str | None, music: str | None,
          cta_mid: bool = False, voice: str | None = None) -> str:
    sid = script["id"]
    d = os.path.join(out_dir, sid)
    os.makedirs(d, exist_ok=True)

    # Spoken text: hook, then the lines, then the CTA. Blank lines become the
    # pause edge-tts reads between them, so the read breathes.
    #
    # cta_mid moves the CTA to just after the story's peak (K's ch4 experiment,
    # 2026-11-09). Measured: ch4 watched to the end (59.5% avg) but converted
    # 1.79 subs/1k vs ch1's 5.38 and 0 shares/comments -- a subscribe ask at the
    # tail lands after the viewer has swiped. A five-advisor panel put the CTA
    # mid-clip; this is that change, kept to the channel the numbers flag.
    seq = spoken_sequence(script, cta_mid)
    spoken = "\n".join(seq)
    voice_mp3 = os.path.join(d, "voice.mp3")
    if not os.path.exists(voice_mp3):
        # K's cloned voice when it is configured (see tts_fish.py), the house
        # edge-tts voice otherwise. Either way the file lands at voice.mp3, so a
        # voice already synthesised by hand is never overwritten.
        try:
            import tts_fish
        except ImportError:
            tts_fish = None
        if tts_fish and tts_fish.available():
            tts_fish.synth(spoken, voice_mp3)
        else:
            asyncio.run(speak(spoken, voice_mp3, voice or VOICE))
    dur = duration(voice_mp3)

    # Captions: one PNG per line, shown for its share of the audio. The order
    # must match `seq` so a mid-clip CTA shows where it is spoken.
    shown = seq
    cards = []
    for i, text in enumerate(shown):
        p = os.path.join(d, f"cap_{i:02d}.png")
        caption_image(text, p, big=(i == 0))
        cards.append(p)

    # Rough per-line timing: proportional to character count. Exact timing is
    # not needed for a Short; the card changes feel deliberate either way.
    weights = [max(1, len(t)) for t in shown]
    tot = sum(weights)
    bounds, acc = [], 0.0
    for wgt in weights:
        acc += dur * wgt / tot
        bounds.append(acc)

    bg = os.path.join(d, "bg.jpg")
    backdrop(bg, art)

    # Assemble: loop the still, overlay each caption for its window, mux audio.
    parts = []
    prev = 0.0
    for i, (card, end) in enumerate(zip(cards, bounds)):
        seg = os.path.join(d, f"seg_{i:02d}.mp4")
        seg_len = max(0.4, end - prev)
        vf = (f"[1:v]scale={W}:{H}[c];[0:v][c]overlay=0:0:format=auto[v]")
        cmd = ["ffmpeg", "-y", "-loop", "1", "-t", f"{seg_len:.3f}", "-i", bg,
               "-loop", "1", "-t", f"{seg_len:.3f}", "-i", card,
               "-filter_complex", vf, "-map", "[v]",
               "-r", "30", "-pix_fmt", "yuv420p", "-c:v", "libx264",
               "-preset", "veryfast", "-crf", "20", seg]
        run(cmd)
        parts.append(seg)
        prev = end

    listfile = os.path.join(d, "parts.txt")
    with open(listfile, "w") as fh:
        for p in parts:
            # ffmpeg resolves relative paths in a concat list against the list
            # file's own directory, so a relative path here is doubled. Absolute
            # paths are unambiguous.
            fh.write(f"file '{os.path.abspath(p)}'\n")
    silent = os.path.join(d, "silent.mp4")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", listfile,
         "-c", "copy", silent])

    out = os.path.join(d, f"short_{sid}.mp4")
    # Mix the voice (and optional bed) to a normalised wav, then mux it under the
    # already-encoded video. Doing loudness in one pass over the mux is what let
    # the true peak run to -1.3 dBTP.
    mixed = os.path.join(d, "mix.wav")
    if music and os.path.exists(music):
        # -stream_loop repeats the bed if it is shorter than the read, so a short
        # CC0 bed still covers the whole clip instead of dropping out mid-sentence.
        # normalize=0 keeps the voice at its own level; the default amix halves
        # every input, which dropped the mix ~0.6 LU below the music-less cut.
        v_lufs = measure_audio(voice_mp3) or -20.0
        vol = bed_gain(music, v_lufs)
        print(f"  bed gain {vol:.3f} ({20 * math.log10(vol):.1f} dB)")
        run(["ffmpeg", "-y", "-i", voice_mp3, "-stream_loop", "-1", "-i", music,
             "-filter_complex",
             f"[1:a]volume={vol:.4f}[m];[0:a][m]amix=inputs=2:duration=first:"
             "dropout_transition=0:normalize=0[a]",
             "-map", "[a]", "-ar", "48000", mixed])
    else:
        run(["ffmpeg", "-y", "-i", voice_mp3, "-ar", "48000", mixed])
    norm = os.path.join(d, "norm.wav")
    normalise(mixed, norm, gain_db=BED_GAIN_DB if (music and os.path.exists(music)) else 0.0)
    run(["ffmpeg", "-y", "-i", silent, "-i", norm, "-map", "0:v", "-map", "1:a",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", out])
    print(f"  {sid}: {duration(out):.1f}s -> {out}")
    return out


def pick_art(art_dir: str, sid: str) -> str | None:
    """Choose one still from a folder, stable across rebuilds.

    Kept for the remake rail and as a last resort. It is NOT how a new Short gets
    its picture: a folder of ten stills shared by a hundred clips repeats every
    image about ten times, which the owner forbade ("no two clips may share an
    image, ever"). unique_art() generates one image per clip instead.
    """
    if not art_dir or not os.path.isdir(art_dir):
        return None
    pool = sorted(f for f in os.listdir(art_dir)
                  if f.lower().endswith((".jpg", ".jpeg", ".png")))
    if not pool:
        return None
    h = 0
    for ch in sid:
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    return os.path.join(art_dir, pool[h % len(pool)])


def unique_art(d: str, sid: str, hook: str, art_style: str | None,
               art_dir: str | None, ledger_path: str | None) -> str | None:
    """One image that no other clip uses. Measured 2026-11-09: pick_art over a
    10-still pool gave each ch4 image to ~5 of its 49 live Shorts, ch2 to ~11 of
    104. The owner forbade repeats, so a new Short now gets a picture generated
    from a seed of its own id, and the md5 of every image made is kept in a
    committed ledger -- if a generation ever collides, it is re-seeded.

    Cached at <d>/art.jpg so a rebuild of the same clip reuses the exact picture
    the reviewer already saw (the render dir is stable for one id)."""
    cache = os.path.join(d, "art.jpg")
    if os.path.exists(cache):
        return cache
    if not art_style:
        return pick_art(art_dir, sid)
    import gen_cover_image as G
    seed0 = int(hashlib.sha256(sid.encode("utf-8")).hexdigest()[:8], 16)
    used = {}
    if ledger_path and os.path.exists(ledger_path):
        try:
            with open(ledger_path, encoding="utf-8") as fh:
                used = json.load(fh).get("md5", {})
        except (OSError, ValueError):
            used = {}
    for bump in range(8):
        data, source = G.generate(art_style, hook or "", seed0 + bump, 1080, 1920)
        if not data:
            continue
        md5 = hashlib.md5(data).hexdigest()
        if used.get(md5, sid) == sid:      # unused, or already ours
            os.makedirs(d, exist_ok=True)
            with open(cache, "wb") as fh:
                fh.write(data)
            if ledger_path:
                used[md5] = sid
                tmp = ledger_path + ".part"
                os.makedirs(os.path.dirname(ledger_path), exist_ok=True)
                with open(tmp, "w", encoding="utf-8") as fh:
                    json.dump({"md5": used}, fh, ensure_ascii=False, indent=2)
                os.replace(tmp, ledger_path)
            print(f"  art {sid}: {source} seed {seed0 + bump} md5 {md5[:8]}")
            return cache
    return pick_art(art_dir, sid)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scripts", default=os.path.join(ROOT, "content", "ch2_shorts", "scripts.json"))
    ap.add_argument("--out-dir", default=os.path.join(ROOT, "work", "ch2_shorts"))
    ap.add_argument("--art", help="background image (default: a dark gradient)")
    ap.add_argument("--art-dir", help="directory of stills; one is picked per short")
    ap.add_argument("--art-style", help="generate a unique image per short with this "
                    "gen_cover_image style (dharma|family); preferred over --art-dir")
    ap.add_argument("--art-ledger", help="JSON file recording every generated image's "
                    "md5, so a clip can never reuse another clip's picture")
    ap.add_argument("--music", help="optional bed to mix under the voice")
    ap.add_argument("--cta-mid", action="store_true",
                    help="speak the CTA after the story's peak instead of at the tail "
                         "(ch4 experiment: a tail CTA lands after the viewer swiped)")
    ap.add_argument("--voice", default=None,
                    help=f"edge-tts voice (default {VOICE})")
    ap.add_argument("--probe", action="store_true",
                    help=f"build the changed clip a withheld channel comes back with: "
                         f"use {VOICE_ALT} instead of {VOICE}, so the recovery is audible")
    ap.add_argument("--index", action="append", help="build only these ids")
    args = ap.parse_args()
    if args.probe and not args.voice:
        args.voice = VOICE_ALT

    with open(args.scripts, encoding="utf-8") as fh:
        scripts = json.load(fh)
    if args.index:
        scripts = [s for s in scripts if s["id"] in args.index]
    os.makedirs(args.out_dir, exist_ok=True)
    for s in scripts:
        if args.art:
            art = args.art
        elif args.art_style:
            art = unique_art(os.path.join(args.out_dir, s["id"]), s["id"], s.get("hook", ""),
                             args.art_style, args.art_dir, args.art_ledger)
        else:
            art = pick_art(args.art_dir, s["id"])
        build(s, args.out_dir, art, args.music, cta_mid=args.cta_mid, voice=args.voice)
    print(f"built {len(scripts)} short(s) in {args.out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
