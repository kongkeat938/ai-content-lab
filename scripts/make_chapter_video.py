#!/usr/bin/env python3
"""Turn a long narration track into a video that changes picture per chapter.

The advisor panel (2026-11-07, four camps: gemini-3.5-flash-lite, gemini-3.6-flash,
gemma-4-31b-it, gpt-oss-20b) agreed on the cause of the channel's 5.2% AVD on a
120-minute file: one static card looped for two hours is "visual boredom" and reads
to YouTube as low-effort, reused content. Their ordered fix was a real opening hook,
a shorter file (20-30 min), and a picture that changes as the narration moves from
beat to beat -- not a 24-second loop repeated for hours.

This is the picture half of that fix. Given the per-piece durations that
`make_compilation.py` already records, it renders ONE card per piece, each with a
slow Ken Burns drift and the chapter's own label, and concatenates them so the
screen changes every few minutes while the audio never stops. The loop of the last
card bounds nothing; the track's own length does.

Usage:
    python3 scripts/make_chapter_video.py --audio compilation.mp3 \
        --info compilation.mp3.info.json --images art_dir \
        --out video.mp4 --title "ปรัชญาชีวิต"

`--images` holds one source image per piece, named `NN_<piece>.jpg` to match the
`NN_<piece>.txt` the compilation was built from; a missing one falls back to the
first image so a build never fails for want of art.
"""
from __future__ import annotations

import argparse
import hashlib
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
TP_CEILING = -3.0
TP_MARGIN = 0.1
TP_TRIES = 3
# How long the first card holds before the drift visibly starts, and how long a
# crossfade runs between cards. A hard cut reads as a glitch to a listener who is
# half-watching; a 1.5 s dissolve reads as a scene change.
XFADE = 1.5
# Cap on the number of cards in one xfade chain. A 120-minute sleep file would need
# ~130 one-per-piece cards; grouping them keeps a picture change every few minutes
# (the panel's guidance) without an unbounded filter chain on CI.
MAX_CARDS = 30


def run(cmd: list) -> None:
    subprocess.run(cmd, check=True, capture_output=True)


def duration(path: str) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", path], capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def true_peak(path: str) -> float:
    """Measure the true peak of the finished file, in dBFS.

    Read from the *finished* file, not the intermediate: AAC overshoots the mp3 it
    was encoded from, so the mp3's own measurement does not describe what ships.
    """
    out = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", path,
         "-map", "0:a:0", "-af", "ebur128=peak=true", "-f", "null", "-"],
        capture_output=True, text=True).stderr
    tail = out.split("Summary:")[-1]
    m = re.search(r"Peak:\s*(-?\d+\.\d+)\s*dBFS", tail)
    return float(m.group(1)) if m else float("nan")


def piece_boundaries(info: dict) -> list[tuple[str, float]]:
    """(piece name, seconds) for every repetition, in playback order.

    `make_compilation` records each piece's duration once and a cycle count; the
    sequence is each cycle rotated by its index (see sequence_to_length), so this
    reproduces that order to know where each card starts and ends.
    """
    pieces = info.get("pieces") or []
    if not pieces:
        return []
    hook = info.get("hook")
    out: list[tuple[str, float]] = []
    if hook and float(hook.get("duration_sec") or 0.0) > 0:
        out.append((hook.get("name") or "00_hook", float(hook["duration_sec"])))
    cycles = int(info.get("cycles") or 1)
    n = len(pieces)
    for c in range(cycles):
        r = c % n
        for p in pieces[r:] + pieces[:r]:
            out.append((p["name"], float(p.get("duration_sec") or 0.0)))
    return out


def coalesce(segs: list[tuple[str, float]], max_cards: int) -> list[tuple[str, float]]:
    """Merge consecutive pieces until there are at most `max_cards` of them.

    A 120-minute file built one-card-per-piece would need ~130 cards, and a single
    xfade chain that long is both slow and memory-heavy on CI. The panel's guidance
    was a picture change every 3-5 minutes, so grouping pieces up to a card ceiling
    is the intended shape for a long sleep file, not a compromise. A short file
    stays one card per piece because it never reaches the ceiling.
    """
    if max_cards <= 0 or len(segs) <= max_cards:
        return segs
    group = (len(segs) + max_cards - 1) // max_cards
    out: list[tuple[str, float]] = []
    for i in range(0, len(segs), group):
        chunk = segs[i:i + group]
        out.append((chunk[0][0], sum(d for _, d in chunk)))
    return out


def label_for(name: str) -> str:
    """A human chapter label from a piece name: `03_others` -> `03 others`."""
    base = os.path.splitext(os.path.basename(name))[0]
    return re.sub(r"[_]+", " ", base).strip()


def find_image(images: str, name: str, fallback: str) -> str:
    stem = os.path.splitext(os.path.basename(name))[0]
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        p = os.path.join(images, stem + ext)
        if os.path.exists(p):
            return p
    return fallback


def ensure_image(images: str, name: str, style: str, prompt: str) -> str:
    """The image for a piece, generated on the spot if the caller supplied none.

    `build_night --chapters` pre-generates one image per piece, but the renderer
    must also work standalone -- so a missing file is generated here rather than
    failing the build for want of art.
    """
    stem = os.path.splitext(os.path.basename(name))[0]
    dst = os.path.join(images, stem + ".jpg")
    if os.path.exists(dst):
        return dst
    os.makedirs(images, exist_ok=True)
    seed = int(hashlib.sha256(stem.encode()).hexdigest()[:8], 16)
    subprocess.run([sys.executable, os.path.join(HERE, "gen_cover_image.py"),
                    "--out", dst, "--style", style, "--seed", str(seed),
                    "--prompt", prompt], check=True, capture_output=True)
    return dst


