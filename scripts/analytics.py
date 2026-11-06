#!/usr/bin/env python3
"""Measured channel analytics -- the numbers that decide the next move.

The Data API gives views and durations, but not *watch time*. Watch time is the
metric YPP is built on, and it cannot be derived by multiplying duration by
views: that assumes every viewer watches the whole file, which is wrong by more
than an order of magnitude (measured 2026-11-04: the naive sum said 348 h; the
Analytics API says 31 h for the same year). This script reads the real figures.

The granted token scope is the full `youtube` scope, which the YouTube Analytics
API accepts -- so no extra consent is needed. Verified 2026-11-04 on all three
channel tokens.

    python3 scripts/analytics.py                 # all three channels, 28 days
    python3 scripts/analytics.py --days 365
    python3 scripts/analytics.py --channel dharma --videos
"""
from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone

CHANNELS = {
    "genx": ("YT_CH1_REFRESH_TOKEN", "UCI6EfsgM1HNjrYarvigxyrQ"),
    "dharma": ("YT_CH2_REFRESH_TOKEN", "UCM3QO5L_pmj34n1JVlbhh-w"),
    "kongkeat": ("YT_CH4_REFRESH_TOKEN", "UC7gCIu4G_7QCEJ8hJ-34zoQ"),
}


def _client() -> tuple:
    """(client_id, client_secret), from YT_CLIENT_ID/SECRET or the CLIENT_SECRET blob.

    The blob path means a plain agent session that only holds CLIENT_SECRET still
    works -- the same fallback yt_auth.py uses.
    """
    cid = (os.environ.get("YT_CLIENT_ID") or "").strip()
    secret = (os.environ.get("YT_CLIENT_SECRET") or "").strip()
    if cid and secret:
        return cid, secret
    raw = (os.environ.get("CLIENT_SECRET") or "").strip()
    if raw:
        doc = json.loads(raw)
        for key in ("web", "installed"):
            section = doc.get(key)
            if isinstance(section, dict) and section.get("client_id"):
                return section["client_id"], section["client_secret"]
    raise SystemExit("Set YT_CLIENT_ID + YT_CLIENT_SECRET, or CLIENT_SECRET.")


def access_token(env: str) -> str:
    cid, secret = _client()
    data = urllib.parse.urlencode({
        "client_id": cid, "client_secret": secret,
        "refresh_token": os.environ[env], "grant_type": "refresh_token"}).encode()
    with urllib.request.urlopen("https://oauth2.googleapis.com/token", data=data, timeout=30) as fh:
        return json.load(fh)["access_token"]


def analytics(token: str, start: str, end: str, metrics: str,
              dims: str = "", sort: str = "", max_results: int = 200) -> list:
    params = {"ids": "channel==MINE", "startDate": start, "endDate": end, "metrics": metrics}
    if dims:
        params["dimensions"] = dims
    if sort:
        params["sort"] = sort
    if max_results:
        params["maxResults"] = str(max_results)
    req = urllib.request.Request(
        "https://youtubeanalytics.googleapis.com/v2/reports?" + urllib.parse.urlencode(params),
        headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=60) as fh:
        return json.load(fh).get("rows", [])


def titles(token: str, ids: list[str]) -> dict:
    out = {}
    for i in range(0, len(ids), 50):
        req = urllib.request.Request(
            "https://www.googleapis.com/youtube/v3/videos?part=snippet,contentDetails&id="
            + ",".join(ids[i:i + 50]), headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req, timeout=30) as fh:
            for it in json.load(fh).get("items", []):
                out[it["id"]] = it["snippet"]["title"]
    return out


def report(name: str, token: str, start: str, end: str, show_videos: bool) -> dict:
    head = analytics(token, start, end,
                     "views,estimatedMinutesWatched,averageViewDuration,"
                     "averageViewPercentage,subscribersGained,subscribersLost")
    views = mw = sg = sl = 0.0
    if head:
        views, mw, _avg, _pct, sg, sl = head[0]
    hours = mw / 60.0
    print(f"\n=== {name}  ({start} .. {end})")
    print(f"  views={views:,.0f}   watch-hours={hours:,.1f}   subs +{sg:.0f}/-{sl:.0f}")
    if show_videos:
        # The Analytics endpoint has its own quota, so the per-video rows usually
        # come back even when the Data API (needed only for the titles) is spent.
        rows = analytics(token, start, end,
                         "views,estimatedMinutesWatched,averageViewDuration,"
                         "averageViewPercentage,subscribersGained",
                         dims="video", sort="-estimatedMinutesWatched", max_results=30)
        try:
            tmap = titles(token, [r[0] for r in rows]) if rows else {}
        except urllib.error.HTTPError as exc:
            print(f"  (titles skipped: {exc.code} — the Data API quota is spent)")
            tmap = {}
        print(f"  {'video_id':12s} {'views':>7s} {'watch-h':>8s} {'avg%':>7s} {'subs+':>6s}  title")
        for r in rows:
            vid, v, m, _d, pct, s = r
            flag = " ⟳loop" if pct and pct > 100 else ""
            print(f"  {vid:12s} {v:7.0f} {m/60:8.2f} {pct:6.1f}% {s:6.0f}  "
                  f"{tmap.get(vid, '?')[:38]}{flag}")
    return {"views": views, "watch_hours": hours, "subs_gained": sg, "subs_lost": sl}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", choices=list(CHANNELS))
    ap.add_argument("--days", type=int, default=28)
    ap.add_argument("--videos", action="store_true", help="per-video breakdown")
    ap.add_argument("--json", metavar="PATH", help="also write the totals to this file")
    args = ap.parse_args()

    end = date.today().isoformat()
    start = (date.today() - timedelta(days=args.days)).isoformat()
    names = [args.channel] if args.channel else list(CHANNELS)
    total_h = 0.0
    out = {"measured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "days": args.days, "start": start, "end": end, "channels": {}}
    for name in names:
        env, _cid = CHANNELS[name]
        try:
            r = report(name, access_token(env), start, end, args.videos)
            total_h += r["watch_hours"]
            out["channels"][name] = r
        except urllib.error.HTTPError as exc:
            print(f"\n=== {name}: FAILED {exc.code} {exc.read().decode()[:160]}")
    out["total_watch_hours"] = round(total_h, 2)
    print(f"\nTOTAL watch-hours across {len(names)} channel(s), {args.days} d: {total_h:,.1f}")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(out, fh, ensure_ascii=False, indent=2)
        print(f"wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
