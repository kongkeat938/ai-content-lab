#!/usr/bin/env python3
"""Build and publish vertical Shorts to a channel -- the reach engine.

Shorts are shown to people who have never seen the channel, so they are how a
small channel gets discovered. The long video is what collects the watch hours
the Partner Programme counts. So every Short this script publishes carries a link
to the long video: the funnel is Short -> long.

    python3 scripts/publish_shorts.py --dry-run
    python3 scripts/publish_shorts.py                 # build + upload what is due
    python3 scripts/publish_shorts.py --per-run 1     # cadence: one per run

It builds with scripts/make_short.py (edge-tts + ffmpeg, both free), so a CI
runner needs no prebuilt file. Double-post safety matches publish_batch.py: an
entry with a video_id is never uploaded again, and the id is written to the
manifest before anything else can fail.

Credentials: YT_CLIENT_ID, YT_CLIENT_SECRET and YT_CH2_REFRESH_TOKEN.
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
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

SCRIPTS = os.path.join(ROOT, "content", "ch2_shorts", "scripts.json")
MANIFEST = os.path.join(ROOT, "content", "ch2_shorts.json")
CHANNEL_ID = "UCM3QO5L_pmj34n1JVlbhh-w"
TOKEN_ENV = "YT_CH2_REFRESH_TOKEN"
LONG_URL = "https://youtu.be/F4qFHoVpEyI"
LONG_TITLE = "ธรรมะก่อนนอน 120 นาที"


def access_token() -> str:
    cid, sec = os.environ.get("YT_CLIENT_ID"), os.environ.get("YT_CLIENT_SECRET")
    rt = os.environ.get(TOKEN_ENV)
    if not (cid and sec and rt):
        sys.exit(f"Missing credentials: need YT_CLIENT_ID, YT_CLIENT_SECRET and {TOKEN_ENV}")
    data = urllib.parse.urlencode({"client_id": cid, "client_secret": sec,
                                   "refresh_token": rt, "grant_type": "refresh_token"}).encode()
    try:
        return json.load(urllib.request.urlopen(
            "https://oauth2.googleapis.com/token", data=data, timeout=30))["access_token"]
    except urllib.error.HTTPError as exc:
        sys.exit(f"Token refresh failed: {exc.code} {exc.read().decode()[:200]}")


def load(path: str, default):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    return default


def save(man, path: str) -> None:
    tmp = path + ".part"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(man, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    os.replace(tmp, path)


LIMIT_FILE = os.path.join(ROOT, "content", "upload_limit.json")


def note_upload_limit() -> None:
    """Remember that the channel is out of upload slots until the daily reset.

    The ceiling is per channel per day and resets at midnight Pacific (08:00 UTC).
    Without this note the foreman re-dispatches the rail every tick, and every
    tick burns a run to learn the same thing. The note is what makes the foreman
    skip a rail that cannot possibly succeed yet.
    """
    now = datetime.now(timezone.utc)
    reset = now.replace(hour=8, minute=0, second=0, microsecond=0)
    if reset <= now:
        reset = reset + timedelta(days=1)
    payload = {"channel_id": CHANNEL_ID, "hit_at": now.isoformat(timespec="seconds"),
               "reset_at": reset.isoformat(timespec="seconds")}
    with open(LIMIT_FILE, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    print(f"  recorded upload limit; resets {payload['reset_at']}")
    commit(LIMIT_FILE, "publish(ch2): record the daily upload limit")


def commit(path: str, message: str) -> None:
    """Persist the manifest to git the moment an id is known.

    The CI runner is ephemeral: if the run dies before the workflow's commit step
    (a cancel, an upload-limit abort), an id that lives only on the runner is
    lost, and the next run re-uploads the same Short. Committing here makes the
    record survive the run it was made in.
    """
    if not os.environ.get("GITHUB_ACTIONS"):
        return
    try:
        subprocess.run(["git", "add", os.path.relpath(path, ROOT)], cwd=ROOT, check=True)
        subprocess.run(["git", "-c", "user.name=openhands",
                        "-c", "user.email=openhands@all-hands.dev",
                        "commit", "-q", "-m", message], cwd=ROOT, check=True)
        subprocess.run(["git", "push"], cwd=ROOT, check=True,
                       capture_output=True, timeout=120)
        print("  manifest committed")
    except subprocess.CalledProcessError as exc:
        print(f"  manifest commit failed (will retry at the workflow step): {exc}",
              file=sys.stderr)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--per-run", type=int, default=0, help="upload at most N per run (0 = all)")
    ap.add_argument("--privacy", default="public", choices=["private", "unlisted", "public"])
    ap.add_argument("--work", default=os.path.join(ROOT, "work", "ch2_shorts"))
    args = ap.parse_args()

    scripts = load(SCRIPTS, [])
    man = load(MANIFEST, {"channel_slug": "dharma", "channel_id": CHANNEL_ID, "shorts": {}})
    if not scripts:
        sys.exit(f"no scripts at {SCRIPTS}")

    # If a previous run already hit the channel's daily upload ceiling, do not
    # build anything -- the upload cannot succeed until the reset, and a build
    # here costs minutes for nothing.
    lim = load(LIMIT_FILE, {})
    if lim.get("reset_at"):
        if datetime.fromisoformat(lim["reset_at"].replace("Z", "+00:00")) > datetime.now(timezone.utc):
            print(f"channel upload limit recorded; resets {lim['reset_at']} -- nothing to do")
            return 0

    todo = [s for s in scripts if not man["shorts"].get(s["id"], {}).get("video_id")]
    if args.per_run:
        todo = todo[:args.per_run]
    done = [s["id"] for s in scripts if man["shorts"].get(s["id"], {}).get("video_id")]
    print(f"{len(todo)} to publish, {len(done)} already live {done}")

    if args.dry_run:
        for s in todo:
            print(f"  {s['id']}: {s['hook']}")
        return 0
    if not todo:
        print("nothing to do")
        return 0

    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from googleapiclient.errors import HttpError
    from google.oauth2.credentials import Credentials

    creds = Credentials(token=access_token(), refresh_token=os.environ[TOKEN_ENV],
                        token_uri="https://oauth2.googleapis.com/token",
                        client_id=os.environ["YT_CLIENT_ID"],
                        client_secret=os.environ["YT_CLIENT_SECRET"])
    yt = build("youtube", "v3", credentials=creds, cache_discovery=False)
    try:
        res = yt.channels().list(part="snippet", mine=True).execute()
        got = res["items"][0]["id"]
        if got != CHANNEL_ID:
            sys.exit(f"WRONG CHANNEL: token is {got}, expected {CHANNEL_ID}")
        print(f"  authorised as {res['items'][0]['snippet']['title']} ({got})")
    except HttpError as exc:
        print(f"  channel check skipped ({exc.status_code})", file=sys.stderr)

    rc = 0
    for s in todo:
        sid = s["id"]
        # Build if needed (CI has no prebuilt file).
        out = os.path.join(args.work, sid, f"short_{sid}.mp4")
        if not os.path.exists(out):
            print(f"building {sid} ...")
            r = subprocess.run([sys.executable, os.path.join(HERE, "make_short.py"),
                                "--index", sid, "--out-dir", args.work],
                               capture_output=True, text=True)
            if r.returncode != 0:
                print(f"  build failed: {r.stderr[-400:]}", file=sys.stderr)
                rc = 1
                continue
        if not os.path.exists(out):
            print(f"  {sid}: no output at {out}", file=sys.stderr)
            rc = 1
            continue

        description = (f"{s['hook']}\n\n" + "\n".join(s["lines"]) +
                       f"\n\n{s['cta']}\n\nฟังเวอร์ชันเต็ม 120 นาทีได้ที่นี่ "
                       f"→ {LONG_URL}\n\n#ธรรมะก่อนนอน #นอนไม่หลับ #ปล่อยวาง")
        body = {
            "snippet": {
                "title": (s["hook"][:95] + " #Shorts")[:100],
                "description": description[:5000],
                "tags": ["ธรรมะก่อนนอน", "นอนไม่หลับ", "ปล่อยวาง", "ธรรมะ", "สมาธิ",
                         "คลายเครียด", "ฟังก่อนนอน", "Farmmer", "Shorts"],
                "categoryId": "22",
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
            if "uploadLimitExceeded" in text:
                # The channel has hit its daily upload ceiling. This is an expected
                # end to the day, not a fault: stop, and do not mark the run failed,
                # or every day would look broken and the real failures hide.
                print("  daily upload limit reached; stopping this run", file=sys.stderr)
                note_upload_limit()
                break
            rc = 1
            continue
        vid = response["id"]
        man["shorts"][sid] = {"video_id": vid, "url": f"https://youtu.be/{vid}",
                              "title": body["snippet"]["title"]}
        save(man, MANIFEST)   # record before anything else can fail
        commit(MANIFEST, f"publish(ch2): record Short {sid}")
        print(f"  live: https://youtu.be/{vid}")

    print(f"\n{len([v for v in man['shorts'].values() if v.get('video_id')])}"
          f"/{len(scripts)} shorts live")
    return rc


if __name__ == "__main__":
    sys.exit(main())
