#!/usr/bin/env python3
"""Publish a NEW version of every Short that is already live.

The owner's call (2026-11-07): do not delete the old clips, publish new versions
of them in the current format -- a blurred, licence-checked picture with an
instrumental bed -- and let the views decide.

YouTube has no way to swap the file under an existing video. Its own help page
says it plainly: "You can't replace a video. Any new video you upload to YouTube
will get a new URL." The Data API can change a video's title, description and
tags, never its pixels. So "a new version" can only be a new upload, and the old
clip keeps its URL, views, likes and comments for as long as we leave it alone.

That leaves the channel holding two cuts of the same script. Two advisors agreed
that showing both publicly reads as a duplicate and invites YouTube's reused
content rule, so the old clip is set to **unlisted** once its replacement is live
-- not deleted, not private: the URL still works, the comments and view count
survive, and one API call puts it back. `--old keep` turns that off.

Unlisting is skipped for a clip that is still earning. A Short with 1,236 views
is traffic we already have; hiding it to show a 0-view replacement is a straight
loss, so `--old unlist-low` (the default) unlists only the ones below
`--old-view-threshold` views and leaves the earners up.

    python3 scripts/remake_shorts.py --dry-run            # list, change nothing
    python3 scripts/remake_shorts.py --channel genx --per-run 1
    python3 scripts/remake_shorts.py --old keep           # never touch the old clip

The daily cap, the spacing between posts and the upload ledger are the rail's own
(`scripts/publish_shorts.py`), reused here rather than re-implemented, so a remake
day and a normal day cannot both flood a channel.

Credentials: YT_CLIENT_ID, YT_CLIENT_SECRET and the channel's refresh token.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import publish_shorts as ps  # noqa: E402  -- reuse the rail's helpers on purpose


def remakes_path(manifest: str) -> str:
    """`content/ch2_shorts.json` -> `content/ch2_shorts_remakes.json`."""
    return manifest.replace("_shorts.json", "_shorts_remakes.json")


def views_of(yt, video_id: str) -> int:
    """Views of one video, or 0 when the call fails -- the caller only compares it."""
    try:
        r = yt.videos().list(part="statistics", id=video_id).execute()
        items = r.get("items", [])
        return int(items[0]["statistics"].get("viewCount", 0)) if items else 0
    except Exception:  # noqa: BLE001 -- a failed read must not stop a remake
        return 0


def set_privacy(yt, video_id: str, privacy: str) -> None:
    """Move a clip to unlisted/private. Reversible: the same call sets it back."""
    yt.videos().update(part="status",
                       body={"id": video_id, "status": {"privacyStatus": privacy}}).execute()


def fix_old(yt, rem: dict, rpath: str, mode: str, threshold: int, channel: str) -> int:
    """Retry the old-clip moves that a quota-exhausted run could not finish.

    The Data API shares one quota across every call, so an upload that runs the
    budget to zero leaves its own clip's unlist as a 403 -- measured 2026-11-07 on
    dharma. The upload is the part that matters and it is already recorded, so the
    move is left pending and swept up here on a later run, when the quota has
    reset. Nothing is uploaded by this pass.
    """
    pending = [(sid, v) for sid, v in rem["shorts"].items() if v.get("old_privacy_pending")]
    print(f"{len(pending)} old clip(s) pending a privacy move")
    rc = 0
    for sid, v in pending:
        old_id = v.get("old_video_id")
        if not old_id:
            v.pop("old_privacy_pending", None)
            continue
        try:
            n = views_of(yt, old_id)
            if mode == "unlist-low" and n >= threshold:
                v["old_privacy"] = "public"
                v.pop("old_privacy_pending", None)
                print(f"  {sid}: old {old_id} kept public ({n} views)")
                continue
            privacy = "private" if mode == "private" else "unlisted"
            set_privacy(yt, old_id, privacy)
            v["old_privacy"] = privacy
            v.pop("old_privacy_pending", None)
            print(f"  {sid}: old {old_id} -> {privacy} ({n} views)")
        except Exception as exc:  # noqa: BLE001 -- quota, retry on a later run
            print(f"  {sid}: still pending ({exc})")
            rc = 1
    ps.save(rem, rpath)
    ps.commit(rpath, f"remake({channel}): sweep the old clips that were left public")
    return rc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", default="dharma", choices=list(ps.CHANNELS))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--per-run", type=int, default=1,
                    help="remake at most N per run (default 1)")
    ap.add_argument("--privacy", default="public",
                    choices=["private", "unlisted", "public"])
    ap.add_argument("--old", default="unlist-low",
                    choices=["keep", "unlist", "unlist-low", "private"],
                    help="what to do with the old clip once the new one is live")
    ap.add_argument("--old-view-threshold", type=int, default=100,
                    help="with --old unlist-low, leave clips at or above this many views alone")
    ap.add_argument("--force", action="store_true",
                    help="ignore the daily cap and the spacing for ONE deliberate remake "
                         "(a one-off the owner asked for); never for a batch")
    ap.add_argument("--work", help="override the build dir (default: per channel)")
    args = ap.parse_args()

    spec = ps.CHANNELS[args.channel]
    work = args.work or spec["work"]
    scripts = ps.load(spec["scripts"], [])
    man = ps.load(spec["manifest"], {"shorts": {}})
    rpath = remakes_path(spec["manifest"])
    rem = ps.load(rpath, {"channel_slug": args.channel,
                          "channel_id": spec["channel_id"], "shorts": {}})
    if not scripts:
        sys.exit(f"no scripts at {spec['scripts']}")

    lim = ps.load(ps.LIMIT_FILE, {})
    rec = (lim.get("channels", {}) if isinstance(lim, dict) else {}).get(spec["channel_id"], {})
    if (rec.get("reset_at")
            and datetime.fromisoformat(rec["reset_at"].replace("Z", "+00:00")) > datetime.now(timezone.utc)):
        print(f"channel upload limit recorded; resets {rec['reset_at']} -- nothing to do")
        return 0

    # Only a clip that is live can be remade, and only once: the remakes manifest
    # is the record, so a second run never builds a third cut of the same script.
    todo = [s for s in scripts
            if man["shorts"].get(s["id"], {}).get("video_id")
            and not rem["shorts"].get(s["id"], {}).get("video_id")]
    todo = ps.winning_first(todo, spec.get("cues"))

    already = ps.uploads_in_last_24h(args.channel, spec["manifest"])
    room = max(ps.DAILY_CAP - already, 0)
    since = ps.hours_since_last_upload(args.channel, spec["manifest"])
    if args.force:
        # A deliberate one-off the owner asked for: this run publishes, and the
        # ledger still records it, so the cap counts it from here on.
        room = max(room, args.per_run)
        since = None
        print(f"--force: ignoring the cap ({already}/{ps.DAILY_CAP}) for this one run")

    # A dry run is a look at the plan, so it shows the queue even on a day the cap
    # would park a real run -- otherwise the only day the owner wants to check the
    # list is the day it prints nothing.
    if args.dry_run:
        print(f"{len(todo)} to remake, {len(rem['shorts'])} already remade, "
              f"{already}/{ps.DAILY_CAP} published in the last 24h")
        if room == 0:
            print(f"  (a real run would wait: cap reached; {args.per_run} per run when it frees)")
        elif since is not None and since < ps.MIN_GAP_HOURS:
            print(f"  (a real run would wait: last upload {since:.1f}h ago)")
        for s in todo[:max(args.per_run, 1)]:
            old = man["shorts"][s["id"]]["video_id"]
            print(f"  {s['id']}: {s['hook'][:60]}")
            print(f"      old {old} -> new version ({args.privacy}); old clip: {args.old}")
        return 0

    planned = todo[:min(args.per_run, room)] if room else []
    # The feed guard (2026-11-11). The daily cap and the 2-hour gap pace a HEALTHY
    # channel; neither knows the feed has stopped showing this one. A remake is a
    # fresh upload of the SAME shape, so posting it to a withheld channel deepens
    # the block (five-advisor panel, 2026-11-10). Use the same guard publish_shorts
    # uses, so a remake day and a normal day cannot disagree about a stalled channel.
    if planned and not args.force:
        try:
            import pace
            rows = pace.stats(ps.access_token(spec),
                              [v["video_id"] for v in man["shorts"].values()
                               if v.get("video_id")][-50:])
            stall = pace.detect_stall(
                [(k, v) for k, v in man["shorts"].items() if v.get("video_id")],
                {vid: r["views"] for vid, r in rows.items()})
        except Exception as exc:  # noqa: BLE001 -- a quota miss must not fake a stall
            print(f"  (pace unavailable: {exc}; using the cap and gap only)",
                  file=sys.stderr)
        else:
            if stall.get("stalled"):
                print(f"the Shorts feed has stopped showing this channel "
                      f"({stall['reason']}) -- holding remakes until it recovers "
                      "(still sweeping any pending old-clip move)")
                planned = []      # skip the upload; the old-clip sweep below still runs
    pending = [v for v in rem["shorts"].values() if v.get("old_privacy_pending")]
    if not planned and not pending:
        if room == 0:
            print(f"daily cap reached ({already}/{ps.DAILY_CAP} in the last 24h) -- waiting")
        elif since is not None and since < ps.MIN_GAP_HOURS:
            print(f"last upload {since:.1f}h ago, under the {ps.MIN_GAP_HOURS}h gap -- waiting")
        else:
            print("nothing to do")
        return 0

    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload
    from google.oauth2.credentials import Credentials

    creds = Credentials(token=ps.access_token(spec), refresh_token=os.environ[spec["token"]],
                        token_uri="https://oauth2.googleapis.com/token",
                        client_id=os.environ["YT_CLIENT_ID"],
                        client_secret=os.environ["YT_CLIENT_SECRET"])
    yt = build("youtube", "v3", credentials=creds, cache_discovery=False)
    try:
        res = yt.channels().list(part="snippet", mine=True).execute()
        got = res["items"][0]["id"]
        if got != spec["channel_id"]:
            sys.exit(f"WRONG CHANNEL: token is {got}, expected {spec['channel_id']}")
        print(f"  authorised as {res['items'][0]['snippet']['title']} ({got})")
    except HttpError as exc:
        print(f"  channel check skipped ({exc.status_code})", file=sys.stderr)

    # Sweep any old-clip move an earlier run could not finish, before this run
    # spends the shared Data API quota on an upload. Cheap, and it is the only
    # thing that puts a stuck old clip to unlisted.
    fix_old(yt, rem, rpath, args.old, args.old_view_threshold, args.channel)

    if not planned:
        print("nothing to upload this run; swept the old clips")
        return 0
    print(f"{len(planned)} to remake, {len(rem['shorts'])} already remade, "
          f"{already}/{ps.DAILY_CAP} published in the last 24h")

    rc = 0
    for s in planned:
        sid = s["id"]
        old_id = man["shorts"][sid]["video_id"]
        out = os.path.join(work, sid, f"short_{sid}.mp4")
        if not os.path.exists(out):
            print(f"building {sid} ...")
            cmd = [sys.executable, os.path.join(HERE, "make_short.py"),
                   "--scripts", spec["scripts"], "--index", sid, "--out-dir", work]
            if spec.get("art_style"):
                cmd += ["--art-style", spec["art_style"],
                        "--art-dir", spec.get("art", ""),
                        "--art-ledger", ps.art_ledger_path(args.channel)]
            elif spec.get("art") and os.path.isdir(spec["art"]):
                cmd += ["--art-dir", spec["art"]]
            bed = ps.pick_bed(spec.get("music_dir"), sid, spec.get("mood"),
                        ps.bed_ledger_path(args.channel))
            if bed:
                cmd += ["--music", bed]
            if spec.get("cta_mid"):
                cmd += ["--cta-mid"]
            r = subprocess.run(cmd, capture_output=True, text=True)
            if r.returncode != 0:
                print(f"  build failed: {r.stderr[-400:]}", file=sys.stderr)
                rc = 1
                continue
        if not os.path.exists(out):
            print(f"  {sid}: no output at {out}", file=sys.stderr)
            rc = 1
            continue

        description = (f"{s['hook']}\n\n" + "\n".join(s["lines"]) +
                       f"\n\n{s['cta']}" + spec["tail"] +
                       (ps.MUSIC_CREDIT if spec.get("music_dir") else ""))
        body = {
            "snippet": {
                "title": (s["hook"][:95] + " #Shorts")[:100],
                "description": description[:5000],
                "tags": spec["tags"],
                "categoryId": spec["category"],
                "defaultLanguage": "th",
                "defaultAudioLanguage": "th",
            },
            "status": {"privacyStatus": args.privacy, "selfDeclaredMadeForKids": False,
                       "license": "youtube", "embeddable": True},
        }
        print(f"uploading {sid} ({os.path.getsize(out)/1e6:.1f} MB) ...")
        try:
            request = yt.videos().insert(part="snippet,status", body=body,
                                         media_body=MediaFileUpload(out, chunksize=8 << 20,
                                                                    resumable=True))
            response = None
            while response is None:
                _, response = request.next_chunk()
        except HttpError as exc:
            text = str(exc)
            print(f"  UPLOAD FAILED: {text}", file=sys.stderr)
            if "uploadLimitExceeded" in text or "Video Uploads per day" in text:
                print("  daily upload limit reached; stopping this run", file=sys.stderr)
                ps.note_upload_limit(spec["channel_id"], text)
                break
            rc = 1
            continue

        vid = response["id"]
        rem["shorts"][sid] = {
            "video_id": vid, "url": f"https://youtu.be/{vid}",
            "title": body["snippet"]["title"], "old_video_id": old_id,
            "remade_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        ps.save(rem, rpath)                     # record before anything else can fail
        ps.note_upload(args.channel)
        ps.commit(rpath, f"remake({args.channel}): record Short {sid} v2")
        ps.commit(ps.UPLOAD_LOG, f"remake({args.channel}): count Short {sid} toward the cap")
        print(f"  live: https://youtu.be/{vid}")

        # The old clip is only hidden after the new one is safely recorded, and a
        # clip that is still earning is left alone: those views are already ours.
        if args.old != "keep":
            v = views_of(yt, old_id)
            if args.old == "unlist-low" and v >= args.old_view_threshold:
                rem["shorts"][sid]["old_privacy"] = "public"
                print(f"  old {old_id} kept public ({v} views >= {args.old_view_threshold})")
            else:
                privacy = "private" if args.old == "private" else "unlisted"
                try:
                    set_privacy(yt, old_id, privacy)
                    rem["shorts"][sid]["old_privacy"] = privacy
                    print(f"  old {old_id} -> {privacy} ({v} views); reversible")
                except HttpError as exc:
                    # Usually the shared Data API quota: the upload above spent it.
                    # Leave it pending so a later run finishes the move.
                    rem["shorts"][sid]["old_privacy_pending"] = privacy
                    print(f"  old clip not moved ({exc.status_code}); left as it was, "
                          f"pending a later run", file=sys.stderr)
            ps.save(rem, rpath)
            ps.commit(rpath, f"remake({args.channel}): record the old clip's privacy")

    print(f"\n{len([v for v in rem['shorts'].values() if v.get('video_id')])}"
          f"/{len(scripts)} shorts remade")
    return rc


if __name__ == "__main__":
    sys.exit(main())
