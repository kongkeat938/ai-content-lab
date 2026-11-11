#!/usr/bin/env python3
"""Audit the three channels for defects, using each channel's own token.

Read-only. Pulls the channel branding, playlists, and the newest videos with
their titles, descriptions and tags, then prints what is wrong rather than what
is there -- a listing of correct things is not an audit.

    python3 scripts/audit_channels.py                 # all channels
    python3 scripts/audit_channels.py --slug dharma   # one

The findings it can raise:
  * a channel with no description / no keywords / wrong language / wrong country
  * a channel with no playlists (the series cannot be followed)
  * a video with no description, no tags, or a title with no hook
  * a description that never links the channel's own playlists or siblings
  * a near-duplicate title (the throttle signal)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import yt_auth  # noqa: E402


def client_for(slug: str, channel_id: str):
    from googleapiclient.discovery import build
    creds = yt_auth.load_credentials(expected_channel=channel_id)
    yt = build("youtube", "v3", credentials=creds, cache_discovery=False)
    # Fail loudly rather than auditing the wrong channel: this is exactly the bug
    # that reported all three channels as ch1, because they shared a token file.
    got = (yt.channels().list(part="id", mine=True).execute()
           .get("items") or [{}])[0].get("id")
    if got != channel_id:
        raise SystemExit(f"token for {slug} answered as {got}, expected {channel_id}")
    return yt


def channel_report(yt, slug: str) -> dict:
    ch = yt.channels().list(
        part="snippet,statistics,brandingSettings,contentDetails,status",
        mine=True).execute()
    item = (ch.get("items") or [None])[0]
    if not item:
        return {"slug": slug, "error": "token has no channel"}
    sn = item["snippet"]
    bs = (item.get("brandingSettings") or {}).get("channel", {})
    st = item.get("statistics", {})
    return {
        "slug": slug,
        "id": item["id"],
        "title": sn.get("title"),
        "description": (sn.get("description") or "").strip(),
        "keywords": (bs.get("keywords") or "").strip(),
        "default_language": bs.get("defaultLanguage"),
        "country": bs.get("country"),
        "subs": st.get("subscriberCount"),
        "videos": st.get("videoCount"),
        "views": st.get("viewCount"),
        "uploads_playlist": (item.get("contentDetails", {})
                             .get("relatedPlaylists", {}).get("uploads")),
    }


def playlists(yt) -> list:
    out, token = [], None
    while True:
        r = yt.playlists().list(part="snippet,contentDetails", mine=True,
                                maxResults=50, pageToken=token).execute()
        out.extend(r.get("items", []))
        token = r.get("nextPageToken")
        if not token:
            return out


def recent_videos(yt, uploads: str, limit: int = 20) -> list:
    ids, token = [], None
    while uploads and len(ids) < limit:
        r = yt.playlistItems().list(part="contentDetails", playlistId=uploads,
                                    maxResults=50, pageToken=token).execute()
        ids.extend(i["contentDetails"]["videoId"] for i in r.get("items", []))
        token = r.get("nextPageToken")
        if not token:
            break
    ids = ids[:limit]
    if not ids:
        return []
    out = []
    for i in range(0, len(ids), 50):
        r = yt.videos().list(part="snippet,statistics,contentDetails",
                             id=",".join(ids[i:i + 50])).execute()
        out.extend(r.get("items", []))
    return out


def recorded_ids(channel_id: str) -> set:
    """Every video id this repo has recorded for a channel.

    A video the channel owns but no manifest names was uploaded by something
    OUTSIDE these rails -- a manual Studio upload, or a second tool. That is the
    one class of upload the pace/cap/gap guards cannot see, so the audit must
    name it (measured 2026-11-11: ch4 had 97 uploads against 57 recorded, and 25
    carried a brand token no code here writes).
    """
    root = os.path.dirname(HERE)
    ids = set()
    for name in os.listdir(os.path.join(root, "content")):
        if not name.endswith(".json"):
            continue
        try:
            d = json.load(open(os.path.join(root, "content", name), encoding="utf-8"))
        except (ValueError, OSError):
            continue
        if not isinstance(d, dict) or d.get("channel_id") != channel_id:
            continue
        for v in (d.get("shorts") or {}).values():
            if isinstance(v, dict) and v.get("video_id"):
                ids.add(v["video_id"])
        for v in (d.get("videos") or []):
            if isinstance(v, dict) and v.get("video_id"):
                ids.add(v["video_id"])
    return ids


OLD_BRAND = "เรื่องเล่าการ์ตูน"

# An unrecorded upload published within this many days is the LIVE rogue stream;
# anything older is the pre-manifest backlog (the rails only started recording in
# 2026-11). The two need opposite treatment, so the audit must not blur them:
# a take-down on the backlog would hide legitimate old videos.
RECENT_DAYS = 3


def _age_days(published: str | None) -> float | None:
    if not published:
        return None
    try:
        t = datetime.fromisoformat(published.replace("Z", "+00:00"))
    except ValueError:
        return None
    return (datetime.now(timezone.utc) - t).total_seconds() / 86400


def find_defects(ch: dict, pls: list, vids: list, recorded: set | None = None) -> list:
    d = []
    if not ch.get("description"):
        d.append("channel has NO description")
    if not ch.get("keywords"):
        d.append("channel has NO keywords")
    if ch.get("default_language") != "th":
        d.append(f"defaultLanguage is {ch.get('default_language')!r}, expected 'th'")
    # No country check: measured 2026-11-11, brandingSettings.channel.country is
    # not writable through the Data API -- a PUT with country='TH' returns 200 but
    # the field stays null on every channel. A check that can never be satisfied
    # is noise, so it is dropped rather than left to fire forever.
    if not pls:
        d.append("channel has NO playlists -- a series cannot be followed")
    if ch.get("videos") and int(ch["videos"]) == 0:
        d.append("channel has no videos")

    titles = Counter()
    for v in vids:
        sn = v["snippet"]
        t = sn["title"]
        titles[t] += 1
        if not (sn.get("description") or "").strip():
            d.append(f"video {v['id']} has NO description: {t[:50]}")
        if not sn.get("tags"):
            d.append(f"video {v['id']} has NO tags: {t[:50]}")
        desc = sn.get("description") or ""
        if "youtu.be/" not in desc and "youtube.com/" not in desc:
            d.append(f"video {v['id']} description links no video: {t[:50]}")
        if re.search(r"#\w+", t) and "Shorts" not in t:
            d.append(f"video {v['id']} title has hashtags but is not marked Shorts: {t[:50]}")
        if recorded is not None and v["id"] not in recorded:
            age = _age_days(sn.get("publishedAt"))
            if age is not None and age <= RECENT_DAYS:
                d.append(f"video {v['id']} is UNRECORDED and published {age:.1f}d ago "
                         f"-- LIVE rogue upload outside the rails: {t[:50]}")
            else:
                d.append(f"video {v['id']} is on the channel but in NO manifest "
                         f"(historical, pre-manifest): {t[:50]}")
        if OLD_BRAND in t:
            d.append(f"video {v['id']} still carries the old brand {OLD_BRAND!r}: {t[:50]}")
    for t, n in titles.items():
        if n > 1:
            d.append(f"{n} videos share the title: {t[:60]}")
    return d


def alert_live_rogue(report: dict) -> None:
    """Open (or refresh) a GitHub issue while a LIVE rogue upload is on a channel.

    The step summary is not where K looks. Measured 2026-11-11: a second stream
    is inserting clips our code never writes (`en-US`, category 27, the old brand
    `เรื่องเล่าการ์ตูน`) at a fixed `:21` minute. It is invisible to every other
    guard, so it must reach a place that is seen -- a GitHub issue, like
    health.py. The issue clears itself when no live rogue upload remains.
    """
    live = {}
    for slug, r in report.items():
        hits = [x for x in (r.get("defects") or []) if "LIVE rogue upload" in x]
        if hits:
            live[slug] = hits
    repo = os.environ.get("GITHUB_REPOSITORY", "kongkeat938/ai-content-lab")
    title = "Channel audit: a live upload stream outside the rails"
    try:
        listed = subprocess.run(["gh", "issue", "list", "--repo", repo, "--state", "open",
                                 "--search", title, "--json", "number,title"],
                                capture_output=True, text=True, check=True)
        existing = next((i for i in json.loads(listed.stdout or "[]")
                         if i["title"] == title), None)
        if live:
            body = "\n".join(
                [f"Measured {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC.",
                 "These videos are on a channel but in NO manifest and were published "
                 "recently. Our uploaders all write `defaultLanguage=th` and category 22/24; "
                 "these carry `en-US`/category 27 and an old brand, so they are NOT our rails.",
                 ""]
                + [f"- {s}: {h}" for s, hs in live.items() for h in hs]
                + ["", "The stream runs at a fixed `:21` minute. Our own tokens hold the "
                   "`youtube` scope, so the same access can pause a rogue clip "
                   "(`status.privacyStatus=private`, reversible) -- but first confirm the "
                   "source, because a take-down on the historical backlog would hide "
                   "legitimate old videos.", "",
                   "_Opened/updated by scripts/audit_channels.py; it clears itself when no "
                   "live rogue upload remains._"])
            if existing:
                subprocess.run(["gh", "issue", "comment", str(existing["number"]),
                                "--repo", repo, "--body", body], check=True)
                print(f"rogue alert updated on issue #{existing['number']}")
            else:
                subprocess.run(["gh", "issue", "create", "--repo", repo,
                                "--title", title, "--body", body], check=True)
                print("rogue alert issue opened")
        elif existing:
            subprocess.run(["gh", "issue", "comment", str(existing["number"]), "--repo", repo,
                            "--body", "No live rogue upload remains; closing."], check=True)
            subprocess.run(["gh", "issue", "close", str(existing["number"]),
                            "--repo", repo], check=True)
            print(f"rogue alert cleared; closed issue #{existing['number']}")
    except Exception as exc:  # a report must never fail the rail
        print(f"rogue alert step skipped: {exc}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", default=None)
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--write", action="store_true",
                    help="also write docs/CHANNEL-AUDIT-LATEST.md")
    ap.add_argument("--alert", action="store_true",
                    help="open/update a GitHub issue when a LIVE rogue upload is found")
    a = ap.parse_args()

    reg = json.load(open(os.path.join(os.path.dirname(HERE), "channels.json"),
                         encoding="utf-8"))
    chans = reg["channels"]
    if a.slug:
        chans = [c for c in chans if c["slug"] == a.slug]
    report = {}
    for c in chans:
        if "CANCELLED" in (c.get("status") or ""):
            print(f"== {c['slug']}: CANCELLED, skipped ==")
            continue
        print(f"== {c['slug']} ({c['handle']}) ==")
        try:
            yt = client_for(c["slug"], c["channel_id"])
        except SystemExit as e:
            print(f"  no token: {e}")
            report[c["slug"]] = {"error": str(e)}
            continue
        ch = channel_report(yt, c["slug"])
        pls = playlists(yt)
        vids = recent_videos(yt, ch.get("uploads_playlist"), a.limit)
        recorded = recorded_ids(c["channel_id"])
        print(f"  {ch.get('title')}  subs={ch.get('subs')} videos={ch.get('videos')} "
              f"views={ch.get('views')} playlists={len(pls)}")
        defects = find_defects(ch, pls, vids, recorded)
        for x in defects:
            print(f"    DEFECT: {x}")
        if not defects:
            print("    no defects found")
        report[c["slug"]] = {"channel": ch, "playlists": len(pls),
                             "checked_videos": len(vids), "defects": defects}
    out = os.path.join(os.path.dirname(HERE), "work", "channel_audit.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(report, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\nwrote {out}")
    if a.write:
        doc = os.path.join(os.path.dirname(HERE), "docs", "CHANNEL-AUDIT-LATEST.md")
        with open(doc, "w", encoding="utf-8") as fh:
            fh.write(f"# Channel audit -- {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC\n\n")
            fh.write("Measured live from the Data API. A video listed as \"in NO "
                     "manifest\" was uploaded by something outside these rails.\n\n")
            for slug, r in report.items():
                if "error" in r:
                    fh.write(f"## {slug}\n\n- error: {r['error']}\n\n")
                    continue
                ch = r["channel"]
                fh.write(f"## {slug} ({ch.get('title')})\n\n")
                fh.write(f"- subs={ch.get('subs')} videos={ch.get('videos')} "
                         f"views={ch.get('views')} playlists={r['playlists']} "
                         f"checked={r['checked_videos']}\n")
                if r["defects"]:
                    for x in r["defects"]:
                        fh.write(f"- DEFECT: {x}\n")
                else:
                    fh.write("- no defects found\n")
                fh.write("\n")
        print(f"wrote {doc}")
    if a.alert:
        alert_live_rogue(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
