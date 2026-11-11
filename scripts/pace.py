#!/usr/bin/env python3
"""Pace the Shorts drip, and grade the last post before making the next one.

K's rule (2026-11-09): post one clip, wait two to three hours, then look at how
the last one did before posting the next. Good reception -> keep the shape. Bad
reception -> change it. Never post several at once, and never repeat a shape that
is not working. The cap in `publish_shorts.py` stops a *flood*; it cannot express
"wait and check", because a cap only counts posts, it does not read their result.
This module adds that gate:

  1. `gate()` refuses the next post until MIN_GAP_HOURS have passed since the last
     one (the 2-3 h spacing), and meanwhile grades the last post's reception.
  2. `order()` uses that verdict: a good post keeps the winning shape at the front
     of the queue, a bad one moves the *other* shape to the front so the next clip
     is a change, not a repeat.

Reception is views-per-hour now against the channel's own median views-per-hour
(measured from the videos' current view counts and ages). It is a proxy, and an
honest one: it asks "is this clip outrunning the channel's steady rate?", which is
the question K's loop needs. It is not a retention curve -- `analytics.py` and
`video_review.py` own that.

    python3 scripts/pace.py --channel dharma          # grade + say if due
    python3 scripts/pace.py --channel dharma --json

Writes content/reception/<channel>.json so the verdict is on the record and the
next run reads the same number. No secret needed for the gap check; the grade
needs the channel's token (YT_CH*_REFRESH_TOKEN) and is skipped, not faked, when
that is absent or the Data API quota is spent.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

MIN_GAP_HOURS = 2.0          # the floor of K's 2-3 h window; the 30-min foreman tick
                             # supplies the jitter above it, so gaps land in 2-3 h.
MIN_BASELINE_CLIPS = 3       # below this the median is noise, so the verdict is unknown
BASELINE_MIN_AGE_H = 12.0    # only clips older than this inform the steady rate
GOOD_QUANTILE = 0.75         # "good" = at least the channel's upper quartile (see _quantile)
# The feed-suppression guard (2026-11-10). A new channel can be *withheld* by the
# Shorts feed, not merely ignored: kongkeat's feed views fell from 4,340 in six days
# to 6 in four, and its last 37 clips sat at 0-2 views while its first 14 held
# 40-242. That is reach removed, not a weak hook, and repeating the same clip makes
# it worse. A clip the feed never showed sits at <= this many views.
SUPPRESS_VIEWS = 5
STALL_LOOKBACK = 5           # this many flat clips in a row = the feed stopped
STALL_COOLDOWN_H = 20.0      # after this pause, post ONE changed clip as a probe

RECEPTION_DIR = os.path.join(ROOT, "content", "reception")


def now() -> datetime:
    return datetime.now(timezone.utc)


def parse(iso: str) -> datetime:
    return datetime.fromisoformat(str(iso).replace("Z", "+00:00"))


def _load(path: str, default):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def reception_path(slug: str) -> str:
    return os.path.join(RECEPTION_DIR, f"{slug}.json")


def access_token(env: str) -> str:
    data = urllib.parse.urlencode({
        "client_id": os.environ["YT_CLIENT_ID"],
        "client_secret": os.environ["YT_CLIENT_SECRET"],
        "refresh_token": os.environ[env],
        "grant_type": "refresh_token"}).encode()
    with urllib.request.urlopen("https://oauth2.googleapis.com/token", data=data,
                                timeout=30) as fh:
        return json.load(fh)["access_token"]


def stats(token: str, ids: list[str]) -> dict:
    """Current view count, likes, comments + publish time for up to 50 ids, one call.

    Likes and comments come back in the same request as the view count, so a young
    channel can read engagement the same day instead of waiting 1-2 days for the
    Analytics subscriber number (K, 2026-11-10: a new channel must be read in hours,
    not days). Returns {} on a spent quota (403) rather than raising: the gate must
    degrade to "unknown", never invent a grade, and never break the publish rail.
    """
    if not ids:
        return {}
    q = urllib.parse.urlencode({"part": "statistics,snippet",
                                "id": ",".join(ids[:50]), "maxResults": "50"})
    req = urllib.request.Request(f"https://www.googleapis.com/youtube/v3/videos?{q}",
                                 headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as fh:
            items = json.load(fh).get("items", [])
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
        return {}
    out = {}
    for it in items:
        st = it.get("statistics", {})
        out[it["id"]] = {
            "views": int(st.get("viewCount", 0)),
            "likes": int(st.get("likeCount", 0)),
            "comments": int(st.get("commentCount", 0)),
            "published_at": it.get("snippet", {}).get("publishedAt"),
        }
    return out


def analytics_views(token: str, days: int = 90) -> dict:
    """Views per video from the Analytics API -- its own quota, separate from the
    Data API's.

    This is the quota-safe source. The Data API's shared pool is spent most days
    here, which is exactly when the learning loop must keep working; the Analytics
    quota answers on those days (measured 2026-11-09, Data API 403 while Analytics
    returned rows). Returns {} on any failure so the caller can degrade.
    """
    end = now().date()
    start = end - timedelta(days=days)
    q = urllib.parse.urlencode({
        "ids": "channel==MINE", "startDate": str(start), "endDate": str(end),
        "metrics": "views", "dimensions": "video", "sort": "-views",
        "maxResults": "200"})
    req = urllib.request.Request(
        "https://youtubeanalytics.googleapis.com/v2/reports?" + q,
        headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=40) as fh:
            rows = json.load(fh).get("rows", [])
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
        return {}
    return {r[0]: int(r[1]) for r in rows}


def _median(xs: list[float]) -> float:
    xs = sorted(xs)
    n = len(xs)
    if not n:
        return 0.0
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2.0


def _quantile(xs: list[float], q: float) -> float:
    """Linear-interpolated quantile. Used for the "worth repeating" bar.

    The bar is the upper quartile, not the median: half this channel's clips sit
    at zero views, so the median is near zero and would call almost anything
    "good" (measured 2026-11-09: a clip with 2 views in 3 h cleared a median bar of
    0.5/h). "Good" must mean "doing as well as the clips worth making more of",
    which is the top quarter, not the middle.
    """
    xs = sorted(xs)
    if not xs:
        return 0.0
    if len(xs) == 1:
        return xs[0]
    pos = q * (len(xs) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def _posted_entries(man: dict) -> list[tuple[str, dict]]:
    """The manifest's live Shorts in the order they were recorded (last = newest)."""
    shorts = man.get("shorts", {})
    return [(sid, v) for sid, v in shorts.items() if v.get("video_id")]


