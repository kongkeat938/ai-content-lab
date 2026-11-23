#!/usr/bin/env python3
"""May this clip be uploaded? K's three rules, in one place.

K (2026-11-23): "ต้อง 4k เท่านั้นถึงอัพขึ้นได้ ห้ามซ้ำ ทั้งภาพ ดนตรี บท" --
4K only, and nothing repeated: not the pictures, not the music, not the script.

So this is the gate an upload has to pass, and every reason it can say no is
measurable on the files themselves:

  * **4K only** -- long-form 3840x2160, a Short 2160x3840. A 1080p file is not
    "almost 4K", it is refused.
  * **no repeated picture** -- the md5 of every scene is checked against the
    channel's art ledger; a frame that already carried another video is refused.
  * **no repeated music** -- the bed is checked against the bed ledger; a track
    that already plays under another video id is refused (a re-render of the
    same id may keep its own bed).
  * **no repeated script** -- the narration is compared with every published
    script by character n-grams (Thai has no spaces, so words would fail): a
    script that is half the same as one already out is refused.

    python3 scripts/upload_gate.py --kind short --video out.mp4 --sid 191 \\
        --art-ledger content/art_ledger_dharma.json --bed-ledger content/bed_ledger_dharma.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys

# K's bar, per orientation. A file must MEET it; there is no tolerance band.
FOUR_K = {"long": (3840, 2160), "short": (2160, 3840)}
DUP_THRESHOLD = 0.45          # share of 4-gram overlap that counts as the same script


def probe(path: str) -> tuple[int, int, str | None]:
    """Width, height and pix_fmt of the first video stream (0,0,None if unknown)."""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
             "stream=width,height,pix_fmt", "-of", "json", path],
            capture_output=True, text=True, stdin=subprocess.DEVNULL, check=True).stdout
        s = (json.loads(out).get("streams") or [{}])[0]
        return int(s.get("width") or 0), int(s.get("height") or 0), s.get("pix_fmt")
    except (OSError, subprocess.CalledProcessError, ValueError):
        return 0, 0, None


def resolution_problems(path: str, kind: str) -> list[str]:
    want_w, want_h = FOUR_K[kind]
    w, h, _ = probe(path)
    if not w or not h:
        return [f"cannot read a video stream from {os.path.basename(path)}"]
    if w < want_w or h < want_h:
        return [f"{w}x{h} is not 4K for a {kind} (needs {want_w}x{want_h})"]
    return []


def md5_of(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def image_problems(md5s: list[str], ledger: dict, sid: str | None = None) -> list[str]:
    """A picture that already carried another video is a repeat."""
    used = ledger.get("md5", {}) if isinstance(ledger, dict) else {}
    out = []
    for m in md5s:
        owner = used.get(m)
        if owner and str(owner) != str(sid):
            out.append(f"picture {m[:8]} already used by {owner}")
    return out


def music_problems(bed: str | None, ledger: dict, sid: str | None = None) -> list[str]:
    used = ledger.get("beds", {}) if isinstance(ledger, dict) else {}
    if not bed:
        return []
    owner = used.get(os.path.basename(bed))
    if owner and str(owner) != str(sid):
        return [f"music {os.path.basename(bed)} already plays under {owner}"]
    return []


def _norm(text: str) -> str:
    return re.sub(r"[\s\W_]+", "", text or "")


def _grams(text: str, n: int = 4) -> set[str]:
    t = _norm(text)
    return {t[i:i + n] for i in range(max(0, len(t) - n + 1))}


def similarity(a: str, b: str) -> float:
    ga, gb = _grams(a), _grams(b)
    if not ga or not gb:
        return 0.0
    return len(ga & gb) / len(ga | gb)


def script_problems(text: str, published: list[tuple[str, str]]) -> list[str]:
    """`published` is [(label, narration)]. Half-shared is a repeat."""
    out = []
    for label, other in published:
        share = similarity(text, other)
        if share >= DUP_THRESHOLD:
            out.append(f"script is {share:.0%} the same as {label}")
    return out


def script_text(script: dict) -> str:
    return " ".join([str(script.get("hook", "")), *map(str, script.get("lines", [])),
                     str(script.get("cta", ""))])


def check(kind: str, video: str | None = None, *, md5s=(), art_ledger=None, bed=None,
          bed_ledger=None, sid=None, narration=None, published=()) -> tuple[bool, list[str]]:
    """Every rule at once. Empty reason list means the upload may go."""
    reasons: list[str] = []
    if video:
        reasons += resolution_problems(video, kind)
    if art_ledger is not None:
        reasons += image_problems(list(md5s), art_ledger, sid)
    if bed_ledger is not None:
        reasons += music_problems(bed, bed_ledger, sid)
    if narration:
        reasons += script_problems(narration, list(published))
    return (not reasons), reasons


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", required=True, choices=sorted(FOUR_K))
    ap.add_argument("--video", required=True)
    ap.add_argument("--sid", default=None)
    ap.add_argument("--art-ledger")
    ap.add_argument("--image", action="append", default=[], help="a scene file (repeatable)")
    ap.add_argument("--bed-ledger")
    ap.add_argument("--bed", help="the music bed file name")
    args = ap.parse_args()

    art = json.load(open(args.art_ledger, encoding="utf-8")) if args.art_ledger else None
    beds = json.load(open(args.bed_ledger, encoding="utf-8")) if args.bed_ledger else None
    ok, reasons = check(args.kind, args.video, md5s=[md5_of(p) for p in args.image],
                        art_ledger=art, bed=args.bed, bed_ledger=beds, sid=args.sid)
    print(json.dumps({"verdict": "pass" if ok else "fail", "reasons": reasons}, indent=1,
                     ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
