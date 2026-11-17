#!/usr/bin/env python3
"""Fetch free, licence-clean REAL b-roll clips -- no API key, no GPU.

The owner's reference (a Google Veo clip) is a live-action shot of a person in a
warm room. Vision-graded 2026-11-17, the honest gap is that a *free* generative
model cannot make a believable human (pollinations scored 3-4/10; the Gemini free
tier has zero image quota; a paid video API is ~$135 for a 30-min file). The panel
(advise.py, 5/5) therefore ruled: do NOT ship AI faces and do NOT pay per clip --
use REAL footage. Real footage is also what "photoreal" actually means here.

Coverr (coverr.co) exposes a keyless search API and serves 1080p mp4s from its CDN;
its licence (checked 2026-11-17, coverr.co/license) allows free commercial use and
requires no attribution. This client searches, filters to usable landscape clips
(drops premium / vertical / AI-generated / too-short or too-long), downloads one,
and returns its attribution so the caller can credit it anyway.

    python3 scripts/fetch_broll.py --query "ocean waves" --out work/broll/01.mp4
    python3 scripts/fetch_broll.py --query "rain on window" --out x.mp4 --json
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request

API = "https://coverr.co/api/videos"
CDN = "https://cdn.coverr.co/videos"
UA = "Mozilla/5.0 (ai-content-lab; b-roll fetcher)"


def _get(url: str, timeout: int = 40) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as fh:
        return fh.read()


def search(query: str, page_size: int = 24) -> list[dict]:
    """Raw Coverr hits for a query (keyless). Returns [] if the API is unreachable."""
    url = f"{API}?query={urllib.parse.quote(query)}&page_size={page_size}"
    try:
        return json.loads(_get(url)).get("hits", [])
    except Exception:  # noqa: BLE001 - a dead source must read as "no clip", not crash
        return []


def usable(hit: dict, min_height: int = 720, min_dur: float = 4.0,
           max_dur: float = 40.0, allow_ai: bool = False) -> bool:
    """A clip we can legally and usefully put behind a Thai voice-over."""
    if hit.get("is_premium") or hit.get("is_vertical"):
        return False
    if hit.get("is_ai_generated") and not allow_ai:
        return False  # the whole point is REAL footage, not more AI
    if (hit.get("max_height") or 0) < min_height:
        return False
    try:
        d = float(hit.get("duration") or 0)
    except (TypeError, ValueError):
        return False
    if not (min_dur <= d <= max_dur):
        return False
    return bool(hit.get("base_filename"))


def pick(query: str, avoid: set | None = None, **kw) -> dict | None:
    """The best usable hit for a query, skipping ids already used this video."""
    avoid = avoid or set()
    for h in search(query):
        if h.get("id") in avoid:
            continue
        if usable(h, **kw):
            return h
    return None


def pick_and_download(query: str, out: str, avoid: set | None = None,
                      min_luma: float = 0.0, quality: str = "1080p",
                      tries: int = 5) -> dict | None:
    """Download the first usable hit whose mean luma clears `min_luma`.

    `pick` returns a single hit, so a rejected one (too dark) had no fallback and
    the beat silently fell back to a still -- measured 2026-11-17 with the luma
    gate on, 3 of 4 beats lost their real b-roll. So walk the search results and
    take the first that both downloads and is bright enough. Returns the hit, or
    None when none qualify.
    """
    avoid = avoid or set()
    n = 0
    for h in search(query):
        if h.get("id") in avoid or not usable(h):
            continue
        n += 1
        if download(h, out, quality, min_luma=min_luma):
            return h
        if n >= tries:
            break
    return None


def video_url(hit: dict, quality: str = "1080p") -> str:
    return f"{CDN}/{hit['base_filename']}/{quality}.mp4"


def attribution(hit: dict) -> dict:
    return {"source": "Coverr", "title": hit.get("title", ""),
            "url": f"https://coverr.co/videos/{hit.get('slug', hit.get('id', ''))}",
            "license": "Coverr License (free commercial use, no attribution required)"}


def download(hit: dict, out: str, quality: str = "1080p") -> bool:
    """Stream the mp4 to `out` (trying 1080p then 720p). True on success."""
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    for q in ([quality] if quality == "720p" else [quality, "720p"]):
        url = video_url(hit, q)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=120) as r, open(out, "wb") as f:
                shutil.copyfileobj(r, f)
        except Exception:  # noqa: BLE001
            continue
        if os.path.getsize(out) > 20000 and _is_video(out):
            return True
    return False


def _is_video(path: str) -> bool:
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                        "-show_entries", "stream=codec_name", "-of", "csv=p=0", path],
                       capture_output=True, text=True)
    return r.returncode == 0 and bool(r.stdout.strip())


def mean_luma(path: str, t: float = 1.0) -> float:
    """Mean luma (0-255) of one frame. A dark clip reads as 'ขุ่นมัว' (muddy),
    which the owner rejected -- so the fetcher must be able to reject it."""
    r = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", str(t), "-i", path,
                        "-frames:v", "1", "-vf", "scale=64:36,format=gray",
                        "-f", "rawvideo", "-"], capture_output=True)
    if r.returncode != 0 or not r.stdout:
        return 255.0  # cannot measure -> do not reject
    return sum(r.stdout) / len(r.stdout)


def download(hit: dict, out: str, quality: str = "1080p",
             min_luma: float = 0.0) -> bool:
    """Stream the mp4 to `out` (trying 1080p then 720p). True on success.

    A clip whose mean luma is below `min_luma` is rejected -- measured 2026-11-17
    a 'sleepy' b-roll landed at luma 70 and made the beat look muddy, the exact
    complaint the owner raised. Default 0 disables the gate (CLI use)."""
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    for q in ([quality] if quality == "720p" else [quality, "720p"]):
        url = video_url(hit, q)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=120) as r, open(out, "wb") as f:
                shutil.copyfileobj(r, f)
        except Exception:  # noqa: BLE001
            continue
        if os.path.getsize(out) > 20000 and _is_video(out):
            if min_luma and mean_luma(out) < min_luma:
                continue  # too dark -> try the next quality, then give up
            return True
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--query", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--quality", default="1080p", choices=["1080p", "720p"])
    ap.add_argument("--json", action="store_true", help="print the attribution as JSON")
    a = ap.parse_args()
    hit = pick(a.query)
    if not hit:
        print(f"no usable free b-roll for {a.query!r}", file=sys.stderr)
        return 1
    if not download(hit, a.out, a.quality):
        print(f"download failed for {a.query!r}", file=sys.stderr)
        return 1
    att = attribution(hit)
    if a.json:
        print(json.dumps(att, ensure_ascii=False))
    else:
        print(f"{a.out} <- {att['title']} ({att['url']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
