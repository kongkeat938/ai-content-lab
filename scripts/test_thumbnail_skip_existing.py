#!/usr/bin/env python3
"""A truthy maxres URL is not proof a custom thumbnail is set.

Measured 2026-11-18: video DHs1j6o0JE0 served a `maxresdefault.jpg` URL whose
content was the auto frame, not the file we meant to install (correlation with
our file +0.43). `set_thumbnails.py --skip-existing` tested only `if url:` and
so skipped that video forever -- a video with no custom thumbnail, silently
counted as done.

This guard runs the REAL comparison (`_same_as`) on REAL images: our file vs a
re-encoded copy must match, our file vs a different image must not. Mutate the
threshold or the comparison and it fails.

    python3 scripts/test_thumbnail_skip_existing.py    # exit 0 = compare is honest
"""
from __future__ import annotations

import io
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import set_thumbnails as st  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

fails = 0


def check(name: str, ok: bool) -> None:
    global fails
    print(f"  {'ok  ' if ok else 'FAIL'} {name}")
    if not ok:
        fails += 1


def our_card() -> Image.Image:
    img = Image.new("RGB", (1280, 720), (30, 40, 90))
    d = ImageDraw.Draw(img)
    d.rectangle([80, 80, 1200, 640], fill=(230, 180, 40))
    d.ellipse([400, 200, 880, 520], fill=(20, 20, 20))
    return img


def another_frame() -> Image.Image:
    # A different picture, the stand-in for YouTube's auto frame.
    img = Image.new("RGB", (1280, 720), (10, 120, 60))
    d = ImageDraw.Draw(img)
    for i in range(0, 1280, 64):
        d.line([(i, 0), (i, 720)], fill=(255, 255, 255), width=3)
    return img


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="thumbguard-")
    local = os.path.join(tmp, "ours.jpg")
    our_card().save(local, quality=92)

    # YouTube re-encodes; a lossy copy of our file must still read as ours.
    buf = io.BytesIO()
    our_card().save(buf, format="JPEG", quality=70)
    buf.seek(0)
    reencoded = Image.open(buf).convert("RGB")
    check("a re-encoded copy of our file matches", st._same_as(reencoded, local) is True)

    # The auto frame (a different image) must NOT match.
    check("a different frame does NOT match", st._same_as(another_frame(), local) is False)

    # A missing local file is never a match (an unknown is not 'done').
    check("a missing local file is not a match",
          st._same_as(our_card(), os.path.join(tmp, "nope.jpg")) is False)

    print(f"\n{'all checks passed' if not fails else f'{fails} check(s) FAILED'}")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
