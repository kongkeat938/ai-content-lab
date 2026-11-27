#!/usr/bin/env python3
"""Read the D10 verdict: did any of the five top long-forms gain SHORTS views?

The CTA comment sends a viewer to the playlist, not to one video, so the click
can land on any of the long-forms in it. Measuring a single video would
undercount; measuring the five biggest is the agreed floor.

    python3 scripts/measure_d10.py                 # dharma, since the comment
    python3 scripts/measure_d10.py --days 2 --json

Exit codes: 0 = at least one long-form gained SHORTS views (pipe works),
3 = every one of the five is still zero (do not backfill), 2 = BLIND (the query
itself failed -- a dead query must never read as "no traffic").
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

BASELINE = {"dharma": "content/baseline_dharma_20261126.json",
            "genx": "content/baseline_genx_20261126.json",
            "kongkeat-story": "content/baseline_kongkeat_20261126.json"}
CHANNEL_ID = {"dharma": "UCM3QO5L_pmj34n1JVlbhh-w",
              "genx": "UCI6EfsgM1HNjrYarvigxyrQ",
              "kongkeat-story": "UC7gCIu4G_7QCEJ8hJ-34zoQ"}


def shorts_views(yta, video_id: str, start: str, end: str) -> int | None:
    """SHORTS views for one video, or None when the query itself failed."""
    from googleapiclient.errors import HttpError
    try:
        r = yta.reports().query(ids="channel==MINE", startDate=start, endDate=end,
                                metrics="views", dimensions="insightTrafficSourceType",
                                filters=f"video=={video_id}").execute()
    except HttpError as exc:
        print(f"BLIND: {video_id} query failed HTTP {exc.resp.status}", file=sys.stderr)
        return None
    return sum(row[1] for row in r.get("rows", []) if row[0] == "SHORTS")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--slug", default="dharma", choices=list(BASELINE))
    ap.add_argument("--baseline")
    ap.add_argument("--days", type=int, default=0,
                    help="window length; 0 = from the test comment to today")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    path = args.baseline or os.path.join(ROOT, BASELINE[args.slug])
    with open(path, encoding="utf-8") as fh:
        doc = json.load(fh)
    top = doc.get("d10_top5_longforms") or []
    if not top:
        print(f"refusing: {path} has no d10_top5_longforms", file=sys.stderr)
        return 2

    start = (doc.get("test_comment") or {}).get("posted_utc", "")[:10] or "2026-11-01"
    today = dt.date.today()
    end = (today - dt.timedelta(days=1)).isoformat()
    if args.days:
        start = (today - dt.timedelta(days=args.days)).isoformat()

    import yt_auth
    from googleapiclient.discovery import build
    creds = yt_auth.load_credentials(CHANNEL_ID[args.slug])
    yta = build("youtubeAnalytics", "v2", credentials=creds, cache_discovery=False)

    rows, blind = [], False
    for item in top:
        vid = item["video_id"]
        now = shorts_views(yta, vid, start, end)
        if now is None:
            blind = True
            continue
        before = item.get("shorts_feed_views") or 0
        rows.append({"video_id": vid, "title": item.get("title", ""),
                     "views": item.get("views", 0), "shorts_before": before,
                     "shorts_now": now, "delta": now - before})

    if args.json:
        print(json.dumps({"slug": args.slug, "window": [start, end], "rows": rows,
                          "blind": blind}, ensure_ascii=False, indent=1))
    else:
        print(f"D10 {args.slug} · window {start}..{end}")
        print(f"{'video':14} {'views':>6} {'SHORTS':>7} {'before':>7} {'delta':>6}  title")
        for r in rows:
            print(f"{r['video_id']:14} {r['views']:>6} {r['shorts_now']:>7} "
                  f"{r['shorts_before']:>7} {r['delta']:>+6}  {r['title'][:44]}")

    if blind:
        return 2
    gained = [r for r in rows if r["delta"] > 0]
    if gained:
        print(f"PIPE WORKS: {len(gained)} of {len(rows)} long-forms gained SHORTS views "
              f"({', '.join(r['video_id'] for r in gained)})")
        return 0
    print(f"ALL ZERO: none of {len(rows)} long-forms gained SHORTS views -- do not backfill")
    return 3


if __name__ == "__main__":
    sys.exit(main())