def _last_posted(man: dict, live: dict) -> tuple[str, dict] | None:
    """The most recently posted Short, by recorded time, else by YouTube's clock."""
    entries = _posted_entries(man)
    if not entries:
        return None
    with_ts = [(sid, v) for sid, v in entries if v.get("posted_at")]
    if with_ts:
        return max(with_ts, key=lambda kv: parse(kv[1]["posted_at"]))
    dated = [(sid, v) for sid, v in entries
             if live.get(v["video_id"], {}).get("published_at")]
    if dated:
        return max(dated, key=lambda kv: parse(live[kv[1]["video_id"]]["published_at"]))
    return entries[-1]          # nothing to order by: trust insertion order


def hook_shape(script: dict, cues) -> str:
    """The channel's measured shape split: a concrete-action hook, or a plain one.

    For dharma the winners all carry a cue word ("ลอง" / "คืนนี้" / "เปิดทิ้งไว้")
    -- see docs/HOOKS-MEASURED.md. That binary is the axis this loop explores:
    a good post keeps the cue shape, a bad one tries the other side.
    """
    if cues and any(c in script.get("hook", "") for c in cues):
        return "cue"
    return "plain"


def grade(per_hour: float, baseline: float, n_baseline: int) -> str:
    if n_baseline < MIN_BASELINE_CLIPS:
        return "unknown"
    return "good" if per_hour >= baseline else "bad"


