#!/usr/bin/env python3
"""Upload ready videos to a channel from a manifest -- no browser, no human.

This is the rail that turns a finished, verified render into a live video. It is
built to run on a CI runner, where the pod's problems (a recycled login, a
10,000-unit daily quota shared with every other call) do not apply to a fresh
day's upload quota.

    python3 scripts/publish_batch.py --dry-run       # show what it would post
    python3 scripts/publish_batch.py                 # upload every 'ready' entry
    python3 scripts/publish_batch.py --only night_120
    python3 scripts/publish_batch.py --privacy private   # override for a test

Double-post safety: an entry with a `video_id` is never uploaded again, and the
manifest is written back the moment an upload returns an id. `videos.insert` has
its own daily quota (100/day) separate from the read endpoints, so a spent
read-quota does not block publishing -- but it does block the thumbnail step,
which is best-effort and never fatal.

Credentials: YT_CLIENT_ID, YT_CLIENT_SECRET and YT_<SLUG>_REFRESH_TOKEN, exactly
like scripts/set_thumbnails.py and publish_youtube.py.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

MANIFEST = os.path.join(ROOT, "content", "ch2_publish.json")
TOKEN_ENV = {
    "dharma": "YT_CH2_REFRESH_TOKEN",
    "genx": "YT_CH1_REFRESH_TOKEN",
    "aeris-music": "YT_CH3_REFRESH_TOKEN",
    "kongkeat-story": "YT_CH4_REFRESH_TOKEN",
}
SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
          "https://www.googleapis.com/auth/youtube"]


def access_token(slug: str) -> str:
    cid = os.environ.get("YT_CLIENT_ID")
    sec = os.environ.get("YT_CLIENT_SECRET")
    var = TOKEN_ENV.get(slug, f"YT_{slug.upper().replace('-', '_')}_REFRESH_TOKEN")
    rt = os.environ.get(var)
    if not (cid and sec and rt):
        sys.exit(f"Missing credentials: need YT_CLIENT_ID, YT_CLIENT_SECRET and {var}")
    data = urllib.parse.urlencode({
        "client_id": cid, "client_secret": sec,
        "refresh_token": rt, "grant_type": "refresh_token"}).encode()
    try:
        return json.load(urllib.request.urlopen(
            "https://oauth2.googleapis.com/token", data=data, timeout=30))["access_token"]
    except urllib.error.HTTPError as exc:
        sys.exit(f"Token refresh failed for {slug} ({var}): {exc.code} {exc.read().decode()[:200]}")


def _due(v: dict) -> bool:
    """False while a video is deliberately held for cadence (not_before in the future)."""
    nb = v.get("not_before")
    if not nb:
        return True
    from datetime import datetime, timezone
    try:
        when = datetime.fromisoformat(nb.replace("Z", "+00:00"))
    except ValueError:
        return True
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) >= when


def save(man: dict, path: str) -> None:
    tmp = path + ".part"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(man, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    os.replace(tmp, path)


def commit(path: str, message: str) -> None:
    """Persist the manifest to git as soon as an id is known. An id that lives
    only on an ephemeral runner is lost if the run dies before the workflow's
    commit step, and the next run would upload the same video again."""
    if not os.environ.get("GITHUB_ACTIONS"):
        return
    try:
        subprocess.run(["git", "add", os.path.relpath(path, ROOT)], cwd=ROOT, check=True)
        subprocess.run(["git", "-c", "user.name=openhands",
                        "-c", "user.email=openhands@all-hands.dev",
                        "commit", "-q", "-m", message], cwd=ROOT, check=True)
        # Rebase before pushing. Two runs can land a commit each in the same
        # second; a bare push then loses the loser's id, and the id is the only
        # thing stopping a re-upload. Measured 2026-11-03: a rejected push lost
        # tSgNrHJGVoo this way and left a duplicate 120-minute video live.
        subprocess.run(["git", "-c", "user.name=openhands",
                        "-c", "user.email=openhands@all-hands.dev",
                        "pull", "--rebase", "--autostash", "origin", "main"],
                       cwd=ROOT, check=True, capture_output=True, timeout=120)
        subprocess.run(["git", "push"], cwd=ROOT, check=True,
                       capture_output=True, timeout=300)
        print("  manifest committed")
    except subprocess.CalledProcessError as exc:
        print(f"  manifest commit failed (the workflow step will retry): {exc}",
              file=sys.stderr)


def _upload_capped(channel_id: str) -> str | None:
    """Return the recorded reset time if this channel is known to be upload-capped.

    ch4 is on a per-channel upload cap most days ("uploadLimitExceeded"); the pod
    records when it was hit and when it clears in content/upload_limit.json.
    Checking it here saves a 132 MB download on every capped tick.
    """
    from datetime import datetime, timezone
    path = os.path.join(ROOT, "content", "upload_limit.json")
    if not os.path.exists(path):
        return None
    rec = json.load(open(path, encoding="utf-8")).get("channels", {}).get(channel_id)
    if not rec or not rec.get("reset_at"):
        return None
    try:
        when = datetime.fromisoformat(rec["reset_at"].replace("Z", "+00:00"))
    except ValueError:
        return None
    return rec["reset_at"] if when > datetime.now(timezone.utc) else None


def _note_upload_capped(channel_id: str, detail: str) -> None:
    """Record a per-channel upload cap, with the reset the API actually honours.

    "uploadLimitExceeded" is the per-channel daily cap; it clears at midnight
    Pacific (08:00 UTC), not a few hours after it is hit. The pod's 3-hour probe
    window is wrong for this error, so set the reset to the next 08:00 UTC.
    """
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    reset = now.replace(hour=8, minute=0, second=0, microsecond=0)
    if reset <= now:
        reset += timedelta(days=1)
    path = os.path.join(ROOT, "content", "upload_limit.json")
    data = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {"channels": {}}
    data.setdefault("channels", {})[channel_id] = {
        "hit_at": now.isoformat(timespec="seconds"),
        "reset_at": reset.isoformat(timespec="seconds"),
        "probe_hours": 24,
        "detail": detail[:200],
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    print(f"  recorded upload cap; resets {reset.isoformat(timespec='seconds')}")


def existing_titles(yt, channel_id: str) -> dict:
    """Map exact title -> video_id for everything already on the channel.

    This is the guard that makes a re-upload impossible even when the manifest
    is stale. `actions/checkout` pins the run to the SHA it was created with, so
    a run that starts after a sibling's commit still reads the manifest from
    *before* that commit -- that is exactly how night_120 was posted twice on
    2026-11-03 (F4qFHoVpEyI by one run, tSgNrHJGVoo by the next). The live
    channel is the only source that cannot be stale, so ask it.
    """
    up = yt.channels().list(part="contentDetails", id=channel_id).execute()
    pl = up["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    out, page = {}, None
    while True:
        req = yt.playlistItems().list(part="snippet", playlistId=pl, maxResults=50)
        if page:
            req = yt.playlistItems().list(part="snippet", playlistId=pl,
                                          maxResults=50, pageToken=page)
        r = req.execute()
        for it in r["items"]:
            sn = it["snippet"]
            out.setdefault(sn["title"], sn["resourceId"]["videoId"])
        page = r.get("nextPageToken")
        if not page:
            return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default=MANIFEST)
    ap.add_argument("--only", action="append")
    ap.add_argument("--privacy", choices=["private", "unlisted", "public"])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--forget", metavar="KEY",
                    help="clear a recorded video_id (for a known duplicate that was deleted)")
    ap.add_argument("--cache", default=os.path.join(ROOT, "work", "publish_cache"))
    ap.add_argument("--publish-at", metavar="ISO8601", default=None,
                    help="schedule release (e.g. 2026-11-09T12:30:00Z): uploads "
                         "private with status.publishAt, so the slot fires even if "
                         "the cron that would flip it to public is dropped")
    args = ap.parse_args()

    with open(args.manifest, encoding="utf-8") as fh:
        man = json.load(fh)
    slug = man["channel_slug"]
    vids = man["videos"]
    if args.only:
        vids = [v for v in vids if v["key"] in args.only]

    if args.forget:
        hit = [v for v in man["videos"] if v["key"] == args.forget]
        if not hit or not hit[0].get("video_id"):
            sys.exit(f"{args.forget}: no recorded video_id to forget")
        print(f"{args.forget}: forgetting {hit[0]['video_id']}")
        for field in ("video_id", "url"):
            hit[0].pop(field, None)
        hit[0]["state"] = "ready"
        save(man, args.manifest)
        return 0

    todo = [v for v in vids if not v.get("video_id") and _due(v)
            and v.get("state") != "blocked"]
    held = [v for v in vids if not v.get("video_id") and not _due(v)
            and v.get("state") != "blocked"]
    blocked = [v for v in vids if not v.get("video_id") and v.get("state") == "blocked"]
    done = [v for v in vids if v.get("video_id")]
    print(f"channel {slug} ({man['channel_id']}): {len(todo)} to publish, "
          f"{len(held)} held, {len(blocked)} blocked, {len(done)} already live")
    for v in blocked:
        why = "; ".join((v.get("qa") or {}).get("reasons") or ["QA veto"])
        print(f"  {v['key']}: BLOCKED by QA — {why}")
    for v in held:
        print(f"  {v['key']}: held until {v.get('not_before')} — cadence, not a block")
    for v in done:
        print(f"  {v['key']}: already live {v['video_id']} — skipping")

    if args.dry_run:
        for v in todo:
            print(f"  {v['key']}: would upload {v['video_url']}")
            print(f"      title   {v['title']}")
            print(f"      privacy {args.privacy or v.get('privacy','public')}")
            print(f"      thumb   {v.get('thumbnail','-')}")
        return 0
    if not todo:
        # Still worth running when nothing new is due: a previously-live video
        # may be waiting on its playlist insert (see the repair pass).
        needs_repair = any(v.get("video_id") and v.get("playlist")
                           and not v.get("playlist_added") for v in man["videos"])
        if not needs_repair:
            print("nothing to do")
            return 0
        print("nothing new to upload; checking playlist repair")

    capped = _upload_capped(man["channel_id"])
    if capped and todo:
        print(f"channel {man['channel_id']} is upload-capped until {capped}; "
              f"deferring (the scheduled tick will retry after the reset)")
        return 0

    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from googleapiclient.errors import HttpError
    from google.oauth2.credentials import Credentials

    # Build credentials straight from the environment. yt_auth.load_credentials()
    # verifies the token's channel with channels.list, a quota-limited call: when
    # the shared daily quota is spent it cannot tell which channel a token owns
    # and gives up. Publishing must not depend on a read call, so the token is
    # taken as-is here and the channel is checked below, tolerating a quota 403.
    token = access_token(slug)
    creds = Credentials(token=token, refresh_token=os.environ[
        TOKEN_ENV.get(slug, f"YT_{slug.upper().replace('-', '_')}_REFRESH_TOKEN")],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["YT_CLIENT_ID"], client_secret=os.environ["YT_CLIENT_SECRET"])
    yt = build("youtube", "v3", credentials=creds, cache_discovery=False)

    # Refuse to post to the wrong channel before a single byte moves -- but a
    # quota error is not a wrong channel, so only a real mismatch aborts.
    try:
        res = yt.channels().list(part="snippet", mine=True).execute()
        got = res["items"][0]["id"] if res.get("items") else None
        if got != man["channel_id"]:
            sys.exit(f"WRONG CHANNEL: token is {got}, manifest says {man['channel_id']}")
        print(f"  authorised as {res['items'][0]['snippet']['title']} ({got})")
    except HttpError as exc:
        print(f"  channel check skipped ({exc.status_code}); "
              f"the per-channel secret pins the target channel", file=sys.stderr)

    os.makedirs(args.cache, exist_ok=True)
    # The live channel, not the manifest, is the authority on what is already
    # posted -- see existing_titles() for why the manifest can be stale.
    try:
        posted = existing_titles(yt, man["channel_id"])
        print(f"  channel holds {len(posted)} videos; will refuse to re-upload any of them")
    except HttpError as exc:
        print(f"  could not read the channel ({exc.status_code}); "
              f"falling back to the manifest's own video_id guard", file=sys.stderr)
        posted = {}
    rc = 0
    for v in todo:
        key = v["key"]
        if v["title"] in posted:
            vid = posted[v["title"]]
            print(f"\n{key}: SKIP — an identical title is already live ({vid}); "
                  f"recording it instead of re-uploading")
            v["video_id"] = vid
            v["url"] = f"https://youtu.be/{vid}"
            v["state"] = "published"
            save(man, args.manifest)
            commit(args.manifest, f"publish({slug}): {key} already live as {vid} — not re-uploaded")
            continue
        local = os.path.join(args.cache, f"{key}.mp4")
        if not (os.path.exists(local) and os.path.getsize(local) > 0):
            print(f"downloading {v['video_url']} -> {local}")
            req = urllib.request.Request(v["video_url"],
                                         headers={"User-Agent": "content-lab-publish/1.0"})
            with urllib.request.urlopen(req, timeout=1800) as src, open(local, "wb") as out:
                while True:
                    chunk = src.read(1 << 18)
                    if not chunk:
                        break
                    out.write(chunk)
        privacy = args.privacy or v.get("privacy", "public")
        body = {
            "snippet": {
                "title": v["title"][:100],
                "description": v.get("description", "")[:5000],
                "tags": v.get("tags", [])[:500],
                "categoryId": str(v.get("category_id", "22")),
                "defaultLanguage": "th",
                "defaultAudioLanguage": "th",
            },
            "status": {
                "privacyStatus": privacy,
                "selfDeclaredMadeForKids": False,
                "license": "youtube",
                "embeddable": True,
            },
        }
        # A scheduled release is the safe way to hit a fixed slot: YouTube holds
        # the video private and flips it public at publishAt on its own clock, so
        # a dropped cron tick cannot miss the slot. It requires privacyStatus
        # private; the API rejects publishAt on a public insert.
        if args.publish_at:
            body["status"]["privacyStatus"] = "private"
            body["status"]["publishAt"] = args.publish_at
            privacy = "private"
            print(f"  scheduled release at {args.publish_at} (held private until then)")
        print(f"\nuploading {key} ({os.path.getsize(local)/1e6:.0f} MB) as {privacy} ...")
        try:
            request = yt.videos().insert(
                part="snippet,status", body=body,
                media_body=MediaFileUpload(local, chunksize=16 * 1024 * 1024,
                                           resumable=True))
            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    print(f"  {int(status.progress() * 100)}%", flush=True)
        except HttpError as exc:
            text = str(exc)
            if "uploadLimitExceeded" in text or "Video Uploads per day" in text:
                _note_upload_capped(man["channel_id"], text)
                print(f"  {key}: channel upload cap hit; deferred to the next reset",
                      file=sys.stderr)
                continue
            print(f"  UPLOAD FAILED: {exc}", file=sys.stderr)
            rc = 1
            continue

        vid = response["id"]
        url = f"https://youtu.be/{vid}"
        v["video_id"] = vid
        v["url"] = url
        v["state"] = "published"
        save(man, args.manifest)   # record BEFORE anything else can fail
        commit(args.manifest, f"publish({slug}): record {key}")
        print(f"  live: {url} ({response['status']['privacyStatus']}) — recorded")

        thumb = v.get("thumbnail")
        if thumb:
            path = thumb if os.path.isabs(thumb) else os.path.join(ROOT, thumb)
            try:
                yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(path)).execute()
                v["thumbnail_set"] = True
                save(man, args.manifest)
                print("  thumbnail set")
            except HttpError as exc:
                print(f"  thumbnail deferred ({exc.status_code}); "
                      f"set_thumbnails.py will finish it", file=sys.stderr)

        pl = v.get("playlist")
        if pl:
            try:
                yt.playlistItems().insert(part="snippet", body={"snippet": {
                    "playlistId": pl, "resourceId": {"kind": "youtube#video", "videoId": vid}}}).execute()
                v["playlist_added"] = True
                save(man, args.manifest)
                print(f"  added to playlist {pl}")
            except HttpError as exc:
                # Not fatal: the repair pass below retries every run until it
                # lands. A quota 403 here is the common case, and without the
                # retry the video would be live forever with the funnel still
                # pointing at an empty playlist.
                print(f"  playlist insert deferred ({exc.status_code}); "
                      f"the repair pass will retry", file=sys.stderr)

    # Repair pass: an entry can be live with its playlist insert missing -- a
    # quota 403 at upload time leaves it that way, and `state=published` means
    # the main loop never touches it again. Re-attempt every run; the flag makes
    # a success permanent, so this costs one call per not-yet-added video.
    pending = [v for v in man["videos"]
               if v.get("video_id") and v.get("playlist") and not v.get("playlist_added")]
    for v in pending:
        try:
            yt.playlistItems().insert(part="snippet", body={"snippet": {
                "playlistId": v["playlist"],
                "resourceId": {"kind": "youtube#video", "videoId": v["video_id"]}}}).execute()
            v["playlist_added"] = True
            save(man, args.manifest)
            print(f"repaired: {v['key']} -> playlist {v['playlist']}")
        except HttpError as exc:
            print(f"  playlist repair deferred for {v['key']} ({exc.status_code})",
                  file=sys.stderr)

    # Thumbnail repair, for the same reason as the playlist one: a quota 403 at
    # upload time leaves a published video wearing a frame grabbed from its own
    # second minute, and nothing retries it. `thumbnails.set` is idempotent, so a
    # re-set costs nothing and the flag makes a success permanent.
    for v in [x for x in man["videos"]
              if x.get("video_id") and x.get("thumbnail") and not x.get("thumbnail_set")]:
        path = v["thumbnail"] if os.path.isabs(v["thumbnail"]) else os.path.join(ROOT, v["thumbnail"])
        if not os.path.exists(path):
            continue
        try:
            yt.thumbnails().set(videoId=v["video_id"],
                                media_body=MediaFileUpload(path)).execute()
            v["thumbnail_set"] = True
            save(man, args.manifest)
            print(f"repaired: {v['key']} -> thumbnail")
        except HttpError as exc:
            print(f"  thumbnail repair deferred for {v['key']} ({exc.status_code})",
                  file=sys.stderr)

    live = [v for v in man["videos"] if v.get("video_id")]
    print(f"\n{len(live)}/{len(man['videos'])} live: " +
          ", ".join(f"{v['key']}={v['url']}" for v in live))
    return rc


if __name__ == "__main__":
    sys.exit(main())
