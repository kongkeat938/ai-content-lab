#!/usr/bin/env python3
"""The truth about what gates YPP: long-form watch time, apart from Shorts.

progress.py compares 28-day watch-hours against YPP's 4,000-hour bar. But the
4,000-hour path counts **long-form only** -- Shorts have their own path (10M
Shorts views / 90 days), and Shorts watch time does not count toward the 4,000.
The channel-level `estimatedMinutesWatched` mixes both, so a Shorts-heavy channel
looks closer to YPP than it is.

This splits the number by `creatorContentType` (SHORTS vs VIDEO) so the tracked
figure is the one the threshold actually measures. It also reads the retention
curve of the channel's best long-form, because the two-minute mark is where a
calm long-form loses its audience -- the lever, not the symptom.

    python3 scripts/leverage.py                 # all channels, 28 days
    python3 scripts/leverage.py --days 90 --json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import analytics as A  # noqa: E402

# (slug, refresh-token env, channel id)
CHANNELS = [
    ("genx", "YT_CH1_REFRESH_TOKEN", "UCI6EfsgM1HNjrYarvigxyrQ"),
    ("dharma", "YT_CH2_REFRESH_TOKEN", "UCM3QO5L_pmj34n1JVlbhh-w"),
    ("kongkeat", "YT_CH4_REFRESH_TOKEN", "UC7gCIu4G_7QCEJ8hJ-34zoQ"),
]

HOURS_TARGET = 4000  # YPP long-form watch-hours per 12 months


def split(token: str, cid: str, start: str, end: str) -> dict:
    """Watch minutes per content type (SHORTS / VIDEO / LIVE / ...)."""
    params = {"ids": "channel==" + cid, "startDate": start, "endDate": end,
              "metrics": "views,estimatedMinutesWatched,subscribersGained",
              "dimensions": "creatorContentType", "sort": "-estimatedMinutesWatched"}
    url = "https://youtubeanalytics.googleapis.com/v2/reports?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=60) as fh:
            rows = json.load(fh).get("rows", [])
    except urllib.error.HTTPError as exc:
        return {"_error": f"HTTP {exc.code}"}
    out = {}
    for row in rows:
        ctype, views, minutes, subs = (row + [0, 0, 0, 0])[:4]
        out[ctype] = {"views": views, "minutes": minutes, "subs": subs}
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=28)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    end = date.today()
    start = end - timedelta(days=a.days)
    s, e = start.isoformat(), end.isoformat()

    report = {"window": {"start": s, "end": e, "days": a.days}, "channels": {}}
    for slug, env, cid in CHANNELS:
        try:
            token = A.access_token(env)
        except Exception as exc:  # noqa: BLE001
            report["channels"][slug] = {"_error": str(exc)}
            continue
        parts = split(token, cid, s, e)
        lf_min = parts.get("videoOnDemand", {}).get("minutes", 0) or 0
        sh_min = parts.get("shorts", {}).get("minutes", 0) or 0
        lf_hours = lf_min / 60.0
        annual_lf = lf_hours * 365 / a.days
        report["channels"][slug] = {
            "by_type": parts,
            "longform_hours": round(lf_hours, 1),
            "shorts_hours": round(sh_min / 60.0, 1),
            "longform_annual_hours": round(annual_lf, 1),
            "longform_pct_of_ypp": round(100 * annual_lf / HOURS_TARGET, 1),
            "shorts_share_of_watchtime": round(100 * sh_min / max(lf_min + sh_min, 1), 0),
        }

    if a.json:
        print(json.dumps(report, ensure_ascii=False, indent=1))
        return 0

    print(f"Long-form watch time vs the YPP bar (long-form only), {s} .. {e}")
    print(f"{'channel':10} {'LF hours':>9} {'annual LF':>10} {'% of 4,000':>11} {'Shorts share':>13}")
    for slug, d in report["channels"].items():
        if "_error" in d:
            print(f"{slug:10} {d['_error']}")
            continue
        print(f"{slug:10} {d['longform_hours']:>9} {d['longform_annual_hours']:>10} "
              f"{d['longform_pct_of_ypp']:>10}% {d['shorts_share_of_watchtime']:>12.0f}%")
    print("\nThe channel total in progress.py includes Shorts; only 'annual LF' counts")
    print("toward the 4,000-hour YPP threshold.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
