#!/usr/bin/env python3
"""The minimum standard every Short must meet before it may upload.

Owner K (2026-11-17): the look K approved for the long-form is now the **minimum
bar for every channel**, and a Short's **aspect ratio and thumbnail** must meet
that same bar -- "ถ้าไม่ได้มาตรฐานห้ามอัพเลย ของเก่าที่ค้างอยู่ก็ห้ามอัพ" (if it does
not meet the standard, do not upload it, including the old backlog). So this is
the one place that decides pass/fail, and both the publish rail and the test
guard call it. A build that fails is held, not uploaded.

Every threshold is measured, not assumed:

  * **9:16, 2160x3840 (4K)** -- K's rule, 2026-11-23: 4K only to upload.
  * **yuv420p + range=tv + bt709** -- the long-form standard. Measured 2026-11-17: a
    built Short came out `yuvj420p` / full-range `pc` / `bt470bg` because the JPEG
    backdrop decodes full-range; docs/RECIPE.md warns that plays washed-out. Fixed in
    make_short.py; this guard keeps it from regressing.
  * **-14 LUFS / true peak <= -3 dBFS** -- the house audio target (make_short.py LUFS/TP).
  * **<= 60 s** -- the Shorts length ceiling.
  * **thumbnail 9:16, height >= 640 px, <= 2 MB** -- YouTube's OWN Shorts rule
    (support.google.com/youtube/answer/72431, read 2026-11-17): 9:16 aspect,
    2160x3840 recommended, minimum height 640, JPG/PNG, under the MB limit.

    from short_standard import verify_short
    ok, reasons, metrics = verify_short("short.mp4", "thumb.jpg")
"""
from __future__ import annotations

import json
import os
import subprocess

# Video shape
ASPECT_W, ASPECT_H = 9, 16
# K (2026-11-23): 4K only to upload -- a 1080x1920 Short is now below the bar.
EXPECT_W, EXPECT_H = 2160, 3840
# A delivered-for-a-client Short is not an upload to our channels: 1080x1920 is
# YouTube's delivery size, and the 4K bar is K's rule for OUR channels only. The
# profile is explicit so the default path cannot silently accept 1080p.
PROFILES = {"ours": (2160, 3840), "client": (1080, 1920)}
PIX_FMT = "yuv420p"
COLOR_RANGE = "tv"
COLORSPACE = "bt709"
# Audio (house target)
LOUD_I, LOUD_TOL = -14.0, 1.5
LOUD_TP, TP_TOL = -3.0, 0.5
# Length
MAX_SEC = 60.0
# Thumbnail (YouTube's own Shorts rule)
THUMB_MIN_H = 640
THUMB_MAX_BYTES = 2_000_000
THUMB_FORMATS = ("JPEG", "PNG")


def _probe(path: str) -> dict:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "stream=codec_type,width,height,pix_fmt,color_range,color_space:"
         "format=duration", "-of", "json", path],
        capture_output=True, text=True, stdin=subprocess.DEVNULL)
    return json.loads(r.stdout or "{}")


