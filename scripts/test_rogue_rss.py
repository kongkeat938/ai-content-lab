#!/usr/bin/env python3
"""Guard: the quota-free rogue watcher must actually SEE a rogue upload.

A detector that only ever says "clean" is worthless. This drives `find_rogue`
with hand-built feed entries so it FAILS if the detection ever stops working:
a fresh unrecorded id must be reported, a recorded id must not, and an OLD
unrecorded id (the pre-manifest backlog) must not -- otherwise the rail would
cry wolf on every historical clip and be ignored.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from rogue_watch_rss import (  # noqa: E402
    find_rogue, parse_relative_age_days, parse_uploads_page)

NOW = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)


def iso(hours_ago: float) -> str:
    return (NOW - timedelta(hours=hours_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")


def entry(vid: str, hours_ago: float) -> dict:
    return {"video_id": vid, "title": f"t {vid}", "published": iso(hours_ago)}


def main() -> int:
    fails = []

    # A fresh id no manifest records -> the rogue stream. MUST be reported.
    got = find_rogue([entry("ROGUE000001", 0.5)], recorded=set(), now=NOW)
    if [r["video_id"] for r in got] != ["ROGUE000001"]:
        fails.append("fresh unrecorded id was NOT reported (blind detector)")

    # A recorded id -> ours, never a rogue.
    got = find_rogue([entry("OURS0000001", 0.5)], recorded={"OURS0000001"}, now=NOW)
    if got:
        fails.append("a recorded id was reported as rogue (false positive)")

    # An OLD unrecorded id -> the pre-manifest backlog, not the live stream.
    got = find_rogue([entry("OLD00000001", 24 * 30)], recorded=set(), now=NOW)
    if got:
        fails.append("an old unrecorded id was reported as live rogue (cry wolf)")

    # Mixed: only the fresh unrecorded one survives.
    got = find_rogue([entry("ROGUE000001", 1), entry("OURS0000001", 1),
                      entry("OLD00000001", 24 * 30)],
                     recorded={"OURS0000001"}, now=NOW)
    if [r["video_id"] for r in got] != ["ROGUE000001"]:
        fails.append(f"mixed feed filtered wrong: {[r['video_id'] for r in got]}")

    # The uploads-page fallback: a fresh entry carries an age_days, so find_rogue
    # must use it (the real page supplies relative ages, not ISO timestamps).
    got = find_rogue([{"video_id": "ROGUE000002", "title": "x",
                       "published": "", "age_days": 0.4}],
                     recorded=set(), now=NOW)
    if [r["video_id"] for r in got] != ["ROGUE000002"]:
        fails.append("uploads-page entry with only age_days was NOT reported")

    # Relative-age labels: compact ones ("2d ago") must parse, or the fallback
    # silently treats a fresh rogue as un-measurable and drops it.
    for label, want in [("9h ago", 9 / 24), ("2d ago", 2.0), ("1 week ago", 7.0),
                        ("3 months ago", 90.0), ("1 year ago", 365.0)]:
        got_age = parse_relative_age_days(label)
        if got_age is None or abs(got_age - want) > 1e-6:
            fails.append(f"age label {label!r} parsed as {got_age}, want {want}")
    if parse_relative_age_days("No views") is not None:
        fails.append("a view count parsed as an age (should be None)")

    # The parser must read a real page shape: ytInitialData -> lockupViewModel.
    import json as _json
    lv = {"contentId": "ROGUE000003",
          "metadata": {"lockupMetadataViewModel": {
              "title": {"content": "t"},
              "metadata": {"contentMetadataViewModel": {"metadataRows": [
                  {"metadataParts": [{"text": {"content": "5"}},
                                     {"text": {"content": "2d ago"}}]}]}}}}}
    payload = {"a": {"lockupViewModel": lv}}
    page = "<script>var ytInitialData = " + _json.dumps(payload) + ";</script>"
    parsed = parse_uploads_page(page)
    if [e["video_id"] for e in parsed] != ["ROGUE000003"] or parsed[0]["age_days"] != 2.0:
        fails.append(f"uploads-page parse wrong: {parsed}")
    if find_rogue(parsed, recorded=set(), now=NOW) == []:
        fails.append("a parsed fresh uploads-page entry was NOT reported as rogue")

    # A page with no ytInitialData must RAISE (a blind page is not an empty page).
    try:
        parse_uploads_page("<html>no payload here</html>")
        fails.append("a page without ytInitialData did not raise (blind read = empty)")
    except ValueError:
        pass

    # scan() must report BLIND -- never clean -- when a source cannot answer.
    import rogue_watch_rss as m
    m.channels = lambda: [{"slug": "x", "channel_id": "UC0000000000000000000000"}]
    m.recorded_ids = lambda cid: set()
    m.hidden_ids = lambda: set()

    def boom(_cid):
        raise RuntimeError("404")

    m.fetch_feed = boom
    m.fetch_uploads_page = boom
    rogue, blind = m.scan()
    if rogue or blind != ["x"]:
        fails.append(f"both sources down: scan gave rogue={rogue} blind={blind}, want blind=['x']")

    # Sources that ANSWER but yield zero entries are still blind (broken selector).
    empty_feed = '<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"></feed>'
    empty_page = '<script>var ytInitialData = {"x": 1};</script>'
    m.fetch_feed = lambda cid: empty_feed
    m.fetch_uploads_page = lambda cid: empty_page
    rogue, blind = m.scan()
    if rogue or blind != ["x"]:
        fails.append(f"empty sources: scan gave rogue={rogue} blind={blind}, want blind=['x']")

    # Fallthrough: an empty first source must NOT stop us reading the second one.
    import json as _json2
    good_page = ("<script>var ytInitialData = "
                 + _json2.dumps({"a": {"lockupViewModel": lv}}) + ";</script>")
    m.fetch_feed = lambda cid: empty_feed
    m.fetch_uploads_page = lambda cid: good_page
    rogue, blind = m.scan()
    if blind or [r["video_id"] for r in rogue] != ["ROGUE000003"]:
        fails.append(f"empty RSS + good page: rogue={rogue} blind={blind}, want the page entry")

    if fails:
        for f in fails:
            print("FAIL:", f)
        return 1
    print("ok: rogue watcher reports a fresh unrecorded id and nothing else")
    return 0


if __name__ == "__main__":
    sys.exit(main())
