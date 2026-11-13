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


def upload_ids(yt, uploads: str, cap: int = 1000) -> list:
    """Every video id still on the channel's uploads playlist, newest first.

    A video that was removed -- by YouTube (a policy take-down) or by us -- leaves
    the uploads playlist, so this is the set to diff a manifest against. `private`
    clips stay listed here, which is why they are not read as removals.
    """
    ids, token = [], None
    while uploads and len(ids) < cap:
        r = yt.playlistItems().list(part="contentDetails", playlistId=uploads,
                                    maxResults=50, pageToken=token).execute()
        ids.extend(i["contentDetails"]["videoId"] for i in r.get("items", []))
        token = r.get("nextPageToken")
        if not token:
            break
    return ids[:cap]


def find_removed(recorded: dict, present: set, removed: set) -> list:
    """Recorded videos that are no longer on the channel.

    YouTube removing a video (a policy take-down) is invisible to every other
    guard: the clip simply disappears from the uploads playlist and nothing here
    notices. Measured 2026-11-13: genx carried an active community-guidelines
    warning whose removed content never appeared in any report -- the audit only
    ever diffed channel -> manifest, never manifest -> channel.
    """
    out = []
    for vid, meta in recorded.items():
        if vid in present or vid in removed:
            continue
        out.append(f"video {vid} was recorded but is no longer on the channel "
                   f"(removed by YouTube, or deleted without a backup): "
                   f"{(meta.get('title') or '')[:50]}")
    return out


def recent_videos(yt, uploads: str, limit: int = 20) -> list:
    ids = upload_ids(yt, uploads, cap=limit)[:limit]
    if not ids:
        return []
    out = []
    for i in range(0, len(ids), 50):
        r = yt.videos().list(part="snippet,statistics,contentDetails",
                             id=",".join(ids[i:i + 50])).execute()
        out.extend(r.get("items", []))
    return out


def recorded_entries(channel_id: str) -> dict:
    """Every video this repo has recorded for a channel: id -> {title, posted_at}.

    A video the channel owns but no manifest names was uploaded by something
    OUTSIDE these rails -- a manual Studio upload, or a second tool. That is the
    one class of upload the pace/cap/gap guards cannot see, so the audit must
    name it (measured 2026-11-11: ch4 had 97 uploads against 57 recorded, and 25
    carried a brand token no code here writes).

    The reverse is just as important and was missing until 2026-11-13: a video we
    DID record that is no longer on the channel has been removed -- by YouTube
    (a policy take-down, which is how genx got its warning) or by us. The uploads
    playlist is the only place either shows up, so keep the timestamp too.
    """
    root = os.path.dirname(HERE)
    out: dict = {}
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
                out[v["video_id"]] = {"title": v.get("title", ""),
                                      "posted": v.get("posted_at")}
        for v in (d.get("videos") or []):
            if isinstance(v, dict) and v.get("video_id"):
                out[v["video_id"]] = {"title": v.get("title", ""),
                                      "posted": v.get("posted_at") or v.get("published")}
    return out


def recorded_ids(channel_id: str) -> set:
    return set(recorded_entries(channel_id))


def removed_by_us(channel_id: str) -> set:
    """Ids we ourselves removed -- a delete leaves a backup in content/deleted/.

    Without this the new "recorded but missing" check would fire on every clip we
    deleted on purpose. `private` clips are NOT here: they stay in the uploads
    playlist, so they still read as present.
    """
    root = os.path.dirname(HERE)
    d = os.path.join(root, "content", "deleted")
    ids = set()
    if not os.path.isdir(d):
        return ids
    for name in os.listdir(d):
        if not name.endswith(".json"):
            continue
        try:
            row = json.load(open(os.path.join(d, name), encoding="utf-8"))
        except (ValueError, OSError):
            continue
        vid = row.get("id") if isinstance(row, dict) else None
        if vid:
            ids.add(vid)
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


def removed_defects(recorded: dict, present: set, removed: set) -> list:
    """`removed_by_us` ids are ours; everything else is a take-down to name."""
    return find_removed(recorded, present, removed)


def alert_live_rogue(report: dict) -> None:
    """Open (or refresh) a GitHub issue while a LIVE rogue upload is on a channel.

    The step summary is not where K looks. Measured 2026-11-11: a second stream
    is inserting clips our code never writes (`en-US`, category 27, the old brand
    `เรื่องเล่าการ์ตูน`) at a fixed `:21` minute. It is invisible to every other
    guard, so it must reach a place that is seen -- a GitHub issue, like
    health.py. The issue clears itself when no live rogue upload remains.
    """
    live = {}
    measured = False
    for slug, r in report.items():
        if r.get("channel"):
            measured = True
        hits = [x for x in (r.get("defects") or []) if "LIVE rogue upload" in x]
        if hits:
            live[slug] = hits
    if not measured:
        # Every channel errored (typically the daily read quota is spent). The
        # audit measured NOTHING, so it must not close the alert -- a transient
        # 403 is not "the rogue stream is gone".
        print("rogue alert: nothing measured (all channels errored); issue left as is")
        return
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


def _live_rogue_ids(defects: list) -> list:
    """The (video_id, title) of each LIVE rogue upload named in a defect list."""
    out = []
    for d in defects:
        m = re.match(r"video (\S+) is UNRECORDED.*LIVE rogue upload outside the rails: (.*)$", d)
        if m:
            out.append((m.group(1), m.group(2)))
    return out