def _loudness(path: str) -> tuple[float | None, float | None]:
    r = subprocess.run(["ffmpeg", "-i", path, "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True, stdin=subprocess.DEVNULL)
    i = tp = None
    for ln in r.stderr.splitlines():
        s = ln.strip()
        if s.startswith("I:") and "LUFS" in s:
            i = float(s.split()[1])
        elif s.startswith("Peak:") and "dBFS" in s:
            tp = float(s.split()[1])
    return i, tp


def verify_short(video: str, thumb: str | None = None,
                 profile: str = "ours") -> tuple[bool, list[str], dict]:
    """Return (ok, reasons, metrics). ok is False if ANY standard is missed.

    profile="ours" (default) enforces 2160x3840; profile="client" enforces the
    1080x1920 delivery size. Every other check (colour, loudness, length,
    thumbnail) is identical in both profiles.
    """
    if profile not in PROFILES:
        return False, [f"unknown profile {profile!r} (use one of {sorted(PROFILES)})"], {}
    expect_w, expect_h = PROFILES[profile]
    reasons: list[str] = []
    metrics: dict = {"profile": profile}
    if not (video and os.path.exists(video)):
        return False, [f"no video at {video!r}"], metrics

    info = _probe(video)
    streams = info.get("streams", [])
    v = next((s for s in streams if s.get("codec_type") == "video"), None)
    a = next((s for s in streams if s.get("codec_type") == "audio"), None)

    if not v:
        reasons.append("no video stream")
    else:
        w, h = v.get("width"), v.get("height")
        metrics["size"] = f"{w}x{h}"
        if (w, h) != (expect_w, expect_h):
            reasons.append(f"aspect/size {w}x{h} is not {expect_w}x{expect_h} "
                           f"(9:16, profile {profile})")
        else:
            g = __import__("math").gcd(w, h)
            if (w // g, h // g) != (ASPECT_W, ASPECT_H):
                reasons.append(f"aspect {w // g}:{h // g} is not 9:16")
        metrics["pix_fmt"] = v.get("pix_fmt")
        metrics["color_range"] = v.get("color_range")
        metrics["colorspace"] = v.get("color_space")
        if v.get("pix_fmt") != PIX_FMT:
            reasons.append(f"pix_fmt {v.get('pix_fmt')} is not {PIX_FMT} "
                           "(yuvj420p = full-range JPEG, plays washed-out)")
        if v.get("color_range") != COLOR_RANGE:
            reasons.append(f"color_range {v.get('color_range')} is not {COLOR_RANGE}")
        if v.get("color_space") not in (COLORSPACE, "unknown", None):
            reasons.append(f"colorspace {v.get('color_space')} is not {COLORSPACE}")

    if not a:
        reasons.append("no audio stream")
    else:
        i, tp = _loudness(video)
        metrics["lufs"], metrics["true_peak"] = i, tp
        if i is not None and not (LOUD_I - LOUD_TOL <= i <= LOUD_I + LOUD_TOL):
            reasons.append(f"loudness {i:.1f} LUFS is off the {LOUD_I} target")
        if tp is not None and tp > LOUD_TP + TP_TOL:
            reasons.append(f"true peak {tp:.1f} dBFS exceeds {LOUD_TP}")

    dur = float(info.get("format", {}).get("duration") or 0.0)
    metrics["duration_sec"] = round(dur, 2)
    if dur and dur > MAX_SEC:
        reasons.append(f"duration {dur:.1f}s is over the {MAX_SEC:.0f}s Shorts ceiling")

    # Thumbnail: a Short without a standards-compliant thumbnail is not publishable.
    if not thumb:
        reasons.append("no thumbnail (the Shorts manifest has none; build one with "
                       "make_short_thumbnail.py)")
    elif not os.path.exists(thumb):
        reasons.append(f"thumbnail missing at {thumb!r}")
    else:
        from PIL import Image
        im = Image.open(thumb)
        metrics["thumb_size"] = f"{im.width}x{im.height}"
        metrics["thumb_bytes"] = os.path.getsize(thumb)
        if im.height < THUMB_MIN_H:
            reasons.append(f"thumbnail height {im.height} < {THUMB_MIN_H} (YouTube minimum)")
        g = __import__("math").gcd(im.width, im.height)
        if (im.width // g, im.height // g) != (ASPECT_W, ASPECT_H):
            reasons.append(f"thumbnail aspect {im.width // g}:{im.height // g} is not 9:16")
        if im.format not in THUMB_FORMATS:
            reasons.append(f"thumbnail format {im.format} is not JPG/PNG")
        if os.path.getsize(thumb) > THUMB_MAX_BYTES:
            reasons.append(f"thumbnail {os.path.getsize(thumb)//1024} KB over the "
                           f"{THUMB_MAX_BYTES//1_000_000} MB mobile limit")

    return (not reasons), reasons, metrics


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--thumb")
    a = ap.parse_args()
    ok, reasons, m = verify_short(a.video, a.thumb)
    print(f"{a.video}: {'PASS' if ok else 'FAIL'}")
    print(json.dumps(m, ensure_ascii=False))
    for r in reasons:
        print(f"  - {r}")
    raise SystemExit(0 if ok else 1)
