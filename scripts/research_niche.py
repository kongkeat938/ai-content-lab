#!/usr/bin/env python3
"""Measure the niche live, then write it down (K, 2026-11-21: "ไปค้นหาความรู้").

Two measurements, both from the vendor's own API -- never from an article:

  * market  -- `search.list` for the Thai queries our channels compete on, then
    `videos.list` for real views/duration/age. 100 quota units per query.
  * ours    -- our own recent uploads with views + average view percentage.

    python3 scripts/research_niche.py --market --ours \
        --out docs/RESEARCH-2026-11-21-niche.md

The output is a table an editor can act on: which duration and which promise
actually earn views in this niche right now.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from analytics import CHANNELS, access_token  # noqa: E402
from channel_admin import _get  # noqa: E402
from yt_duration import seconds  # noqa: E402

QUERIES = [
    "ธรรมะก่อนนอน",
    "ปล่อยวาง ก่อนนอน",
    "ฟังก่อนนอน หลับสบาย",
    "เรื่องเล่าก่อนนอน ผู้ใหญ่",
    "ข้อคิดชีวิต วัยกลางคน",
    "นอนไม่หลับ ฟังสิ่งนี้",
]


def _iso_days(published: str) -> float:
    then = datetime.strptime(published, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    return max((datetime.now(timezone.utc) - then).total_seconds() / 86400, 0.5)


def search(token: str, query: str, limit: int = 15) -> list[dict]:
    j = _get("search", {"part": "snippet", "q": query, "type": "video",
                        "maxResults": limit, "regionCode": "TH",
                        "relevanceLanguage": "th", "videoDuration": "long"}, token)
    return [it["id"]["videoId"] for it in j.get("items", []) if it.get("id", {}).get("videoId")]


def details(token: str, ids: list[str]) -> list[dict]:
    if not ids:
        return []
    j = _get("videos", {"part": "snippet,statistics,contentDetails", "id": ",".join(ids)}, token)
    out = []
    for it in j.get("items", []):
        dur = seconds(it["contentDetails"]["duration"])
        days = _iso_days(it["snippet"]["publishedAt"])
        views = int(it["statistics"].get("viewCount", 0))
        out.append({"id": it["id"], "title": it["snippet"]["title"],
                    "channel": it["snippet"]["channelTitle"],
                    "published": it["snippet"]["publishedAt"][:10],
                    "views": views, "dur_min": round(dur / 60, 1),
                    "days": round(days, 0), "views_per_day": round(views / days, 1)})
    return out


def market(token: str) -> dict:
    rows, seen = [], set()
    for q in QUERIES:
        for r in details(token, search(token, q)):
            if r["id"] in seen:
                continue
            seen.add(r["id"])
            r["query"] = q
            rows.append(r)
    return {"rows": rows}


def ours() -> list[dict]:
    from analytics import analytics as api
    start = (datetime.now(timezone.utc).replace(day=1)).strftime("%Y-%m-%d")
    end = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out = []
    for name, (env, cid) in CHANNELS.items():
        try:
            rows = api(access_token(env), start, end,
                       "views,averageViewDuration,averageViewPercentage",
                       dims="video", sort="-views", max_results=25)
        except Exception as exc:  # noqa: BLE001 - a dead read must not kill the report
            out.append({"channel": name, "error": str(exc)[:120]})
            continue
        for r in rows:  # columns follow the requested order: video, views, avg dur, avg %
            vid, views, avg_s, avg_pct = (list(r) + [0, 0, 0, 0])[:4]
            out.append({"channel": name, "video": vid, "views": int(views or 0),
                        "avg_view_pct": round(float(avg_pct or 0), 1),
                        "avg_view_sec": int(float(avg_s or 0))})
    return out


def render(m: dict | None, o: list[dict] | None) -> str:
    lines = [f"# Niche measurement — {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC",
             "", "Measured live from the YouTube Data/Analytics API (not from an article).", ""]
    if m:
        rows = sorted(m["rows"], key=lambda r: -r["views_per_day"])
        lines += ["## Market: top long-form results for our queries (sorted by views/day)", "",
                  "| views/day | views | min | days | published | channel | title |",
                  "|---:|---:|---:|---:|---|---|---|"]
        for r in rows[:40]:
            lines.append(f"| {r['views_per_day']:.0f} | {r['views']:,} | {r['dur_min']:.1f} | "
                         f"{r['days']:.0f} | {r['published']} | {r['channel'][:24]} | "
                         f"{r['title'][:70]} |")
        durs = [r["dur_min"] for r in rows if r["views_per_day"] > 50]
        if durs:
            durs.sort()
            lines += ["", f"- {len(durs)} videos beat 50 views/day; their median length is "
                          f"**{durs[len(durs) // 2]:.1f} min** "
                          f"(min {durs[0]:.1f}, max {durs[-1]:.1f})."]
    if o:
        lines += ["", "## Ours (this month, Analytics API)", "",
                  "| channel | views | avg view % | avg view s | video |", "|---|---:|---:|---:|---|"]
        for r in o:
            if "error" in r:
                lines.append(f"| {r['channel']} | — | — | — | error: {r['error']} |")
            else:
                lines.append(f"| {r['channel']} | {r['views']} | {r['avg_view_pct']} | "
                             f"{r['avg_view_sec']} | {r['video']} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--market", action="store_true")
    ap.add_argument("--ours", action="store_true")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    m = market(access_token(CHANNELS["dharma"][0])) if a.market else None
    o = ours() if a.ours else None
    text = render(m, o)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"wrote {a.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
