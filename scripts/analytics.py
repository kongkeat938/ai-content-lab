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

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yt_duration

import argparse
import json
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


def durations(token: str, ids: list[str]) -> dict:
    """Map video id -> length in seconds, from the Data API's ISO-8601 duration."""
    out = {}
    for i in range(0, len(ids), 50):
        req = urllib.request.Request(
            "https://www.googleapis.com/youtube/v3/videos?part=contentDetails&id="
            + ",".join(ids[i:i + 50]), headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req, timeout=30) as fh:
            for it in json.load(fh).get("items", []):
                out[it["id"]] = yt_duration.seconds(
                    it["contentDetails"]["duration"])
    return out


def retention_curve(token: str, cid: str, video_id: str, days: int = 90) -> list:
    """The audience-retention curve for one video: [(ratio, watch_ratio), ...].

    This is the measurement that decides the growth question. The video's opening
    is where a calm long-form loses its audience -- measured 2026-11-08, 71% of
    starters left a 120-minute file within two minutes -- so the number to watch
    is the watch ratio at the two-minute mark, not the total view count.
    """
    start = (date.today() - timedelta(days=days)).isoformat()
    end = date.today().isoformat()
    params = {"ids": "channel==" + cid, "startDate": start, "endDate": end,
              "metrics": "audienceWatchRatio", "dimensions": "elapsedVideoTimeRatio",
              "filters": "video==" + video_id}
    req = urllib.request.Request(
        "https://youtubeanalytics.googleapis.com/v2/reports?" + urllib.parse.urlencode(params),
        headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=60) as fh:
        return json.load(fh).get("rows", [])


def retention_at(token: str, cid: str, video_id: str, seconds: int,
                 duration_s: float) -> float | None:
    """The watch ratio (percent) at `seconds` into `video_id`, or None if unknown."""
    rows = retention_curve(token, cid, video_id)
    if not rows or duration_s <= 0:
        return None
    target = seconds / duration_s
    return min(rows, key=lambda r: abs(r[0] - target))[1] * 100.0


def content_type_hours(token: str, cid: str, start: str, end: str) -> dict:
    """Watch time split by content type: long-form vs Shorts.

    The channel total mixes both, and only long-form counts toward YPP's
    4,000-hour bar -- Shorts have their own path (10M views / 90 days). Measured
    2026-11-09: on genx 99% of watch time was Shorts, so the channel total said
    39% of the YPP bar while the qualifying number was 0.4%. The split is what
    keeps the tracker honest.
    """
    params = {"ids": "channel==" + cid, "startDate": start, "endDate": end,
              "metrics": "estimatedMinutesWatched", "dimensions": "creatorContentType"}
    req = urllib.request.Request(
        "https://youtubeanalytics.googleapis.com/v2/reports?" + urllib.parse.urlencode(params),
        headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=60) as fh:
            rows = json.load(fh).get("rows", [])
    except urllib.error.HTTPError:
        return {}
    return {row[0]: row[1] for row in rows}   # e.g. {'shorts': 2126.0, 'videoOnDemand': 2664.0}