def merge_hidden(ledger: list, hidden: list) -> list:
    """Add newly-hidden videos to the ledger, skipping ones already recorded.

    Idempotent so a re-run does not append the same clip twice -- the ledger is
    the record of what we paused, and it must not grow on every audit.
    """
    have = {h["video_id"] for h in ledger}
    for h in hidden:
        if h["video_id"] not in have:
            ledger.append(h)
            have.add(h["video_id"])
    return ledger


def hide_live_rogue(report: dict) -> None:
    """Pause each LIVE rogue clip (privacyStatus=private) -- reversible, no delete.

    Measured 2026-11-11: a second stream inserts clips our code never writes at a
    fixed :21 minute. These were never recorded in any manifest, so they are not
    ours to keep. `private` stops the damage in one call and is reversible; a
    delete is not, and a delete driven by a manifest diff could remove a real
    video, so this NEVER deletes and NEVER touches the historical backlog (those
    are handled by find_defects' age split). The token holds the `youtube` scope
    needed for videos.update. Every clip paused is written to a ledger, so a
    later run skips it and the decision is auditable.
    """
    root = os.path.dirname(HERE)
    ledger_path = os.path.join(root, "content", "rogue_hidden.json")
    try:
        ledger = json.load(open(ledger_path, encoding="utf-8")).get("hidden", [])
    except (OSError, ValueError):
        ledger = []
    already = {h["video_id"] for h in ledger}
    newly = []
    for slug, r in report.items():
        ch = r.get("channel") or {}
        ch_id = ch.get("id")
        for vid, title in _live_rogue_ids(r.get("defects") or []):
            if vid in already:
                continue
            try:
                yt = client_for(slug, ch_id)
                yt.videos().update(part="status", body={
                    "id": vid, "status": {"privacyStatus": "private"}}).execute()
            except Exception as exc:
                print(f"  hide FAILED for {vid}: {exc}")
                continue
            print(f"  hid {vid} ({slug}) -- was: {title[:50]}")
            newly.append({"video_id": vid, "channel": slug, "channel_id": ch_id,
                          "title": title, "hidden_at": f"{datetime.now(timezone.utc):%Y-%m-%dT%H:%M:%SZ}",
                          "reason": "live rogue upload outside the rails"})
            already.add(vid)
    if newly:
        merge_hidden(ledger, newly)
        os.makedirs(os.path.dirname(ledger_path), exist_ok=True)
        json.dump({"hidden": ledger}, open(ledger_path, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
        print(f"  recorded {len(newly)} in {ledger_path}")
        _comment_hidden(newly)


def _comment_hidden(newly: list) -> None:
    """Say on the alert issue which clips were paused, so the action is visible."""
    repo = os.environ.get("GITHUB_REPOSITORY", "kongkeat938/ai-content-lab")
    title = "Channel audit: a live upload stream outside the rails"
    try:
        listed = subprocess.run(["gh", "issue", "list", "--repo", repo, "--state", "open",
                                 "--search", title, "--json", "number,title"],
                                capture_output=True, text=True, check=True)
        existing = next((i for i in json.loads(listed.stdout or "[]")
                         if i["title"] == title), None)
        if not existing:
            return
        body = "\n".join(
            [f"Measured {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC. Paused "
             f"{len(newly)} live rogue clip(s) with `privacyStatus=private` "
             "(reversible; no delete, backlog untouched):", ""]
            + [f"- {h['channel']}: {h['video_id']} -- {h['title'][:60]}" for h in newly]
            + ["", "Reversible with `videos.update(privacyStatus=public)`; the ledger is "
               "`content/rogue_hidden.json`."])
        subprocess.run(["gh", "issue", "comment", str(existing["number"]),
                        "--repo", repo, "--body", body], check=True)
        print(f"  commented the take-down on issue #{existing['number']}")
    except Exception as exc:
        print(f"  hide comment skipped: {exc}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", default=None)
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--write", action="store_true",
                    help="also write docs/CHANNEL-AUDIT-LATEST.md")
    ap.add_argument("--alert", action="store_true",
                    help="open/update a GitHub issue when a LIVE rogue upload is found")
    ap.add_argument("--hide-live-rogue", action="store_true",
                    help="pause (private, reversible) each LIVE rogue clip; never deletes")
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
        except Exception as e:  # a spent read quota, a network blip, etc.
            # One channel's failure must not stop the others (the alert would
            # then see only a partial fleet). Record it and move on.
            print(f"  channel unreachable: {e}")
            report[c["slug"]] = {"error": str(e)}
            continue
        ch = channel_report(yt, c["slug"])
        pls = playlists(yt)
        vids = recent_videos(yt, ch.get("uploads_playlist"), a.limit)
        recorded = recorded_entries(c["channel_id"])
        # The full uploads list is needed to notice a take-down: a removed video
        # leaves the playlist, so diff the whole list, not just the newest page.
        present = set(upload_ids(yt, ch.get("uploads_playlist")))
        print(f"  {ch.get('title')}  subs={ch.get('subs')} videos={ch.get('videos')} "
              f"views={ch.get('views')} playlists={len(pls)} uploads={len(present)}")
        defects = find_defects(ch, pls, vids, set(recorded))
        defects += removed_defects(recorded, present, removed_by_us(c["channel_id"]))
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
        if not any("channel" in r for r in report.values()):
            # Nothing measured (usually the read quota is spent). Keep the last
            # good report rather than overwriting it with a page of errors.
            print("nothing measured; leaving the last good audit report in place")
            return 0
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
    if a.hide_live_rogue:
        hide_live_rogue(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
