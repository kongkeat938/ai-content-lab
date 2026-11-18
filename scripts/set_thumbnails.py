#!/usr/bin/env python3
"""Install channel thumbnails with the YouTube Data API -- no browser, no human.

Studio's thumbnail button is gated behind phone verification for a new channel,
and the browser login dies whenever the pod is recycled. The API has neither
problem: a refresh token in the environment is enough. This is the path that
keeps working unattended.

    python3 scripts/set_thumbnails.py --dry-run        # list what it would set
    python3 scripts/set_thumbnails.py                  # set every manifest entry
    python3 scripts/set_thumbnails.py --only _qOSft3tzJ8
    python3 scripts/set_thumbnails.py --check          # are they live already?

Credentials come from the environment, exactly like publish_youtube.py:
YT_CLIENT_ID, YT_CLIENT_SECRET and YT_<SLUG>_REFRESH_TOKEN (here YT_CH2_...).
In GitHub Actions they are repo secrets, so the job runs with no browser at all.

Quota: measured 2026-11-03, `thumbnails.set` is NOT on a quota of its own -- a
spent project quota returns `403 quotaExceeded` for it too, and the daily quota
resets at midnight Pacific (08:00 UTC). So a quota error is reported as
`deferred` and does not fail the run; the scheduled job retries after the reset.

`thumbnails.set` is idempotent: setting the same image again is harmless, so a
re-run after a dropped job costs nothing.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MANIFEST = os.path.join(ROOT, "content", "ch2_thumbnails.json")
TOKEN_URL = "https://oauth2.googleapis.com/token"
SET_URL = "https://www.googleapis.com/upload/youtube/v3/thumbnails/set"
READ_URL = "https://www.googleapis.com/youtube/v3/videos"

# slug -> env var holding that channel's refresh token
TOKEN_ENV = {
    "dharma": "YT_CH2_REFRESH_TOKEN",
    "genx": "YT_CH1_REFRESH_TOKEN",
    "aeris-music": "YT_CH3_REFRESH_TOKEN",
    "kongkeat-story": "YT_CH4_REFRESH_TOKEN",
}


def access_token(slug: str) -> str:
    cid = os.environ.get("YT_CLIENT_ID")
    sec = os.environ.get("YT_CLIENT_SECRET")
    var = TOKEN_ENV.get(slug, f"YT_{slug.upper().replace('-', '_')}_REFRESH_TOKEN")
    rt = os.environ.get(var)
    if not (cid and sec and rt):
        sys.exit(f"Missing credentials: need YT_CLIENT_ID, YT_CLIENT_SECRET and {var}")
    data = urllib.parse.urlencode({
        "client_id": cid, "client_secret": sec,
        "refresh_token": rt, "grant_type": "refresh_token"}).encode()
    try:
        return json.load(urllib.request.urlopen(TOKEN_URL, data=data, timeout=30))["access_token"]
    except urllib.error.HTTPError as exc:
        sys.exit(f"Token refresh failed for {slug} ({var}): {exc.code} {exc.read().decode()[:200]}")


def http_error(exc: urllib.error.HTTPError) -> str:
    body = exc.read().decode(errors="replace")
    try:
        reason = json.loads(body)["error"]["errors"][0]["reason"]
    except Exception:
        reason = body[:160]
    return f"{exc.code} {reason}"


def current_thumbnail(video_id: str, token: str) -> str:
    """Which URL YouTube is serving, so we can tell ours from the auto frame.

    The URL's presence is NOT proof a custom image is set: YouTube also publishes
    `maxresdefault.jpg` for an auto-generated frame, so a truthy URL alone let a
    video with no custom thumbnail be skipped forever (measured 2026-11-18: video
    DHs1j6o0JE0 returned a maxres URL whose content was the auto frame, not ours).
    Compare the served bytes with the file we meant to install (`matches_live`).
    """
    try:
        req = urllib.request.Request(
            f"{READ_URL}?part=snippet&id={video_id}&fields=items/snippet/thumbnails/maxres/url",
            headers={"Authorization": f"Bearer {token}"})
        items = json.load(urllib.request.urlopen(req, timeout=30)).get("items", [])
        if items:
            return items[0]["snippet"]["thumbnails"].get("maxres", {}).get("url", "")
    except urllib.error.HTTPError:
        return ""
    return ""


def _download(url: str) -> Image.Image:
    req = urllib.request.Request(url, headers={"User-Agent": "ai-content-lab"})
    return Image.open(io.BytesIO(urllib.request.urlopen(req, timeout=30).read())).convert("RGB")


def _same_as(live: Image.Image, path: str) -> bool:
    """Correlation of the served frame with the file we meant to install."""
    try:
        local = Image.open(path).convert("RGB").resize(live.size)
        a = np.asarray(live, dtype=float).ravel()
        b = np.asarray(local, dtype=float).ravel()
        return float(np.corrcoef(a, b)[0, 1]) > 0.9
    except Exception:
        return False


def matches_live(video_id: str, path: str, token: str) -> bool:
    """True when the thumbnail YouTube serves is the file we meant to install.

    A correlation over the whole frame: the same image re-encoded scores >0.99,
    while an auto frame or any different image scores far below (measured: ours
    0.999, an auto frame 0.43). Any read/compare error is NOT a match, so an
    unknown never counts as done.
    """
    url = current_thumbnail(video_id, token)
    if not url:
        return False
    try:
        return _same_as(_download(url), path)
    except Exception:
        return False


def set_thumbnail(video_id: str, path: str, token: str) -> tuple[bool, str]:
    with open(path, "rb") as fh:
        img = fh.read()
    req = urllib.request.Request(
        f"{SET_URL}?videoId={video_id}&uploadType=media",
        data=img, method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "image/jpeg"})
    try:
        urllib.request.urlopen(req, timeout=90)
        return True, "set"
    except urllib.error.HTTPError as exc:
        return False, http_error(exc)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default=MANIFEST)
    ap.add_argument("--only", action="append", help="video id (repeatable)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--check", action="store_true", help="report live thumbnails only")
    ap.add_argument("--skip-existing", action="store_true",
                    help="do not re-set a video that already serves a custom thumbnail")
    args = ap.parse_args()

    with open(args.manifest, encoding="utf-8") as fh:
        man = json.load(fh)
    slug = man["channel_slug"]
    items = man["thumbnails"]
    if args.only:
        items = {k: v for k, v in items.items() if k in args.only}

    token = access_token(slug)
    print(f"channel {slug} ({man['channel_id']}) — {len(items)} thumbnail(s)")

    if args.check:
        for vid, rel in items.items():
            path = rel if os.path.isabs(rel) else os.path.join(ROOT, rel)
            have = os.path.exists(path)
            url = current_thumbnail(vid, token)
            live = "ours" if (have and matches_live(vid, path, token)) else "auto/other"
            print(f"  {vid}: {live} {'(local file missing)' if not have else ''} {url[:70]}")
        return 0

    ok = failed = deferred = skipped = 0
    for vid, rel in items.items():
        path = rel if os.path.isabs(rel) else os.path.join(ROOT, rel)
        if not os.path.exists(path):
            print(f"  {vid}: MISSING {rel}"); failed += 1; continue
        if args.dry_run:
            print(f"  {vid}: would set {rel} ({os.path.getsize(path)//1024} KB)"); continue
        if args.skip_existing and matches_live(vid, path, token):
            # Already serving OUR image. Re-setting is idempotent but a
            # thumbnails.set costs real quota, and YouTube rate-limits a burst
            # (429 uploadRateLimitExceeded, measured 2026-11-03). Do not spend
            # quota on a video that is already done.
            print(f"  {vid}: already set, skipped"); skipped += 1; continue
        good, msg = set_thumbnail(vid, path, token)
        if good:
            print(f"  {vid}: OK")
        elif "quotaExceeded" in msg:
            # The daily quota resets at midnight Pacific; the schedule retries.
            print(f"  {vid}: deferred (quota resets 08:00 UTC)"); deferred += 1
        elif "429" in msg or "RateLimit" in msg:
            # A burst rate limit, not a defect: back off and let the next run finish.
            print(f"  {vid}: deferred (rate limited, retry later)"); deferred += 1
        else:
            print(f"  {vid}: FAIL ({msg})"); failed += 1
        ok += good

    if args.dry_run:
        return 0
    print(f"done: {ok} set, {skipped} skipped, {deferred} deferred, {failed} failed")
    # A quota deferral is not a defect -- the next scheduled run finishes it.
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
