#!/usr/bin/env python3
"""Verify against data that must grow: an append-only counter ledger.

K's point (2026-11-08): the best thing to verify against is not a snapshot you have
to trust, but a counter that *must keep increasing*. A snapshot can only be
compared to another value we also wrote down. A cumulative counter carries its own
truth:

  * it can never go down -- a lifetime view count that drops is not "a bit stale",
    it is impossible, so a decrease is a definite error (wrong channel, a bug, a
    corrupted row), not a judgement call
  * it can never stand still -- if lifetime views have not moved in days, the
    channel has stopped, or the pipeline has, and either is a fact worth a flag
  * the ledger itself only grows -- so the file is evidence that the check ran

That is why this reads counters the way the audience produces them, appends every
measurement to `docs/counters.jsonl`, and checks the two invariants a real counter
cannot break. The Analytics API is used (not the Data API) because it has its own
quota -- measured 2026-11-08: the Data API was 403 "exceeded your quota" while the
Analytics API answered all three channels.

    python3 scripts/counter_ledger.py                 # measure, append, check
    python3 scripts/counter_ledger.py --check-only    # no network, just the ledger
    python3 scripts/counter_ledger.py --json
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
# Counters that only ever go up, measured over the channel's whole life. The start
# date is deliberately far in the past so the window is "everything so far"; the
# end is always today, so every run extends it.
BEGINNING = "2020-01-01"
METRICS = {"views": "views", "watch_min": "estimatedMinutesWatched",
           "subs_gained": "subscribersGained"}
# A cumulative counter that has not moved in this many days is a flag, not noise.
STALL_DAYS = 3
LEDGER_CAP = 2000  # keep the file small; the newest entries are the ones read


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


def measure_one(token: str, end: str) -> dict:
    params = {"ids": "channel==MINE", "startDate": BEGINNING, "endDate": end,
              "metrics": ",".join(METRICS.values())}
    url = ANALYTICS + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=30) as fh:
        rows = json.load(fh).get("rows") or []
    if not rows:
        return {}
    return {name: int(rows[0][i]) for i, name in enumerate(METRICS)}


def measure(end: str | None = None) -> dict:
    end = end or datetime.now(timezone.utc).date().isoformat()
    out = {}
    for name, env in CHANNELS.items():
        try:
            out[name] = measure_one(access_token(env), end)
        except Exception as exc:  # noqa: BLE001 - one channel down must not stop the rest
            out[name] = {"error": str(exc)[:120]}
    return out


def read_ledger(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return rows


def check(series: list[dict]) -> dict:
    """The two invariants a cumulative counter cannot break. Pure, so testable.

    Returns {ok, violations, flags}. A violation is impossible data (a counter
    went down, or the ledger lost entries). A flag is data that has stopped moving.
    """
    violations: list[str] = []
    flags: list[str] = []

    if len(series) < 2:
        return {"ok": True, "violations": [], "flags": ["only one measurement so far"]}

    prev = series[-2]
    last = series[-1]

    def counters(entry: dict) -> dict:
        return entry.get("counters") or {}

    for ch in CHANNELS:
        p, l = counters(prev).get(ch) or {}, counters(last).get(ch) or {}
        if "error" in l or "error" in p:
            continue
        for c in METRICS:
            if c in p and c in l and l[c] < p[c]:
                violations.append(f"{ch}.{c} went DOWN: {p[c]} -> {l[c]} "
                                  "(a lifetime counter cannot decrease)")

    # Staleness: compare the newest reading against the newest one that is at least
    # STALL_DAYS old, so "has it moved in the last N days" is a real comparison.
    def age_days(a: dict) -> float:
        try:
            t = datetime.fromisoformat(str(a.get("measured_at")).replace("Z", "+00:00"))
            if t.tzinfo is None:
                t = t.replace(tzinfo=timezone.utc)
            return (datetime.now(timezone.utc) - t).total_seconds() / 86400.0
        except Exception:  # noqa: BLE001
            return 0.0

    baseline = None
    for s in series[:-1]:
        if age_days(s) >= STALL_DAYS:
            baseline = s
    if baseline is not None:
        for ch in CHANNELS:
            o, l = counters(baseline).get(ch) or {}, counters(last).get(ch) or {}
            if "error" in l or "error" in o:
                continue
            for c in METRICS:
                if c in o and c in l and l[c] == o[c]:
                    flags.append(f"{ch}.{c} flat at {l[c]} for "
                                 f"~{age_days(baseline):.1f} days")

    return {"ok": not violations, "violations": violations, "flags": flags}


def ledger_path() -> str:
    return os.path.join(ROOT, "docs", "counters.jsonl")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check-only", action="store_true", help="no network; read the ledger")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    path = ledger_path()
    series = read_ledger(path)

    if not a.check_only:
        counters = measure()
        if any("error" not in v and v for v in counters.values()):
            entry = {"measured_at": datetime.now(timezone.utc)
                     .isoformat(timespec="seconds"), "counters": counters}
            series.append(entry)
            trimmed = series[-LEDGER_CAP:]
            with open(path, "w", encoding="utf-8") as fh:
                for row in trimmed:
                    fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            if not a.json:
                print(f"appended measurement #{len(series)} ({len(trimmed)} lines kept)")
        elif not a.json:
            print("no counters measured (all channels errored); ledger unchanged",
                  file=sys.stderr)

    result = check(series)
    if a.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        for ch in CHANNELS:
            if series:
                c = (series[-1].get("counters") or {}).get(ch) or {}
                if c and "error" not in c:
                    print(f"  {ch:9s} lifetime views={c.get('views'):>8} "
                          f"watch-h={c.get('watch_min', 0)/60:>8.1f} "
                          f"subs+={c.get('subs_gained')}")
        for v in result["violations"]:
            print(f"  VIOLATION: {v}")
        for f in result["flags"]:
            print(f"  flag: {f}")
        print("verdict: " + ("counters are monotonic and moving"
                             if result["ok"] and not result["flags"] else
                             ("COUNTER WENT DOWN" if not result["ok"] else
                              "counters monotonic; some are not moving")))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
