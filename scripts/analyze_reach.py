#!/usr/bin/env python3
"""Classify every live video by hook shape and print the measured contrast.

`report_reach.py` lists videos by views/day; this asks the next question: *which
shape* of hook wins, and by how much. It reads the live channels through the
same Data API, tags each title by shape (a rule table, not a hand-picked list),
and prints the median views/day per shape and channel. Medians, not means: one
2,000-view first day would drag a mean off the honest signal, and the channels
are small enough that a single clip can do that.

    python3 scripts/analyze_reach.py
    python3 scripts/analyze_reach.py --json   # machine-readable, for the doc

Read-only. Needs the same YT_*_REFRESH_TOKEN env as report_reach.py.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yt_duration

import argparse
import json
import re
import statistics
import urllib.parse
import urllib.request
from datetime import datetime, timezone

CHANNELS = {
    "genx": ("YT_CH1_REFRESH_TOKEN", "UCI6EfsgM1HNjrYarvigxyrQ", "ตาต้า GenX"),
    "dharma": ("YT_CH2_REFRESH_TOKEN", "UCM3QO5L_pmj34n1JVlbhh-w", "Farmmer"),
    "kongkeat": ("YT_CH4_REFRESH_TOKEN", "UC7gCIu4G_7QCEJ8hJ-34zoQ", "เรื่องเล่าอบอุ่นใจ"),
}

# Hook shapes, per channel. Each rule is a set of substrings; the first rule
# that matches wins, so order is priority. They are per channel because the same
# words mean opposite things on different channels: on dharma "ทำไมนอนไม่หลับ"
# is a losing problem-restatement, while on genx a hook that names a painful
# truth about the viewer ("คนที่ทรมานเรามากที่สุดคือตัวเราเอง") is the winner.
# Source of the shapes: docs/HOOKS-MEASURED.md.
RULES = {
    "dharma": [
        ("tonight-action", ["คืนนี้", "ก่อนนอน", "ลอง", "เปิดทิ้งไว้", "ทำตามนี้",
                            "ทำท่านี้", "วางมือถือ", "กอดหมอน"]),
        ("problem", ["ทำไม", "เพราะ", "ขโมย", "กลัว", "กังวล", "ผิดพลาด",
                     "ไม่หลับ", "หยุดคิด", "ตาสว่าง"]),
    ],
    "genx": [
        ("permission", ["ไม่ต้อง", "มีสิทธิ์", "อนุญาต", "พอแล้ว", "พักได้"]),
        ("self-truth", ["ตัวเราเอง", "เราเอง", "ทรมาน", "ยอมรับ", "เกลียด",
                        "ความจริง", "ความคุ้นเคย", "ตามหา", "เงียบ", "เหนื่อย"]),
    ],
    "kongkeat": [
        ("family-moment", ["พ่อ", "แม่", "พี่ชาย", "พี่สาว", "ลูกชาย", "ลูกสาว", "ครอบครัว"]),
    ],
}


def classify(slug: str, title: str) -> str:
    for name, cues in RULES.get(slug, []):
        if any(c in title for c in cues):
            return name
    return "other"


def access_token(env: str) -> str:
    data = urllib.parse.urlencode({
        "client_id": os.environ["YT_CLIENT_ID"],
        "client_secret": os.environ["YT_CLIENT_SECRET"],
        "refresh_token": os.environ[env],
        "grant_type": "refresh_token"}).encode()
    with urllib.request.urlopen("https://oauth2.googleapis.com/token", data=data, timeout=30) as fh:
        return json.load(fh)["access_token"]


def api(path: str, token: str) -> dict:
    req = urllib.request.Request(f"https://www.googleapis.com/youtube/v3/{path}",
                                 headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=30) as fh:
        return json.load(fh)


def seconds(iso: str) -> int:
    return yt_duration.seconds(iso)


def uploads(channel_id: str, token: str) -> list[str]:
    up = api(f"channels?part=contentDetails&id={channel_id}", token)["items"][0]
    up = up["contentDetails"]["relatedPlaylists"]["uploads"]
    ids, page = [], None
    while True:
        q = f"playlistItems?part=contentDetails&playlistId={up}&maxResults=50"
        if page:
            q += f"&pageToken={page}"
        r = api(q, token)
        ids += [i["contentDetails"]["videoId"] for i in r["items"]]
        page = r.get("nextPageToken")
        if not page:
            return ids


def collect(slug: str) -> list[dict]:
    env, cid, _ = CHANNELS[slug]
    token = access_token(env)
    ids = uploads(cid, token)
    now = datetime.now(timezone.utc)
    rows = []
    for i in range(0, len(ids), 50):
        v = api("videos?part=statistics,contentDetails,snippet&id=" + ",".join(ids[i:i + 50]), token)
        for x in v["items"]:
            dur = seconds(x["contentDetails"]["duration"])
            pub = datetime.fromisoformat(x["snippet"]["publishedAt"].replace("Z", "+00:00"))
            days = max((now - pub).total_seconds() / 86400, 0.01)
            views = int(x["statistics"].get("viewCount", 0))
            title = x["snippet"]["title"]
            rows.append({"id": x["id"], "title": title, "dur": dur, "views": views,
                         "days": days, "per_day": views / days, "shape": classify(slug, title),
                         "is_short": dur <= 180})
    return rows


def median(xs: list[float]) -> float:
    return round(statistics.median(xs), 1) if xs else 0.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    out = {}
    for slug in CHANNELS:
        rows = collect(slug)
        shorts = [r for r in rows if r["is_short"] and 0.5 <= r["days"] <= 8]
        out[slug] = {"rows": rows, "shorts": shorts}
        if not args.json:
            print(f"\n===== {slug} ({CHANNELS[slug][2]}) — {len(rows)} videos, "
                  f"{len(shorts)} Shorts 0.5-8 days old =====")
            print(f"{'shape':16s} {'n':>3s} {'median views/day':>17s}  examples")
            by_shape: dict[str, list] = {}
            for r in shorts:
                by_shape.setdefault(r["shape"], []).append(r)
            for shape, rs in sorted(by_shape.items(), key=lambda kv: -median([r["per_day"] for r in kv[1]])):
                ex = sorted(rs, key=lambda r: -r["per_day"])[:2]
                exs = " | ".join(f"{r['title'][:28]} ({r['per_day']:.0f})" for r in ex)
                print(f"{shape:16s} {len(rs):3d} {median([r['per_day'] for r in rs]):17.1f}  {exs}")

    if args.json:
        print(json.dumps({s: {"shorts": [{k: r[k] for k in
                        ("id", "title", "views", "days", "per_day", "shape", "dur")}
                        for r in v["shorts"]]} for s, v in out.items()},
                         ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
