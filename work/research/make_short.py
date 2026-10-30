#!/usr/bin/env python3
"""Cut a vertical Short from a finished episode — the discovery funnel.

The strategy (COMPETITOR-STRATEGY.md §5.3) is long-form + Shorts: the long clip
is the product, the Short is the pipe that brings strangers to it. This cuts a
15-45 s vertical clip on narration-line boundaries and burns a Thai caption, so
the hook reads even with the sound off.

    python3 work/research/make_short.py episodes/ep02_manthana_phatha \
        --lines 0:3 --out site/media/ep02_short_hook.mp4 --hook "คืนนี้จะเล่าเรื่องหนึ่ง"

The clip is taken from `video.mp4` in the episode directory (build it with
`scripts/make_video.py` first). Output is 1080x1920, yuv420p, tv range — the same
colour contract as the long-form video.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
FONT = os.path.join(ROOT, "assets", "fonts", "Prompt-Bold.ttf")
FONT_SMALL = os.path.join(ROOT, "assets", "fonts", "Kanit-Regular.ttf")

MIN_SEC, MAX_SEC = 10.0, 59.0


def line_span(timing: dict, a: int, b: int) -> tuple[float, float, str]:
    lines = timing["lines"]
    if not (0 <= a <= b < len(lines)):
        sys.exit(f"line range {a}:{b} out of bounds (0..{len(lines) - 1})")
    start = float(lines[a]["start"])
    # end = start of the line after the last, or +4 s if it is the final line.
    if b + 1 < len(lines):
        end = float(lines[b + 1]["start"])
    else:
        end = start + 4.0
    text = " ".join(lines[i]["text"] for i in range(a, b + 1))
    return start, end, text


def wrap_thai(text: str, per_line: int = 26) -> str:
    words = text.split()
    out, cur = [], ""
    for w in words:
        if len(cur) + len(w) + 1 > per_line and cur:
            out.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        out.append(cur)
    return "\n".join(out)


def build(ep_dir: str, a: int, b: int, out: str, hook: str | None) -> str:
    timing = json.load(open(os.path.join(ep_dir, "timing.json"), encoding="utf-8"))
    meta = {}
    mp = os.path.join(ep_dir, "meta.json")
    if os.path.exists(mp):
        meta = json.load(open(mp, encoding="utf-8"))
    src = os.path.join(ep_dir, "video.mp4")
    if not os.path.exists(src):
        sys.exit(f"no video.mp4 in {ep_dir} — run scripts/make_video.py first")

    start, end, text = line_span(timing, a, b)
    dur = end - start
    if not (MIN_SEC <= dur <= MAX_SEC):
        sys.exit(f"clip is {dur:.1f}s; Shorts must be {MIN_SEC:.0f}-{MAX_SEC:.0f}s "
                 f"(widen or narrow --lines)")

    caption = wrap_thai(hook or text)
    title = meta.get("title", "")

    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False,
                                     encoding="utf-8") as fh:
        fh.write(caption)
        cap_path = fh.name
    title_path = None
    if title:
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False,
                                         encoding="utf-8") as fh:
            fh.write(title)
            title_path = fh.name

    vf = (
        "[0:v]split=2[bg][fg];"
        "[bg]scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,gblur=sigma=30,eq=brightness=-0.14:saturation=1.1[bgb];"
        "[fg]scale=1080:-2[fgs];"
        "[bgb][fgs]overlay=(W-w)/2:(H-h)/2[comp];"
        f"[comp]drawtext=fontfile={FONT}:textfile={cap_path}:"
        "fontcolor=white:fontsize=58:line_spacing=16:borderw=3:bordercolor=black@0.85:"
        "box=1:boxcolor=black@0.42:boxborderw=30:"
        "x=(w-text_w)/2:y=h*0.58[v1]"
    )
    if title_path:
        vf += (
            f";[v1]drawtext=fontfile={FONT_SMALL}:textfile={title_path}:"
            "fontcolor=white@0.72:fontsize=34:borderw=2:bordercolor=black@0.7:"
            "x=(w-text_w)/2:y=h*0.08[vout]"
        )
    else:
        vf += ";[v1]null[vout]"

    cmd = [
        "ffmpeg", "-hide_banner", "-y",
        "-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", src,
        "-filter_complex", vf, "-map", "[vout]", "-map", "0:a:0",
        "-c:v", "libx264", "-preset", "medium", "-crf", "21",
        # -color_range alone leaves color_range=unknown in the stream; the
        # colorspace tags are what actually make ffprobe report tv.
        "-pix_fmt", "yuv420p", "-color_range", "tv",
        "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
        "-r", "30", "-c:a", "aac", "-b:a", "160k",
        "-movflags", "+faststart", "-shortest", out,
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
    finally:
        os.unlink(cap_path)
        if title_path:
            os.unlink(title_path)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("episode")
    ap.add_argument("--lines", required=True, help="start:end narration lines, e.g. 0:3")
    ap.add_argument("--out", required=True)
    ap.add_argument("--hook", default=None, help="caption override (default: the lines)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    a, b = (int(x) for x in args.lines.split(":"))
    timing = json.load(open(os.path.join(args.episode, "timing.json"), encoding="utf-8"))
    start, end, text = line_span(timing, a, b)
    print(f"lines {a}:{b}  {start:.1f}s -> {end:.1f}s  ({end - start:.1f}s)")
    print(f"caption: {text[:90]}")
    if args.dry_run:
        return 0
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    build(args.episode, a, b, args.out, args.hook)
    size = os.path.getsize(args.out)
    print(f"wrote {args.out}  ({size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
