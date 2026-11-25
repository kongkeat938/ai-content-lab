#!/usr/bin/env python3
"""Guard the Shorts minimum standard -- aspect + colour range + thumbnail.

Owner K (2026-11-17): a Short's aspect ratio and thumbnail must meet the same
standard as the long-form, and a Short that does not meet it must NOT upload
(including the old backlog). This locks the two things that can silently break:

  1. **The standard itself** (`short_standard.verify_short`): a good 2160x3840
     yuv420p/tv/bt709 clip with a 9:16 thumbnail passes; each defect fails
     (wrong size, full-range yuvj420p, a 16:9 thumbnail, an undersized thumbnail,
     a missing thumbnail). Every case is a REAL ffmpeg/PIL artifact, not a mock.
  2. **The wiring**: publish_shorts.py must build the thumbnail and call the
     standard BEFORE `videos().insert`, and must `continue` (hold) on a failure.
     A guard that only checked the standard but not the wiring would pass while the
     rail still uploaded garbage.

    python3 scripts/test_short_standard.py    # exit 0 = the standard holds
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import short_standard  # noqa: E402


def sh(cmd: list[str]) -> None:
    r = subprocess.run(cmd, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    if r.returncode != 0:
        raise SystemExit("cmd failed: " + " ".join(cmd) + "\n" + r.stderr[-1500:])


def make_video(path: str, *, pix_fmt: str, color_range: str, dur: int = 4,
               size: str = "2160x3840") -> None:
    sh(["ffmpeg", "-y", "-loglevel", "error",
        "-f", "lavfi", "-i", f"testsrc2=size={size}:rate=30:duration={dur}",
        "-f", "lavfi", "-i", f"sine=frequency=300:duration={dur}",
        "-af", "loudnorm=I=-14:TP=-3", "-ar", "48000",
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", pix_fmt,
        "-color_range", color_range, "-colorspace", "bt709",
        "-color_primaries", "bt709", "-color_trc", "bt709",
        "-c:a", "aac", "-shortest", path])


def make_thumb(path: str, w: int, h: int) -> None:
    from PIL import Image
    Image.new("RGB", (w, h), (40, 80, 140)).save(path, quality=90)


def expect(ok: bool, reasons: list[str], want_ok: bool, needle: str) -> bool:
    if ok != want_ok:
        print(f"  FAIL: expected ok={want_ok}, got {ok}; reasons={reasons}")
        return False
    if needle and not any(needle in r for r in reasons):
        print(f"  FAIL: no reason mentioning {needle!r}; reasons={reasons}")
        return False
    return True


def main() -> int:
    d = tempfile.mkdtemp(prefix="shortstd_")
    good = os.path.join(d, "good.mp4")
    full = os.path.join(d, "full.mp4")
    wide = os.path.join(d, "wide.mp4")
    hd = os.path.join(d, "hd.mp4")
    thumb = os.path.join(d, "thumb.jpg")
    wide_thumb = os.path.join(d, "wide_thumb.jpg")
    small_thumb = os.path.join(d, "small_thumb.jpg")

    make_video(good, pix_fmt="yuv420p", color_range="tv")
    make_video(full, pix_fmt="yuvj420p", color_range="pc")
    # Same encode at YouTube's delivery size: below OUR bar, valid for a client.
    make_video(hd, pix_fmt="yuv420p", color_range="tv", size="1080x1920")
    # 1280x720 is a valid encode but the wrong shape for a Short.
    sh(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
        "-i", "testsrc2=size=1280x720:rate=30:duration=3",
        "-f", "lavfi", "-i", "sine=frequency=300:duration=3",
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        "-color_range", "tv", "-c:a", "aac", "-shortest", wide])
    make_thumb(thumb, 1080, 1920)
    make_thumb(wide_thumb, 1280, 720)
    make_thumb(small_thumb, 320, 568)   # 9:16 but height 568 < 640

    ok = True
    fails = 0

    def check(label: str, got, want_ok: bool, needle: str):
        nonlocal ok, fails
        o, reasons = got
        if not expect(o, reasons, want_ok, needle):
            fails += 1
            ok = False
        else:
            print(f"  ok: {label}")

    check("good clip + good thumb", short_standard.verify_short(good, thumb)[:2], True, "")
    check("full-range yuvj420p", short_standard.verify_short(full, thumb)[:2], False, "pix_fmt")
    check("16:9 clip", short_standard.verify_short(wide, thumb)[:2], False, "9:16")
    check("16:9 thumbnail", short_standard.verify_short(good, wide_thumb)[:2], False, "thumbnail aspect")
    check("undersized thumbnail", short_standard.verify_short(good, small_thumb)[:2], False, "height")
    check("no thumbnail", short_standard.verify_short(good, None)[:2], False, "no thumbnail")
    # The 4K rule must still bite by default; only the client profile may take 1080p.
    check("1080p clip, default profile", short_standard.verify_short(hd, thumb)[:2], False, "2160x3840")
    check("1080p clip, client profile",
          short_standard.verify_short(hd, thumb, profile="client")[:2], True, "")

    # Wiring: the rail must gate before upload and hold on failure.
    src = open(os.path.join(HERE, "publish_shorts.py"), encoding="utf-8").read()
    if "short_standard.verify_short" not in src:
        print("  FAIL: publish_shorts.py does not call short_standard.verify_short")
        ok = False
    else:
        print("  ok: publish_shorts.py calls the standard")
    gate = src.find("short_standard.verify_short")
    insert = src.find("videos().insert")
    if not (0 <= gate < insert):
        print("  FAIL: the standard is checked AFTER videos().insert")
        ok = False
    else:
        print("  ok: the standard is checked before upload")
    if "HELD -- below the minimum standard" not in src:
        print("  FAIL: no hold path when the standard is missed")
        ok = False
    else:
        print("  ok: a failed Short is held, not uploaded")

    print(f"\n{'PASS' if ok else f'FAIL ({fails} case(s))'} -- short standard")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