def build(audio: str, info: dict, images: str, out: str, title: str,
          subtitle: str = "", fade: float = XFADE, style: str = "dharma",
          prompt: str = "", max_cards: int = MAX_CARDS) -> dict:
    segs = coalesce(piece_boundaries(info), max_cards)
    if not segs:
        raise SystemExit("info has no pieces; cannot lay out chapters")
    tmp = tempfile.mkdtemp(prefix="chapvid_")
    try:
        first = ensure_image(images, segs[0][0], style, prompt)
        cover = os.path.join(tmp, "cover.jpg")
        make_poster.build(first, cover, title, subtitle, 3)

        # One Ken Burns clip per piece, sized to that piece's own duration plus a
        # little room so the xfade overlap does not shorten the whole timeline.
        clips: list[str] = []
        for i, (name, dur) in enumerate(segs):
            src = ensure_image(images, name, style, prompt)
            card = os.path.join(tmp, f"card_{i:03d}.jpg")
            make_poster.build(src, card, title, subtitle, i, chapter=label_for(name),
                              index=f"{i + 1:02d}")
            clip = os.path.join(tmp, f"clip_{i:03d}.mp4")
            clip_len = max(2.0, dur + (fade if i < len(segs) - 1 else 0.0))
            frames = int(clip_len * FPS)
            # Alternate the push direction so consecutive cards do not drift the
            # same way, which is what made the old single-card loop feel static.
            if i % 2 == 0:
                z = f"1.0+0.06*on/{frames}"
            else:
                z = f"1.06-0.06*on/{frames}"
            zoom = (f"scale={int(W * 1.10)}:{int(H * 1.10)},"
                    f"zoompan=z='{z}':d=1:"
                    f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
                    f"s={W}x{H}:fps={FPS}")
            run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-i", card,
                 "-vf", f"fps={FPS},{zoom},format=yuv420p",
                 "-t", f"{clip_len:.3f}", "-r", str(FPS),
                 "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
                 "-color_range", "tv", "-colorspace", "bt709",
                 "-color_primaries", "bt709", "-color_trc", "bt709",
                 "-pix_fmt", "yuv420p", clip])
            clips.append(clip)

        # xfade chains the cards; the audio is muxed in a second pass so a long
        # chain never re-encodes the narration.
        pic = os.path.join(tmp, "picture.mp4")
        if len(clips) == 1:
            run(["ffmpeg", "-y", "-loglevel", "error", "-i", clips[0],
                 "-c:v", "copy", "-an", pic])
        else:
            inputs = []
            for c in clips:
                inputs += ["-i", c]
            parts = []
            prev = "[0:v]"
            offset = 0.0
            for i in range(1, len(clips)):
                offset += float(segs[i - 1][1])
                tag = f"[v{i}]"
                parts.append(f"{prev}[{i}:v]xfade=transition=fade:duration={fade}:"
                             f"offset={offset:.3f}{tag}")
                prev = tag
            run(["ffmpeg", "-y", "-loglevel", "error", *inputs,
                 "-filter_complex", ";".join(parts), "-map", prev,
                 "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
                 "-pix_fmt", "yuv420p", pic])

        adur = duration(audio)

        def encode(dst: str, gain_db: float = 0.0) -> None:
            # A clean loop is the strongest watch-time lever measured on these
            # channels: the top clips show averageViewPercentage > 100%. Fading the
            # tail to silence makes end->start seamless for a replay.
            fo = max(0.0, adur - 8.0)
            chain = f"afade=t=in:st=0:d=4,afade=t=out:st={fo:.3f}:d=8"
            af = f"volume={gain_db:.2f}dB,{chain}" if gain_db else chain
            run(["ffmpeg", "-y", "-loglevel", "error", "-i", pic, "-i", audio,
                 "-map", "0:v", "-map", "1:a", "-t", f"{adur:.3f}", "-shortest",
                 "-af", af, "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                 "-movflags", "+faststart", dst])

        ceiling = TP_CEILING - TP_MARGIN
        gain = 0.0
        for _ in range(TP_TRIES):
            encode(out, gain)
            peak = true_peak(out)
            if not (peak > ceiling):
                break
            gain += (ceiling - peak)
            print(f"  true peak {peak:.2f} > {ceiling:.2f} dBFS; "
                  f"re-encoding at {gain:+.2f} dB", file=sys.stderr)

        info_out = {"out": out, "duration_sec": round(duration(out), 2),
                    "video": f"{W}x{H}", "fps": FPS, "chapters": len(segs),
                    "chapter_seconds": [round(d, 2) for _, d in segs],
                    "true_peak_dbfs": peak, "audio_gain_db": round(gain, 2)}
        json.dump(info_out, open(out + ".info.json", "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
        return info_out
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--audio", required=True)
    ap.add_argument("--info", required=True, help="compilation.mp3.info.json")
    ap.add_argument("--images", required=True, help="directory of per-piece images")
    ap.add_argument("--out", required=True)
    ap.add_argument("--title", default="")
    ap.add_argument("--subtitle", default="")
    ap.add_argument("--style", default="dharma", help="house style for missing art")
    ap.add_argument("--prompt", default="", help="subject for missing art (English)")
    ap.add_argument("--max-cards", type=int, default=MAX_CARDS,
                    help="cap on chapter cards (long files group pieces)")
    ap.add_argument("--fade", type=float, default=XFADE)
    a = ap.parse_args()
    info = json.load(open(a.info, encoding="utf-8"))
    print(json.dumps(build(a.audio, info, a.images, a.out, a.title, a.subtitle,
                           a.fade, a.style, a.prompt, a.max_cards), ensure_ascii=False))


if __name__ == "__main__":
    main()
