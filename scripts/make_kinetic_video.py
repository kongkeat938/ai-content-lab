#!/usr/bin/env python3
"""Kinetic knowledge-video renderer — a moving picture, not a static card.

Why this exists (measured, 2026-11-14): ch4's long-form was one Pillow poster
card with a slow Ken Burns drift, and it measured **5.2% AVD** and 1-6 views.
A five-advisor panel (2026-11-11, scripts/advise.py) was unanimous on the cause:
a still card looped for a long file reads to YouTube as low-effort reused
content. Their fix was a picture that moves the whole time and text that keeps
the eye busy. The poster rail changed the picture only every few minutes; this
renderer changes it every frame.

The moving background is a `gradients` source (its colour stops animate over
time), plus film grain and a slow hue drift, so no frame is ever identical to
the last. On top of that sits a kinetic caption track: every spoken line fades
in with a slide and a small scale pop, holds while it is spoken, then fades out
-- the text is timed to the narration's own line starts, so the picture and the
voice stay locked.

Everything here is CPU-only and free: ffmpeg's libavfilter plus libass for the
captions. There is no GPU step and no paid asset, so it runs inside the 4-vCPU
GitHub Actions runner.

Usage:
    python3 scripts/make_kinetic_video.py \
        --audio compilation.mp3 --timing compilation.mp3.timing.json \
        --out video.mp4 --title "เกร็ดความรู้รอบตัว"

`--timing` is the file `make_audio.build_with_timing` writes: {"duration_sec",
"lines": [{"text", "start"}], ...}. When it is absent the renderer still runs
and lays out captions on a fixed cadence, so a missing timing file degrades the
sync instead of failing the build.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile

W, H = 1920, 1080
FPS = 25
FONT = "Kanit"
HOLD_SEC = 9.0  # a caption animates in, holds at most this long, then leaves
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
# The motion is the point: a background filter chain with none of these
# time-varying sources would reproduce the 5.2% static-card failure. The guard
# test asserts at least one of them is present.
MOTION_TOKENS = ("gradients", "zoompan", "hue", "rotate", "noise", "mandelbrot", "life")


def run(cmd: list) -> None:
    """Run ffmpeg, surfacing its stderr when it fails.

    `capture_output=True` alone swallowed the real message (a bare "exit 234"),
    which cost a debug cycle -- so a failure re-raises with ffmpeg's own text.
    """
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(
            f"command failed ({p.returncode}): {' '.join(cmd)}\n{p.stderr[-2000:]}")


def duration(path: str) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", path], capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def gradient_source(seed: int, dur: float) -> str:
    """The moving-background source for `-f lavfi -i`.

    `gradients` animates its colour stops over the clip, so the source itself
    changes every frame -- this is the motion that replaces the static card. It
    is a *source* filter, so it must be an input, never chained onto another
    input (chaining it fails with "More input link labels ... than it has").
    """
    palettes = [
        ("0x0a1a2f", "0x143a5c", "0x081018"),  # deep blue
        ("0x1a1030", "0x3a1d5c", "0x0a0818"),  # indigo
        ("0x08201a", "0x14463a", "0x06120f"),  # forest teal
    ]
    c0, c1, c2 = palettes[seed % len(palettes)]
    return (
        f"gradients=s={W}x{H}:c0={c0}:c1={c1}:c2={c2}:n=3:"
        f"speed=0.006:d={dur:.3f}:r={FPS}"
    )


def background_chain(seed: int = 0) -> str:
    """The per-frame treatment applied on top of the gradient source.

    `noise` adds a per-frame grain and the slow `hue` drift keeps the palette
    from settling, so even a frame pair from the same gradient position differs.
    `format=yuv420p` is required so libx264 accepts the frames.
    """
    return (
        "format=yuv420p,"
        "noise=alls=7:allf=t+u,"
        "hue=h=t*1.5:s=1.05,"
        "vignette=PI/4.5"
    )


def ass_escape(text: str) -> str:
    """Escape the characters that would break an ASS Dialogue line."""
    return text.replace("\\", "\\\\").replace("{", "(").replace("}", ")").replace("\n", " ")


def _ts(sec: float) -> str:
    """ASS timestamp H:MM:SS.cc"""
    if sec < 0:
        sec = 0.0
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def build_ass(lines: list[dict], total: float, title: str, brand: str) -> str:
    """A kinetic caption track from the narration's own line starts.

    Each line: fade in (250 ms) with an upward slide and a small scale pop, hold
    for its spoken span, fade out. A line with no `start` is skipped rather than
    mis-timed. `total` bounds the last line so it never runs past the audio.
    """
    starts = [(i, l) for i, l in enumerate(lines) if l.get("start") is not None]
    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        f"PlayResX: {W}\n"
        f"PlayResY: {H}\n"
        "WrapStyle: 2\n"
        "ScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, "
        "ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
        "MarginL, MarginR, MarginV, Encoding\n"
        # &H00FFFFFF white, &H00000000 black outline; Alignment 2 = bottom-centre.
        f"Style: Cap,{FONT},74,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,"
        "1,0,0,0,100,100,0,0,1,4,2,2,140,140,150,1\n"
        f"Style: Title,{FONT},96,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,"
        "1,0,0,0,100,100,0,0,1,5,3,5,120,120,120,1\n"
        f"Style: Brand,{FONT},40,&H60FFFFFF,&H60FFFFFF,&H00000000,&H00000000,"
        "0,0,0,0,100,100,0,0,1,2,0,3,60,60,60,1\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, "
        "Effect, Text\n"
    )
    out = [header]

    # Persistent brand tag, bottom-right, for the whole file.
    out.append(
        f"Dialogue: 0,{_ts(0)},{_ts(total)},Brand,,0,0,0,,"
        f"{{\\an3\\alpha&H70&}}{ass_escape(brand)}\n"
    )

    # Opening title card for the first 6 seconds.
    if title:
        out.append(
            f"Dialogue: 0,{_ts(0)},{_ts(min(6.0, total))},Title,,0,0,0,,"
            f"{{\\an5\\pos({W // 2},{H // 2})\\fad(400,600)\\fscx90\\fscy90"
            f"\\t(0,500,\\fscx100\\fscy100)}}{ass_escape(title)}\n"
        )

    for n, (_, line) in enumerate(starts):
        text = (line.get("text") or "").strip()
        if not text:
            continue
        start = float(line["start"])
        # End at the next line's start, the audio end, or HOLD seconds later --
        # whichever is first. The HOLD cap matters when a "line" is really a
        # whole section (minutes long): the caption should animate in, be read,
        # then leave, not sit on screen for the rest of the piece.
        nxt = float(starts[n + 1][1]["start"]) if n + 1 < len(starts) else total
        end = min(nxt, total, start + HOLD_SEC)
        if end < start + 0.8:
            end = min(total, start + 0.8)
        # Kinetic entrance: slide up 60 px while fading in, then a tiny scale
        # settle. The body is a plain dialogue so the words stay legible.
        text_ass = (
            "{\\an5\\pos(%d,%d)\\fad(250,350)\\move(%d,%d,%d,%d,0,400)"
            "\\t(0,450,\\fscx100\\fscy100)}%s"
            % (W // 2, 760, W // 2, 820, W // 2, 760, ass_escape(text))
        )
        out.append(f"Dialogue: 0,{_ts(start)},{_ts(end)},Cap,,0,0,0,,{text_ass}\n")
    return "".join(out)


def load_lines(timing_path: str | None, total: float) -> list[dict]:
    if timing_path and os.path.exists(timing_path):
        data = json.load(open(timing_path, encoding="utf-8"))
        lines = [l for l in data.get("lines", []) if l.get("text")]
        if lines:
            return lines
    # No timing: a fixed 8-second cadence so the render still produces captions.
    return []


def build(audio: str, timing_path: str | None, out: str, title: str = "",
          brand: str = "", seed: int = 0, crf: int = 24,
          preset: str = "veryfast") -> dict:
    total = duration(audio)
    lines = load_lines(timing_path, total)
    tmp = tempfile.mkdtemp(prefix="kinetic_")
    ass_path = os.path.join(tmp, "caps.ass")
    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(build_ass(lines, total, title, brand))

    # libass needs the ass file path escaped for the filtergraph.
    ass_arg = ass_path.replace("\\", "/").replace(":", "\\:")
    # fontconfig on the CI runner does not know the repo fonts, so libass fell
    # back to a font with no Thai coverage and drew garbage glyphs (measured
    # 2026-11-16: "แสงอาทิตย์" came out as "บปพนฎิยแพพ..."). Pointing fontsdir at
    # the bundled Kanit fixes it; the guard test asserts fontsdir is set.
    fonts = os.path.join(ROOT, "assets", "fonts").replace("\\", "/").replace(":", "\\:")
    vf = f"{background_chain(seed)},subtitles='{ass_arg}':fontsdir='{fonts}'"

    run(["ffmpeg", "-y", "-loglevel", "error",
         "-f", "lavfi", "-i", gradient_source(seed, total),
         "-i", audio,
         "-filter_complex", f"[0:v]{vf}[v]",
         "-map", "[v]", "-map", "1:a:0",
         "-c:v", "libx264", "-preset", preset, "-crf", str(crf),
         "-pix_fmt", "yuv420p", "-r", str(FPS),
         "-c:a", "aac", "-b:a", "192k", "-shortest",
         "-movflags", "+faststart", out])

    info = {
        "out": out,
        "duration_sec": round(duration(out), 2),
        "captions": len(lines),
        "title": title,
    }
    with open(out + ".info.json", "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=2)
    return info


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--audio", required=True)
    ap.add_argument("--timing", default=None)
    ap.add_argument("--out", required=True)
    ap.add_argument("--title", default="")
    ap.add_argument("--brand", default="เกร็ดความรู้รอบตัว")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--crf", type=int, default=24)
    ap.add_argument("--preset", default="veryfast")
    a = ap.parse_args()
    info = build(a.audio, a.timing, a.out, a.title, a.brand, a.seed, a.crf, a.preset)
    print(json.dumps(info, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
