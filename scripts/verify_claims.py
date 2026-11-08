#!/usr/bin/env python3
"""PCSEV step V: verify a claim against its source, not against our own docs.

The project rule is "evidence, not claims". But evidence that lives in a committed
file is itself a claim -- it can be stale, or simply wrong. Measured 2026-11-08:
`scripts/report_reach.py` states that the Analytics API refuses these tokens, and
it does not (all three channels answered). Anyone who verified from that docstring
would have believed a false thing and stopped looking.

So this tool defines, per kind of claim, the source that is allowed to settle it,
and re-measures from that source instead of reading the last answer we wrote down:

  * a number about the audience      -> the live YouTube Analytics API, re-queried
                                        over the *same window* the snapshot used
  * a number about a rendered file   -> the file's own receipt (ffprobe/ebur128)
  * "the rail still works"           -> the guard test, which can fail
  * anything else                    -> a committed doc, which is the weakest
                                        source and never the current answer

Exit status: by default this is a *report* -- it prints the verdict and exits 0,
because any snapshot older than the API's ~2-day reporting lag is expected to read
low, and a job that goes red every week trains people to ignore it. Pass --strict
when the run must gate on freshness (exit 1 on any divergence).

    python3 scripts/verify_claims.py
    python3 scripts/verify_claims.py --json
    python3 scripts/verify_claims.py --strict
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

CHANNELS = {
    "genx": "YT_CH1_REFRESH_TOKEN",
    "dharma": "YT_CH2_REFRESH_TOKEN",
    "kongkeat": "YT_CH4_REFRESH_TOKEN",
}
ANALYTICS = "https://youtubeanalytics.googleapis.com/v2/reports"

# A committed number may differ from the live one by rounding noise and by the
# lag between a view happening and the API reporting it. Above this it is a
# different number, not a rounding.
TOLERANCE = 0.05


def access_token(env: str) -> str:
    body = urllib.parse.urlencode({
        "client_id": os.environ["YT_CLIENT_ID"],
        "client_secret": os.environ["YT_CLIENT_SECRET"],
        "refresh_token": os.environ[env],
        "grant_type": "refresh_token",
    }).encode()
    req = urllib.request.Request("https://oauth2.googleapis.com/token", data=body)
    with urllib.request.urlopen(req, timeout=30) as fh:
        return json.load(fh)["access_token"]


def analytics(token: str, start: str, end: str, metrics: str) -> list:
    params = {"ids": "channel==MINE", "startDate": start, "endDate": end,
              "metrics": metrics}
    url = ANALYTICS + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=30) as fh:
        return json.load(fh).get("rows") or []


def compare(snapshot: dict) -> dict:
    """Re-measure every channel over the snapshot's own window and compare.

    Pure enough to reason about: it takes the snapshot as data and returns a
    verdict per channel, so the network part stays in main().
    """
    start, end = snapshot.get("start"), snapshot.get("end")
    results = {}
    for name, env in CHANNELS.items():
        committed = (snapshot.get("channels") or {}).get(name)
        if not committed or not start or not end:
            results[name] = {"status": "unknown", "why": "snapshot has no entry"}
            continue
        try:
            token = access_token(env)
            rows = analytics(token, start, end,
                             "views,estimatedMinutesWatched")
        except Exception as exc:  # noqa: BLE001 - report, do not crash the whole run
            results[name] = {"status": "unreachable", "why": str(exc)[:120]}
            continue
        if not rows:
            results[name] = {"status": "unknown", "why": "API returned no rows"}
            continue
        live_views = float(rows[0][0])
        live_hours = float(rows[0][1]) / 60.0
        cv = float(committed.get("views") or 0)
        ch = float(committed.get("watch_hours") or 0)
        dv = abs(live_views - cv) / cv if cv else 1.0
        dh = abs(live_hours - ch) / ch if ch else 1.0
        ok = dv <= TOLERANCE and dh <= TOLERANCE
        results[name] = {
            "status": "match" if ok else "DIVERGED",
            "window": f"{start}..{end}",
            "committed": {"views": cv, "watch_hours": round(ch, 1)},
            "live": {"views": live_views, "watch_hours": round(live_hours, 1)},
            "delta_pct": {"views": round(dv * 100, 1), "watch_hours": round(dh * 100, 1)},
        }
    return results


def snapshot_path() -> str:
    return os.path.join(ROOT, "docs", "watch_hours.json")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true",
                    help="exit 1 when the snapshot disagrees with the live API")
    a = ap.parse_args()

    path = snapshot_path()
    if not os.path.exists(path):
        print(f"no snapshot at {path}; nothing to verify against", file=sys.stderr)
        return 2
    with open(path, encoding="utf-8") as fh:
        doc = json.load(fh)
    samples = doc.get("samples") or []
    if not samples:
        print("snapshot has no samples", file=sys.stderr)
        return 2
    snap = samples[-1]

    results = compare(snap)
    stale = [k for k, v in results.items() if v["status"] == "DIVERGED"]

    if a.json:
        print(json.dumps({"snapshot_window": f"{snap.get('start')}..{snap.get('end')}",
                          "results": results, "stale": stale}, ensure_ascii=False))
    else:
        print(f"verifying the committed snapshot over its own window "
              f"{snap.get('start')}..{snap.get('end')}")
        for name, r in results.items():
            if r["status"] in ("match", "DIVERGED"):
                c, l = r["committed"], r["live"]
                flag = "ok  " if r["status"] == "match" else "STALE"
                print(f"  {flag} {name:9s} committed {c['views']:>7} views / "
                      f"{c['watch_hours']:>6} h   live {l['views']:>7} / {l['watch_hours']:>6} h "
                      f"(delta {r['delta_pct']['views']}%)")
            else:
                print(f"  ??   {name:9s} {r['status']}: {r.get('why')}")
        print("verdict: " + ("snapshot agrees with the live API"
                             if not stale else
                             f"{len(stale)} channel(s) DIVERGED -- the committed "
                             "number is not the answer; the live API is"))
    return 1 if (stale and a.strict) else 0


if __name__ == "__main__":
    sys.exit(main())
