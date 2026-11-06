#!/usr/bin/env python3
"""Build a designed thumbnail from a video's own frame plus big Thai keywords.

Measured 2026-11-06: 27 of the 30 long-form videos still serve the automatic
frame (no custom thumbnail). A designed thumbnail is the click-through lever on
the browse and search surfaces, and it is the one lever left that needs no new
consent -- `thumbnails.set` works with the tokens we already hold.

The art is the video's own frame, which YouTube already serves at i.ytimg.com,
so no download of the video and no ffmpeg is needed. The best available frame is
fetched, graded, given the channel's dark-blue-and-gold scrim, and stamped with
3-4 short Thai words drawn from the keyword the advisor chose.

    python3 scripts/make_video_thumbnail.py --channel genx --longform
    python3 scripts/make_video_thumbnail.py --channel genx --ids paEd6W-3k1A
    python3 scripts/make_video_thumbnail.py --channel genx --longform --set

--set installs them through the Data API (thumbnails.set), which costs quota, so
by default it only writes the JPGs and prints the plan.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analytics import CHANNELS, access_token  # noqa: E402
from channel_admin import _get  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FONTS = os.path.join(ROOT, "assets", "fonts")
OUTDIR = os.path.join(ROOT, "assets", "branding", "thumbs")

W, H = 1280, 720
GOLD = (245, 199, 90)
WHITE = (248, 249, 252)
FRAME_SIZES = ("maxresdefault", "sddefault", "hqdefault", "mqdefault")


def font(size: int):
    return ImageFont.truetype(os.path.join(FONTS, "Kanit-Bold.ttf"), size)


def fetch_frame(vid: str) -> Image.Image | None:
    for size in FRAME_SIZES:
        url = f"https://i.ytimg.com/vi/{vid}/{size}.jpg"
        try:
            with urllib.request.urlopen(url, timeout=30) as fh:
                data = fh.read()
        except urllib.error.HTTPError:
            continue
        if len(data) < 2000:  # the grey placeholder is tiny; skip it
            continue
        import io
        return Image.open(io.BytesIO(data)).convert("RGB")
    return None


def cover(im: Image.Image) -> Image.Image:
    """Fit the frame to 1280x720. A portrait (Short) frame is pillarboxed over a
    blurred copy of itself, so the vertical subject is not cropped away."""
    if im.height > im.width:
        r = H / im.height
        core = im.resize((int(im.width * r), H), Image.LANCZOS)
        bg = im.resize((W, int(im.width * W / im.width)), Image.LANCZOS)
        bg = bg.crop((0, max(0, (bg.height - H) // 2), W, max(0, (bg.height - H) // 2) + H))
        bg = bg.filter(ImageFilter.GaussianBlur(24))
        bg = ImageEnhance.Brightness(bg).enhance(0.5)
        x = (W - core.width) // 2
        bg.paste(core, (x, 0))
        return bg
    r = max(W / im.width, H / im.height)
    im = im.resize((max(W, int(im.width * r)), max(H, int(im.height * r))), Image.LANCZOS)
    left = (im.width - W) // 2
    top = int((im.height - H) * 0.42)
    return im.crop((left, top, left + W, top + H))


def words(title: str, keyword: str, n: int = 3) -> list[str]:
    """Pick up to n short phrases for the card: the keyword first, then the head.

    The title is already keyword-first, so its first clause is the hook. Keep the
    lines short -- a thumbnail is read at a glance, not scanned.
    """
    picks = []
    if keyword and not keyword.startswith("#"):
        picks.append(keyword.strip())
    head = re.split(r"[:|—–\-]| ", title.strip())
    for part in head:
        part = part.strip(" ,.")
        if part and not part.startswith("#") and part not in picks and len(part) <= 22:
            picks.append(part)
        if len(picks) >= n:
            break
    return picks[:n]


def draw(im: Image.Image, lines: list[str]) -> Image.Image:
    im = ImageEnhance.Color(im).enhance(1.12)
    im = ImageEnhance.Contrast(im).enhance(1.1)
    im = im.filter(ImageFilter.GaussianBlur(0.4))

    scrim = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(scrim)
    for y in range(H):
        d.line([(0, y), (W, y)], fill=int(205 * (y / H) ** 1.5))
    im = Image.composite(Image.new("RGB", (W, H), (4, 8, 20)), im, scrim)

    d = ImageDraw.Draw(im)
    size = 150
    while size > 58:
        f = font(size)
        if max(d.textbbox((0, 0), ln, font=f)[2] for ln in lines) <= W - 120:
            break
        size -= 6
    f = font(size)
    heights = [d.textbbox((0, 0), ln, font=f)[3] - d.textbbox((0, 0), ln, font=f)[1]
               for ln in lines]
    gap = int(size * 0.22)
    total = sum(heights) + gap * (len(lines) - 1)
    y = H - 60 - total
    d.rectangle([56, y + 8, 68, y + total - 8], fill=GOLD)
    for i, (ln, hh) in enumerate(zip(lines, heights)):
        d.text((96, y), ln, font=f, fill=GOLD if i == 0 else WHITE,
               stroke_width=5, stroke_fill=(0, 0, 0))
        y += hh + gap
    return im


def build(vid: str, title: str, keyword: str, out: str,
          gen_art: bool = False, style: str = "dharma") -> str | None:
    if gen_art:
        # K's rule: no two videos share an image. Draw a fresh one seeded by the
        # video id, so each video gets its own art and a re-run is stable.
        sys.path.insert(0, HERE)
        import gen_cover_image
        seed = int(hashlib.sha256(vid.encode()).hexdigest()[:8], 16)
        prompt = keyword.strip() or " ".join(words(title, keyword, 3))
        data, src = gen_cover_image.generate(style, prompt, seed, W, H)
        if not data:
            return None
        import io
        art = Image.open(io.BytesIO(data)).convert("RGB")
        print(f"    art from {src} (seed {seed})")
    else:
        art = fetch_frame(vid)
        if art is None:
            return None
    im = draw(cover(art), words(title, keyword))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    im.save(out, quality=90)
    return out


def set_thumb(vid: str, path: str, token: str) -> tuple[bool, str]:
    with open(path, "rb") as fh:
        img = fh.read()
    req = urllib.request.Request(
        f"https://www.googleapis.com/upload/youtube/v3/thumbnails/set"
        f"?videoId={vid}&uploadType=media",
        data=img, method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "image/jpeg"})
    try:
        urllib.request.urlopen(req, timeout=90)
        return True, "set"
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        try:
            reason = json.loads(body)["error"]["errors"][0]["reason"]
        except Exception:
            reason = body[:120]
        return False, f"{exc.code} {reason}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", default="genx", choices=list(CHANNELS))
    ap.add_argument("--ids", default="")
    ap.add_argument("--longform", action="store_true")
    ap.add_argument("--all", action="store_true",
                    help="every video on the channel, newest first")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--set", action="store_true", help="install through the Data API")
    ap.add_argument("--gen-art", action="store_true",
                    help="draw a fresh unique image per video instead of the frame")
    args = ap.parse_args()

    # title + keyword for each changed video come from the ledger
    ledger = os.path.join(ROOT, "docs", "title_changes.json")
    with open(ledger, encoding="utf-8") as fh:
        changes = {c["id"]: c for c in json.load(fh)["changes"]}

    token = access_token(CHANNELS[args.channel][0])
    ids = [x.strip() for x in args.ids.split(",") if x.strip()]
    if not ids:
        if not (args.longform or args.all):
            sys.exit("give --ids, --longform or --all")
        try:
            it = _get("channels", {"part": "contentDetails", "mine": "true"}, token)["items"][0]
            up = it["contentDetails"]["relatedPlaylists"]["uploads"]
            allids, page = [], None
            while True:
                p = {"part": "contentDetails", "playlistId": up, "maxResults": "50"}
                if page:
                    p["pageToken"] = page
                r = _get("playlistItems", p, token)
                allids += [x["contentDetails"]["videoId"] for x in r.get("items", [])]
                page = r.get("nextPageToken")
                if not page:
                    break
        except urllib.error.HTTPError as exc:
            if exc.code == 403 and "quotaExceeded" in exc.read().decode(errors="ignore"):
                print("daily YouTube quota exhausted -- re-run after the 08:00 UTC reset")
                return 0
            raise
        if args.longform:
            ids = [v for v in allids if v in changes]
        else:
            # --all: every video, but never one already given a thumbnail
            done_path = os.path.join(ROOT, "docs", "thumbnail_changes.json")
            already = set()
            if os.path.exists(done_path):
                with open(done_path, encoding="utf-8") as fh:
                    already = {c["id"] for c in json.load(fh).get("changes", [])}
            ids = [v for v in allids if v not in already]
            print(f"(skipped {len(allids) - len(ids)} already-thumbnailed)")

    if args.limit:
        ids = ids[:args.limit]
    print(f"=== {args.channel}: {len(ids)} video(s)")

    applied = []
    for vid in ids:
        c = changes.get(vid, {})
        # the live title is the ground truth for the card words; the ledger is a
        # fallback for a video the title pass did not reach
        title = c.get("new_title") or c.get("title") or ""
        kw = c.get("keyword", "")
        out = os.path.join(OUTDIR, f"{vid}.jpg")
        style = "family" if args.channel == "kongkeat" else "dharma"
        path = build(vid, title, kw, out, gen_art=args.gen_art, style=style)
        if not path:
            print(f"  {vid}: no frame available")
            continue
        line = f"  {vid}: {os.path.getsize(path)//1024} KB  lines={words(title, kw)}"
        if args.set:
            ok, msg = set_thumb(vid, path, token)
            line += f"  -> {msg}"
            if ok:
                applied.append({"id": vid, "channel": args.channel,
                                "at": datetime.now(timezone.utc).isoformat()})
            elif "quotaExceeded" in msg or "403" in msg:
                print(line + "\n   -> DAILY QUOTA REACHED -- stopping")
                break
        print(line)
    if args.set:
        print(f"set {len(applied)}/{len(ids)}")
        if applied:
            done_path = os.path.join(ROOT, "docs", "thumbnail_changes.json")
            doc = {"changes": []}
            if os.path.exists(done_path):
                with open(done_path, encoding="utf-8") as fh:
                    doc = json.load(fh)
            doc.setdefault("changes", []).extend(applied)
            with open(done_path, "w", encoding="utf-8") as fh:
                json.dump(doc, fh, ensure_ascii=False, indent=2)
            print("ledger", done_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