def report(name: str, token: str, start: str, end: str, show_videos: bool) -> dict:
    head = analytics(token, start, end,
                     "views,estimatedMinutesWatched,averageViewDuration,"
                     "averageViewPercentage,subscribersGained,subscribersLost")
    views = mw = sg = sl = 0.0
    if head:
        views, mw, _avg, _pct, sg, sl = head[0]
    hours = mw / 60.0
    # Split long-form from Shorts: only long-form counts toward YPP's 4,000 h.
    env, cid = CHANNELS[name]
    split = content_type_hours(token, cid, start, end)
    lf_hours = split.get("videoOnDemand", 0.0) / 60.0
    sh_hours = split.get("shorts", 0.0) / 60.0
    print(f"\n=== {name}  ({start} .. {end})")
    print(f"  views={views:,.0f}   watch-hours={hours:,.1f}   subs +{sg:.0f}/-{sl:.0f}")
    print(f"  long-form={lf_hours:,.1f} h (YPP-qualifying)   Shorts={sh_hours:,.1f} h")
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
    return {"views": views, "watch_hours": hours,
            "longform_watch_hours": round(lf_hours, 2),
            "shorts_watch_hours": round(sh_hours, 2),
            "subs_gained": sg, "subs_lost": sl}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", choices=list(CHANNELS))
    ap.add_argument("--days", type=int, default=28)
    ap.add_argument("--videos", action="store_true", help="per-video breakdown")
    ap.add_argument("--retention", action="store_true",
                    help="long-form videos: retention at 2:00 (the growth metric)")
    ap.add_argument("--json", metavar="PATH", help="also write the totals to this file")
    args = ap.parse_args()

    end = date.today().isoformat()
    start = (date.today() - timedelta(days=args.days)).isoformat()
    names = [args.channel] if args.channel else list(CHANNELS)
    total_h = 0.0
    total_lf = 0.0
    out = {"measured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "days": args.days, "start": start, "end": end, "channels": {}}
    for name in names:
        env, _cid = CHANNELS[name]
        try:
            r = report(name, access_token(env), start, end, args.videos)
            total_h += r["watch_hours"]
            total_lf += r.get("longform_watch_hours", 0.0)
            out["channels"][name] = r
        except urllib.error.HTTPError as exc:
            print(f"\n=== {name}: FAILED {exc.code} {exc.read().decode()[:160]}")

    if args.retention:
        # The panel's number to watch for seven days: retention at 2:00 on each
        # long-form. Above ~40% the opening works; below 30% after three uploads
        # the niche is wrong, not the script. Long-form only -- a Short has no
        # two-minute mark to speak of, and its watch time does not count anyway.
        print("\n=== retention at 2:00 (long-form only) ===")
        for name in names:
            env, cid = CHANNELS[name]
            tok = access_token(env)
            try:
                rows = analytics(tok, start, end,
                                 "views,estimatedMinutesWatched,averageViewDuration,"
                                 "averageViewPercentage",
                                 dims="video", sort="-views", max_results=50)
            except urllib.error.HTTPError as exc:
                print(f"  {name}: FAILED {exc.code}")
                continue
            longforms = [r for r in rows if r[3] >= 300]   # >= 5 min avg view
            # Duration from the Analytics API, not the Data API: duration =
            # averageViewDuration / (averageViewPercentage/100). The Data API is
            # spent most days here, so a durations() call returns nothing and the
            # retention number silently reads n/a -- the KPI would be dark.
            try:
                durs = durations(tok, [r[0] for r in longforms])
            except urllib.error.HTTPError:
                durs = {}
            best = None
            for vid, v, _m, avd, avpct in longforms:
                d = durs.get(vid, 0)
                if not d and avd and avpct and avpct > 0:
                    d = avd / (avpct / 100.0)
                pct = retention_at(tok, cid, vid, 120, d) if d else None
                tag = f"{pct:5.1f}%" if pct is not None else "  n/a"
                print(f"  {name:9s} {vid}  views={v:>4.0f}  "
                      f"dur={d/60:>5.1f}m  retention@2min={tag}")
                # The KPI is the channel's best-viewed long-form: the opening of the
                # video most people actually see. Views-weight it, so a big video
                # with a working opening is not outvoted by an unseen one.
                if pct is not None and (best is None or v > best[0]):
                    best = (v, pct, vid)
            if best:
                out["channels"].setdefault(name, {})["retention_2min"] = round(best[1], 1)
                out["channels"][name]["retention_2min_video"] = best[2]
                out["channels"][name]["retention_2min_views"] = best[0]

    out["total_watch_hours"] = round(total_h, 2)
    out["total_longform_watch_hours"] = round(total_lf, 2)
    print(f"\nTOTAL watch-hours across {len(names)} channel(s), {args.days} d: "
          f"{total_h:,.1f}  (long-form / YPP-qualifying: {total_lf:,.1f})")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(out, fh, ensure_ascii=False, indent=2)
        print(f"wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