def detect_stall(entries: list, views: dict, now_dt=None, lookback: int = STALL_LOOKBACK,
                 threshold: int = SUPPRESS_VIEWS) -> dict:
    """Has the Shorts feed stopped showing this channel at all?

    Distinct from "bad reception": a bad clip still gets *some* feed views. A
    suppressed channel's newest clips sit at ~0 views, because the feed is not
    showing them, and posting more of the same is the one thing that deepens the
    suppression (a five-advisor panel was unanimous, 2026-11-10). So this reads the
    newest `lookback` clips: if they are ALL at or under `threshold`, the feed is
    off and the caller should pause and change shape, not keep posting.

    `entries` are (sid, manifest-entry) pairs oldest-first; `views` maps video_id to
    a current view count. A clip with no view count (spent quota) is skipped, not
    counted as zero -- an unknown is not evidence of suppression.
    """
    now_dt = now_dt or now()
    counted, last_ts = [], None
    for sid, v in reversed(entries):
        w = views.get(v.get("video_id"))
        if w is None:
            continue
        counted.append((sid, w))
        if len(counted) >= lookback:
            break
    if len(counted) < lookback:
        return {"stalled": False, "flat": len(counted), "reason": "too few clips to judge"}
    if any(w > threshold for _, w in counted):
        return {"stalled": False, "flat": sum(1 for _, w in counted if w <= threshold)}
    # Every recent clip is flat. The newest clip's age tells us how long the feed
    # has been off; past the cooldown we allow one changed probe.
    last_sid = counted[0][0]
    for sid, v in reversed(entries):
        if sid == last_sid:
            ts = v.get("posted_at")
            if ts:
                last_ts = parse(ts)
            break
    hours = (now_dt - last_ts).total_seconds() / 3600.0 if last_ts else None
    return {"stalled": True, "flat": len(counted), "last_hours": round(hours, 1) if hours else None,
            "reason": (f"the Shorts feed has not shown the last {lookback} clips "
                       f"(all <= {threshold} views) -- reach is removed, not weak")}


def gate(slug: str, manifest_path: str, min_gap: float = MIN_GAP_HOURS,
         token: str | None = None, scripts: list | None = None, cues=()) -> dict:
    """Decide whether the next Short is due, and grade the last one.

    allowed is False when the last post is younger than min_gap: that is the
    "wait 2-3 h" half of K's rule. When it is allowed, `verdict` carries the
    reception of the last post so the caller can keep or change its shape.
    """
    man = _load(manifest_path, {"shorts": {}})
    last = _last_posted(man, {})
    out = {"allowed": True, "verdict": "unknown", "last_shape": None,
           "last_video_id": None, "reason": "no history"}

    if last is None:
        return out

    sid, entry = last
    out["last_video_id"] = entry.get("video_id")
    posted_at = entry.get("posted_at")
    if not posted_at and token:
        live0 = stats(token, [entry["video_id"]])
        posted_at = live0.get(entry["video_id"], {}).get("published_at")
    if not posted_at:
        out["reason"] = "last post has no timestamp; posting on the gap alone"
        return out

    hours = (now() - parse(posted_at)).total_seconds() / 3600.0
    if hours < min_gap:
        out["allowed"] = False
        out["hours_since_last"] = round(hours, 2)
        out["reason"] = (f"only {hours:.1f}h since the last post "
                         f"(need {min_gap}h) -- spacing the posts out")
        return out

    out["hours_since_last"] = round(hours, 2)
    if scripts:
        by_id = {s.get("video_id"): s for s in scripts if s.get("video_id")}
        sc = by_id.get(entry["video_id"])
        if sc:
            out["last_shape"] = hook_shape(sc, cues)

    # Grade: this clip's current views-per-hour against the channel's median.
    if not token:
        out["reason"] = "no token; graded the gap only"
        return out
    entries = _posted_entries(man)
    # Fresh source first: the Data API's viewCount updates within minutes, which
    # is what a 2-3 h check needs. Its shared quota is spent most days, so fall
    # back to the Analytics API -- its own quota, but it lags 1-2 days, so it can
    # grade the *older* clips (the baseline) even when it cannot see the last one.
    live = stats(token, [v["video_id"] for _, v in entries][-50:])
    views = {vid: row["views"] for vid, row in live.items()}
    if not views:
        views = analytics_views(token)
    if not views:
        out["reason"] = "no view source (both API quotas spent); graded the gap only"
        return out
    # Reach guard FIRST, before the "is the last post measurable yet" test. The
    # stall reads the last five clips that HAVE view data, so a newest post too
    # fresh to be measured (or a spent Data API quota on its id) must not skip the
    # check. Returning "unknown -> keep posting" on an unmeasurable newest post is
    # exactly how a withheld channel kept getting posted to: measured 2026-11-11,
    # kongkeat's newest post was always unmeasurable, so the stall branch was never
    # reached and the rail posted 5 clips in ~10 h while the feed was off.
    stall = detect_stall(entries, views)
    out["stall"] = stall
    if stall["stalled"]:
        age = stall.get("last_hours")
        if age is not None and age >= STALL_COOLDOWN_H:
            out["verdict"] = "bad"      # probe: post ONE changed clip, then re-read
            out["reason"] = (f"{stall['reason']}; paused {age:.0f}h -- posting one "
                             "changed clip to test whether the feed returns")
        else:
            out["allowed"] = False
            out["verdict"] = "bad"
            since = f" (last clip {age:.0f}h ago)" if age is not None else ""
            out["reason"] = (f"{stall['reason']}{since} -- do not repeat the shape "
                             "that got the channel withheld")
        return out
    this_views = views.get(entry["video_id"])
    if this_views is None:
        # The last post is too fresh for the Analytics window and the Data API is
        # spent, and the channel is not stalled (checked above). Unknown means
        # "keep the shape" downstream, never "change it".
        out["reason"] = ("the last post is not measurable yet (fresh window / "
                         "spent quota) -- keeping the current shape")
        return out
    per_hour = this_views / max(hours, 0.1)
    base = []
    for _sid, v in entries:
        if v["video_id"] == entry["video_id"]:
            continue
        w = views.get(v["video_id"])
        ts = v.get("posted_at") or live.get(v["video_id"], {}).get("published_at")
        if w is None or not ts:
            continue
        age = (now() - parse(ts)).total_seconds() / 3600.0
        if age >= BASELINE_MIN_AGE_H:
            base.append(w / age)
    baseline = _quantile(base, GOOD_QUANTILE)
    verdict = grade(per_hour, baseline, len(base))
    # Same-day conversion proxy: likes + comments per 1k views, from the Data API
    # call we already make. A young channel can act on this in hours; the Analytics
    # subscriber number lags 1-2 days.
    row = live.get(entry["video_id"], {})
    likes, comments = row.get("likes"), row.get("comments")
    eng = round(1000 * (likes + comments) / this_views, 1) if (this_views and likes is not None) else None
    tail = f", likes {likes} comments {comments} ({eng}/1k)" if eng is not None else ""
    out.update({"verdict": verdict, "views": this_views,
                "likes": likes, "comments": comments, "engagement_per_1k": eng,
                "per_hour": round(per_hour, 2),
                "baseline_per_hour": round(baseline, 2),
                "baseline_clips": len(base),
                "reason": (f"last post {this_views} views in {hours:.1f}h "
                           f"({per_hour:.1f}/h vs channel top-quarter "
                           f"{baseline:.1f}/h){tail} -> {verdict}")})
    return out


