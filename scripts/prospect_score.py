#!/usr/bin/env python3
"""Score a YouTube channel as a client for the clip-cutting service.

Why a score: the first offer draft listed 12 channels by subscriber count, which
says nothing about whether they need the service. This measures the two things
that predict a sale -- a long-form library that keeps growing, and almost no
Shorts -- plus whether the channel publishes a business contact at all.

Usage:
    python3 scripts/prospect_score.py                 # score the default list
    python3 scripts/prospect_score.py --channels UC..,UC..
    python3 scripts/prospect_score.py --json out.json

Weights (K, 2026-11-25): long-form cadence 25, few Shorts 25, clip-friendly
length 20, public business contact 15, active in the last 30 days 15.

Bands: >=80 first wave, 60-79 second wave, <60 do not contact yet.

Shorts are detected by duration: the Data API has no reliable "is a Short"
field, so a video <= 180 s is treated as a Short (YouTube's Shorts limit) and
the title/description is checked for #shorts as a second signal.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://www.googleapis.com/youtube/v3/"
DEFAULT = [
    ("ธรรมะ สอนใจ", "UC9lb6C6ExQQMtcjONdHuZYQ"),
    ("ผีเล่าเรื่อง", "UCP9x1YFhA3FsDJf6jFqBo1w"),
    ("อาหารสมอง The Podcast", "UCG5tYms4TAK-b7iVmRYCyFw"),
    ("รู้ ดู ลอง (รึเปล่านะ)", "UCABedktpjopAFzqTArweZdg"),
    ("Alpha Speech", "UC80YtEc-d11Rd3SDGUynHKg"),
    ("ปลุกพลังในตัวคุณ", "UCgnCVuer-7Ro5xnIlFXHuHQ"),
    ("จิตวิทยาเดลี่", "UCLLnh2-bIrcbw8KakP1M2IQ"),
    ("THE HEART WISDOM", "UCpyryLtZQ6A10uxQL4hXc0w"),
    ("The Perfect Man", "UCI3-0lKEdBA9Siz6eHVOP4Q"),
    ("Limitless Mind", "UCC1ZmT09lM6zcx6JlOFyQIg"),
    ("Turningpoint (จุดเปลี่ยน)", "UCaQrR0pKcNxmNag5wtlw4Xw"),
    ("The Indie Beat", "UCJtYl21_wgAjt1zz9FqpKnA"),
]
SHORT_MAX = 180
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"


def token() -> str:
    data = urllib.parse.urlencode({
        "client_id": os.environ["YT_CLIENT_ID"],
        "client_secret": os.environ["YT_CLIENT_SECRET"],
        "refresh_token": os.environ["YT_CH4_REFRESH_TOKEN"],
        "grant_type": "refresh_token",
    }).encode()
    req = urllib.request.Request("https://oauth2.googleapis.com/token", data=data)
    return json.load(urllib.request.urlopen(req))["access_token"]


def get(path: str, at: str, **params) -> dict:
    url = API + path + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + at})
    return json.load(urllib.request.urlopen(req))


def seconds(iso: str) -> int:
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not m:
        return 0
    h, mi, s = (int(x or 0) for x in m.groups())
    return h * 3600 + mi * 60 + s


def business_email(cid: str) -> str | None:
    """The About page carries businessEmail in its embedded JSON when the owner
    published one. No API exposes it."""
    try:
        req = urllib.request.Request(f"https://www.youtube.com/channel/{cid}/about",
                                     headers={"User-Agent": UA, "Accept-Language": "th,en"})
        html = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "ignore")
    except Exception:
        return None
    m = re.search(r'"businessEmail":"([^"]+)"', html)
    return m.group(1).replace("\\u0040", "@") if m else None


def score(m: dict) -> tuple[int, list[str]]:
    parts = {}
    parts["long_cadence"] = 25 * min(1.0, m["long_90d"] / 8)
    parts["few_shorts"] = 25 * (1 - m["short_share"])
    parts["clip_friendly"] = 20 * min(1.0, m["median_long_s"] / 600)
    parts["contact"] = 15 if m["email"] else 0
    parts["active"] = 15 * min(1.0, m["uploads_30d"] / 4)
    total = round(sum(parts.values()))
    return total, [f"{k}={v:.0f}" for k, v in parts.items()]


def analyse(at: str, name: str, cid: str) -> dict:
    now = time.time()
    ch = get("channels", at, part="statistics,contentDetails,snippet", id=cid)["items"][0]
    uploads = ch["contentDetails"]["relatedPlaylists"]["uploads"]
    pl = get("playlistItems", at, part="contentDetails", playlistId=uploads, maxResults=50)
    ids = [i["contentDetails"]["videoId"] for i in pl.get("items", [])]
    vids = []
    for i in range(0, len(ids), 50):
        vids += get("videos", at, part="contentDetails,statistics,snippet",
                    id=",".join(ids[i:i + 50]))["items"]
    longs, shorts = [], 0
    long_90d = uploads_30d = 0
    for v in vids:
        d = seconds(v["contentDetails"]["duration"])
        age = (now - time.mktime(time.strptime(v["snippet"]["publishedAt"], "%Y-%m-%dT%H:%M:%SZ"))) / 86400
        is_short = d <= SHORT_MAX or "#shorts" in (v["snippet"]["title"] + v["snippet"]["description"]).lower()
        if is_short:
            shorts += 1
        else:
            longs.append((d, int(v["statistics"].get("viewCount", 0))))
            if age <= 90:
                long_90d += 1
        if age <= 30:
            uploads_30d += 1
    m = {
        "name": name,
        "id": cid,
        "url": f"https://www.youtube.com/channel/{cid}",
        "subs": int(ch["statistics"].get("subscriberCount", 0)),
        "videos_total": int(ch["statistics"].get("videoCount", 0)),
        "sampled": len(vids),
        "long": len(longs),
        "short": shorts,
        "short_share": (shorts / len(vids)) if vids else 0.0,
        "long_90d": long_90d,
        "uploads_30d": uploads_30d,
        "median_long_s": statistics.median([d for d, _ in longs]) if longs else 0,
        "median_views_long": statistics.median([v for _, v in longs]) if longs else 0,
        "email": business_email(cid),
    }
    m["score"], m["breakdown"] = score(m)
    m["band"] = "first" if m["score"] >= 80 else ("second" if m["score"] >= 60 else "skip")
    return m


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--channels", help="comma-separated channel ids")
    ap.add_argument("--json", default="content/prospects.json")
    a = ap.parse_args()
    pairs = ([(cid, cid) for cid in a.channels.split(",")] if a.channels else DEFAULT)
    at = token()
    rows = []
    for name, cid in pairs:
        try:
            rows.append(analyse(at, name, cid))
            r = rows[-1]
            print(f"  {r['score']:3} {r['band']:6} {r['subs']:>6} subs | long {r['long']:2} short {r['short']:2} "
                  f"| 90d long {r['long_90d']:2} | 30d {r['uploads_30d']:2} | email {'yes' if r['email'] else 'no ':3} | {name}")
        except Exception as e:
            print(f"  ERR {name}: {e}")
    rows.sort(key=lambda r: -r["score"])
    os.makedirs(os.path.dirname(a.json) or ".", exist_ok=True)
    json.dump({"measured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "channels": rows},
              open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\nwrote {a.json} ({len(rows)} channels)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
