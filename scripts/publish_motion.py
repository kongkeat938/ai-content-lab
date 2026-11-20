#!/usr/bin/env python3
"""Upload a MOTION Short (an animated still) to its channel, under the same gates.

`make_motion_short.py` builds a livelier Shorts shape, but it was a tool, not a
rail: the clips were uploaded by hand, so nothing carried the channel's cap, the
2 h gap, the pace gate, the standard gate, the bed ledger or the CTA. Measured
2026-11-19: K asked for the four fixed clips to go up "ทุกช่องทาง" and there was
no path that could do it without re-implementing all of those.

This is that path, and it holds no rule of its own. Every gate is imported from
`publish_shorts` -- the cap (`uploads_in_last_24h`), the gap and pace verdict
(`pace.gate`), the standard (`short_standard.verify_short`), the bed choice
(`pick_bed`, no two clips share one), the description tail, the pinned CTA and
the record (`note_upload` + the manifest). A second copy of a rule is how the
false-alarm bug survived in `link-shorts`, so there is exactly one copy.

    python3 scripts/publish_motion.py --story content/motion/03.json --dry-run
    python3 scripts/publish_motion.py --story content/motion/03.json --channel genx

The story names its own channel through `genre`; `--channel` overrides that and
must agree with the token, which is checked live before a byte moves.

Quota note: `videos.insert` has its own pool, so publishing is never what runs
the 10,000-unit Data API budget out. The cap and the gap are about the FEED
(measured 2026-11-05: 89 Shorts in a day, median views 1), not about quota.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import pace                      # noqa: E402 - local module
import publish_shorts as PS      # noqa: E402 - one source for every gate
import short_standard            # noqa: E402

# A story's `genre` is the layer profile AND the channel it was written for.
GENRE_CHANNEL = {"dharma": "dharma", "genx": "genx", "knowledge": "kongkeat"}


def record_key(sid: str) -> str:
    """The manifest key a motion story is recorded under.

    A motion story is numbered 01..04, and so is the channel's own script pool
    (`content/ch2_shorts/scripts.json` ids 1..185). Measured 2026-11-19: dharma's
    `shorts["01"]` is already a live video from 2026-11-03, so recording a motion
    clip under the bare id would overwrite a real upload's id and make the next
    run upload it again. The prefix keeps the two id spaces apart.
    """
    return f"motion-{sid}"


def build(story_path: str, out_dir: str) -> tuple[str, str, str]:
    """Build the clip and its 9:16 thumbnail; return (video, thumb, work_dir)."""
    with open(story_path, encoding="utf-8") as fh:
        story = json.load(fh)
    sid = str(story["id"])
    work = os.path.join(out_dir, sid)
    video = os.path.join(work, f"motion_{sid}.mp4")
    thumb = os.path.join(work, f"thumb_{sid}.jpg")
    os.makedirs(work, exist_ok=True)

    if not os.path.exists(video):
        cmd = [sys.executable, os.path.join(HERE, "make_motion_short.py"),
               "--story", story_path, "--out-dir", out_dir]
        bed = PS.pick_bed(PS.CHANNELS[GENRE_CHANNEL[story["genre"]]]["music_dir"],
                          sid, story.get("mood"), PS.bed_ledger_path(
                              GENRE_CHANNEL[story["genre"]]))
        if bed:
            cmd += ["--music", bed]
        r = subprocess.run(cmd, capture_output=True, text=True,
                           stdin=subprocess.DEVNULL)
        if r.returncode != 0:
            raise RuntimeError(f"build failed: {(r.stderr or r.stdout)[-600:]}")

    if not os.path.exists(thumb):
        cmd = [sys.executable, os.path.join(HERE, "make_short_thumbnail.py"),
               "--hook", story["hook"], "--out", thumb, "--video", video]
        r = subprocess.run(cmd, capture_output=True, text=True,
                           stdin=subprocess.DEVNULL)
        if r.returncode != 0:
            raise RuntimeError(f"thumbnail failed: {(r.stderr or r.stdout)[-400:]}")
    return video, thumb, work


def commit(paths: list[str], message: str) -> None:
    """Commit the record, but only inside CI.

    `publish_shorts.commit` is the model, and it deliberately does nothing
    outside GitHub Actions: from a pod K has not approved a push, and an id that
    only reaches a local git index is worse than none -- the ledger the cap reads
    would disagree with the channel. In CI the workflow's own step pushes this
    commit, so the count and the channel stay in step (Gemini, 2026-11-19: a pod
    upload would desync the two and risk the over-quota flood).
    """
    if not os.environ.get("GITHUB_ACTIONS"):
        print("  (not in CI: record written locally, no commit -- the workflow "
              "step commits and pushes it)")
        return
    gitc = ["git", "-c", "user.name=openhands",
            "-c", "user.email=openhands@all-hands.dev"]
    rel = [os.path.relpath(p, ROOT) for p in paths if os.path.exists(p)]
    if not rel:
        return
    subprocess.run(["git", "add", *rel], cwd=ROOT, check=True,
                   stdin=subprocess.DEVNULL)
    if subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT,
                      stdin=subprocess.DEVNULL).returncode == 0:
        return
    subprocess.run(gitc + ["commit", "-q", "-m", message], cwd=ROOT, check=True,
                   stdin=subprocess.DEVNULL)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--story", required=True, help="content/motion/NN.json")
    ap.add_argument("--channel", choices=list(PS.CHANNELS), default=None,
                    help="override the channel; must match the story's genre")
    ap.add_argument("--out-dir", default=os.path.join(ROOT, "work", "motion_publish"))
    ap.add_argument("--privacy", default="private",
                    choices=["private", "unlisted", "public"])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    with open(args.story, encoding="utf-8") as fh:
        story = json.load(fh)
    sid = str(story["id"])
    genre = story.get("genre", "")
    if genre not in GENRE_CHANNEL:
        sys.exit(f"story {sid}: genre {genre!r} has no channel (known: "
                 f"{sorted(GENRE_CHANNEL)})")
    slug = args.channel or GENRE_CHANNEL[genre]
    if GENRE_CHANNEL[genre] != slug:
        sys.exit(f"story {sid} is written for {GENRE_CHANNEL[genre]}, not {slug}")
    if slug in PS.paused_channels():
        print(f"{slug} is paused (content/PAUSED); nothing to publish")
        return 0

    spec = PS.CHANNELS[slug]
    man = PS.load(spec["manifest"], {"channel_slug": slug,
                                     "channel_id": spec["channel_id"], "shorts": {}})
    key = record_key(sid)
    if man["shorts"].get(key, {}).get("video_id"):
        print(f"{key} is already live at {man['shorts'][key]['url']}; nothing to do")
        return 0

    # The cap and the gap are the feed's health, not the quota's -- same numbers
    # the Shorts rail uses, so a motion clip cannot become the way around them.
    already = PS.uploads_in_last_24h(slug, spec["manifest"])
    if already >= PS.DAILY_CAP:
        print(f"daily cap reached ({already}/{PS.DAILY_CAP} in the last 24h) -- "
              "waiting, a steady drip beats a flood")
        return 0
    since = PS.hours_since_last_upload(slug, spec["manifest"])
    if since is not None and since < PS.MIN_GAP_HOURS:
        print(f"only {since:.1f}h since the last upload (need {PS.MIN_GAP_HOURS}h) "
              "-- spacing the posts out")
        return 0

    video, thumb, work = build(args.story, args.out_dir)
    ok, reasons, metrics = short_standard.verify_short(video, thumb)
    print(f"  standard: {'PASS' if ok else 'HELD'} {metrics}")
    if not ok:
        # K's rule (2026-11-17): meet the standard or do not upload. A held clip
        # is loud, never silently shipped.
        print(f"{sid}: HELD below the minimum standard, not uploading:", file=sys.stderr)
        for why in reasons:
            print(f"    - {why}", file=sys.stderr)
        return 1

    description = (f"{story['hook']}\n\n" + "\n".join(story.get("lines", [])) +
                   f"\n\n{story.get('cta', '')}" + spec["tail"] +
                   (PS.MUSIC_CREDIT if spec.get("music_dir") else ""))
    body = {
        "snippet": {
            "title": (story["hook"][:95] + " #Shorts")[:100],
            "description": description[:5000],
            "tags": spec["tags"],
            "categoryId": spec["category"],
            "defaultLanguage": "th",
            "defaultAudioLanguage": "th",
        },
        "status": {"privacyStatus": args.privacy,
                   "selfDeclaredMadeForKids": False,
                   "license": "youtube", "embeddable": True},
    }
    if args.dry_run:
        print(json.dumps({"channel": slug, "story": sid, "body": body,
                          "file": video, "thumb": thumb,
                          "metrics": metrics}, ensure_ascii=False, indent=2))
        return 0

    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build as gbuild
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload

    creds = Credentials(
        token=PS.access_token(spec), refresh_token=os.environ[spec["token"]],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"])
    yt = gbuild("youtube", "v3", credentials=creds, cache_discovery=False)
    # Refuse before uploading a byte if the token belongs to another channel.
    got = yt.channels().list(part="snippet", mine=True).execute()["items"][0]
    if got["id"] != spec["channel_id"]:
        sys.exit(f"WRONG CHANNEL: token is {got['id']}, expected {spec['channel_id']}")
    print(f"  authorised as {got['snippet']['title']} ({got['id']})")

    rec = pace.gate(slug, spec["manifest"], token=PS.access_token(spec),
                    scripts=[story], cues=spec.get("cues"))
    if not rec["allowed"]:
        print(rec["reason"])
        return 0
    print(f"  pace: {rec['reason']}")

    print(f"uploading {sid} ({os.path.getsize(video)/1e6:.1f} MB) ...")
    try:
        request = yt.videos().insert(
            part="snippet,status", body=body,
            media_body=MediaFileUpload(video, chunksize=8 << 20, resumable=True))
        response = None
        while response is None:
            _, response = request.next_chunk()
    except HttpError as exc:
        text = str(exc)
        print(f"  UPLOAD FAILED: {text}", file=sys.stderr)
        if "uploadLimitExceeded" in text or "Video Uploads per day" in text:
            PS.note_upload_limit(spec["channel_id"], text)
        return 1

    vid = response["id"]
    posted_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    thumb_set = False
    try:
        yt.thumbnails().set(videoId=vid,
                            media_body=MediaFileUpload(thumb)).execute()
        thumb_set = True
        print("  thumbnail set")
    except HttpError as exc:
        print(f"  thumbnail deferred ({exc.status_code})", file=sys.stderr)
    note = PS.pin_cta_comment(yt, vid, spec, story, args.privacy)
    if note:
        print(f"  {note}")

    # Record before anything else can fail: an id that lives only in this shell
    # is an id the next run will upload again.
    man["shorts"][key] = {"video_id": vid, "url": f"https://youtu.be/{vid}",
                          "title": body["snippet"]["title"],
                          "posted_at": posted_at, "cta_note": note,
                          "thumbnail": os.path.relpath(thumb, ROOT),
                          "thumbnail_set": thumb_set,
                          "shape": PS.hook_shape(story, spec.get("cues")),
                          "kind": "motion"}
    PS.save(man, spec["manifest"])
    PS.note_upload(slug)
    # The record and the cap counter travel together, or the next run counts a
    # different number than the channel shows.
    commit([spec["manifest"], PS.UPLOAD_LOG,
            PS.bed_ledger_path(slug)],
           f"publish({slug}): record motion Short {key}")
    print(f"  live: https://youtu.be/{vid}")
    print(f"\n{slug}: {len([v for v in man['shorts'].values() if v.get('video_id')])}"
          f"/{len(man['shorts'])} shorts live")
    return 0


if __name__ == "__main__":
    sys.exit(main())