def order(todo: list, cues, verdict: str, last_shape: str | None) -> list:
    """Order the queue from the last post's verdict.

    good/unknown -> keep the measured winning shape first (a stable sort keeps id
    order inside each group). bad -> move the *other* shape to the front, so the
    next clip is a change, which is the "bad reception, try something else" half of
    K's rule. A channel with no cues keeps the old behaviour.
    """
    if not cues:
        return todo
    if verdict == "bad" and last_shape:
        other = "plain" if last_shape == "cue" else "cue"
        return sorted(todo, key=lambda s: 0 if hook_shape(s, cues) == other else 1)
    return sorted(todo, key=lambda s: 0 if hook_shape(s, cues) == "cue" else 1)


def _write_reception(slug: str, rec: dict) -> None:
    os.makedirs(RECEPTION_DIR, exist_ok=True)
    path = reception_path(slug)
    history = _load(path, {"history": []})
    history.setdefault("history", []).append(rec)
    history["latest"] = rec
    history["history"] = history["history"][-50:]
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(history, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


CHANNELS = {
    "dharma": ("YT_CH2_REFRESH_TOKEN", "content/ch2_shorts.json",
               "content/ch2_shorts/scripts.json"),
    "genx": ("YT_CH1_REFRESH_TOKEN", "content/ch1_shorts.json",
             "content/ch1_shorts/scripts.json"),
    "kongkeat": ("YT_CH4_REFRESH_TOKEN", "content/ch4_shorts.json",
                 "content/ch4_shorts/scripts.json"),
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--channel", default="dharma", choices=list(CHANNELS))
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    env, man_rel, scripts_rel = CHANNELS[args.channel]
    token = None
    try:
        token = access_token(env)
    except Exception as exc:                       # noqa: BLE001 -- degrade, do not crash
        print(f"  (no token: {exc}; grading the gap only)", file=sys.stderr)

    scripts = _load(os.path.join(ROOT, scripts_rel), [])
    rec = gate(args.channel, os.path.join(ROOT, man_rel), token=token,
               scripts=scripts)
    rec["channel"] = args.channel
    rec["at"] = now().isoformat(timespec="seconds")
    _write_reception(args.channel, rec)
    if args.json:
        print(json.dumps(rec, ensure_ascii=False, indent=2))
    else:
        print(f"{args.channel}: {'DUE' if rec['allowed'] else 'wait'} -- {rec['reason']}")
        print(f"  verdict={rec['verdict']} last_shape={rec['last_shape']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
