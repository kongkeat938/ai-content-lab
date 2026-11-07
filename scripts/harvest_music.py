#!/usr/bin/env python3
"""Harvest music beds from our own music channel (AERIS Music, ch3).

The owner asked for the channel's real music instead of the synth bed. The
music is ours, so reusing it is safe -- Content ID self-matches and a
rights-owner dispute never arises (panel advice, 2026-11-07). Two measured
constraints shape what this script produces:

  * The pod's IP is refused by YouTube (403, "confirm you're not a bot"), so the
    download must run on a CI runner.
  * The catalogue is vocal Thai songs, and a vocal bed competes with the
    narration, so each track is reduced to a bed: the centre channel (where a
    lead vocal sits) is cancelled and the top end is rolled off, then the result
    is trimmed to a short, loopable length.

    python3 scripts/harvest_music.py --rss UCm44BjAn03ruOF-WaA3ZRww \
        --out-dir assets/music --seconds 45 --limit 12
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.request

RSS = "https://www.youtube.com/feeds/videos.xml?channel_id="
UA = {"User-Agent": "ai-content-lab/1.0 (own-channel music harvest)"}


def rss_ids(channel_id: str) -> list[tuple[str, str]]:
    """(id, title) for the channel's recent uploads, from the RSS feed.

    The feed needs no API key and no quota, unlike search.list which spends 100
    units per call. It carries the 15 most recent uploads, which is enough to
    stock a bed library.
    """
    req = urllib.request.Request(RSS + channel_id, headers=UA)
    xml = urllib.request.urlopen(req, timeout=40).read().decode("utf-8", "replace")
    ids = re.findall(r"<yt:videoId>(.*?)</yt:videoId>", xml)
    titles = re.findall(r"<media:title>(.*?)</media:title>", xml)
    return list(zip(ids, titles))


def grab(vid: str, out_base: str) -> str | None:
    """Download one track's audio. Returns the wav path, or None on refusal."""
    import shutil
    cmd = [sys.executable, "-m", "yt_dlp"]
    # yt-dlp needs a JS runtime to solve YouTube's challenge; without one it is
    # refused with "confirm you're not a bot" (measured on a clean CI runner too).
    if shutil.which("deno"):
        cmd += ["--js-runtimes", "deno"]
    cmd += ["-f", "bestaudio/best", "-x", "--audio-format", "wav",
            "-o", out_base + ".%(ext)s",
            f"https://www.youtube.com/watch?v={vid}"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"    skip {vid}: {r.stderr.strip().splitlines()[-1][:90] if r.stderr else 'failed'}",
              file=sys.stderr)
        return None
    wav = out_base + ".wav"
    return wav if os.path.exists(wav) else None


def to_bed(src: str, out: str, start: float, seconds: float) -> bool:
    """Reduce a song to a bed: centre-cancelled, low-passed, trimmed, quiet.

    Centre cancellation removes a lead vocal that sits in the middle of the
    stereo field; the low-pass keeps what remains from competing with speech
    intelligibility. The target is -22 LUFS, well under the narration, so the
    mix stage only has to nudge it.
    """
    af = (f"atrim=start={start}:duration={seconds},asetpts=PTS-STARTPTS,"
          "pan=stereo|c0=c0-c1|c1=c1-c0,"
          "lowpass=f=7500,"
          "loudnorm=I=-22:TP=-4:LRA=11")
    r = subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                        "-i", src, "-af", af, "-ar", "48000", "-ac", "2",
                        "-b:a", "96k", out], capture_output=True, text=True)
    if r.returncode != 0:
        print(f"    ffmpeg failed: {r.stderr[-160:]}", file=sys.stderr)
        return False
    return True


def slug(title: str) -> str:
    s = re.sub(r"[^0-9A-Za-z\u0e00-\u0e7f]+", "-", title).strip("-")
    return s[:40] or "track"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rss", help="channel id to harvest from")
    ap.add_argument("--ids", help="explicit comma-separated video ids instead")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--seconds", type=float, default=45.0)
    ap.add_argument("--start", type=float, default=8.0,
                    help="skip this many seconds, past a spoken intro")
    ap.add_argument("--limit", type=int, default=12)
    args = ap.parse_args()

    items: list[tuple[str, str]] = []
    if args.ids:
        items = [(i.strip(), i.strip()) for i in args.ids.split(",") if i.strip()]
    elif args.rss:
        items = rss_ids(args.rss)
    items = items[:args.limit]
    if not items:
        print("nothing to harvest", file=sys.stderr)
        return 1

    os.makedirs(args.out_dir, exist_ok=True)
    tmp = os.path.join(args.out_dir, "_tmp")
    os.makedirs(tmp, exist_ok=True)
    prov, ok = [], 0
    for vid, title in items:
        print(f"  {vid}  {title[:50]}")
        wav = grab(vid, os.path.join(tmp, vid))
        if not wav:
            continue
        name = f"{slug(title)}-{vid[:6]}.mp3"
        dest = os.path.join(args.out_dir, name)
        if to_bed(wav, dest, args.start, args.seconds):
            prov.append({"file": name, "video_id": vid, "title": title,
                         "source": f"https://www.youtube.com/watch?v={vid}",
                         "note": "own channel (AERIS Music); bed = centre-cancelled, low-passed"})
            ok += 1
            print(f"    -> {name}")
        os.remove(wav)
    with open(os.path.join(args.out_dir, "provenance.json"), "w", encoding="utf-8") as fh:
        json.dump(prov, fh, ensure_ascii=False, indent=2)
    print(f"harvested {ok} bed(s) into {args.out_dir}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
