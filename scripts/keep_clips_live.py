"""Keep clips that our manifests record as published actually public.

Measured 2026-11-22: `rogue-guard` paused six freshly published clips because the
runner's checkout still called them "unrecorded" (a pod build records its upload
locally; those commits cannot be pushed while the push token is refused). This
tool is the invariant side of that bug: for the ids named, the manifest says
"published", so the live status must be `public`. It reports every clip that is
not, and with `--apply` puts it back. `--watch` re-checks on an interval, which
is what keeps the clips up until the rail itself is fixed.

    python3 scripts/keep_clips_live.py --ids HkFULkG2sRk,7zALsTXwueU
    python3 scripts/keep_clips_live.py --ids ... --apply --watch --hours 6
"""
import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TOKEN_ENV = {"ch1": "YT_CH1_REFRESH_TOKEN", "ch2": "YT_CH2_REFRESH_TOKEN",
             "ch3": "YT_CH3_REFRESH_TOKEN", "ch4": "YT_CH4_REFRESH_TOKEN"}
MANIFESTS = {"ch1": "content/ch1_publish.json", "ch2": "content/ch2_publish.json",
             "ch3": "content/ch3_publish.json", "ch4": "content/ch4_publish.json"}


def token(channel: str) -> str:
    env = TOKEN_ENV[channel]
    data = urllib.parse.urlencode({
        "client_id": os.environ["YT_CLIENT_ID"],
        "client_secret": os.environ["YT_CLIENT_SECRET"],
        "refresh_token": os.environ[env], "grant_type": "refresh_token"}).encode()
    with urllib.request.urlopen("https://oauth2.googleapis.com/token", data) as r:
        return json.load(r)["access_token"]


def owner_of(video_id: str) -> str:
    """Which channel's manifest records this id (empty when nothing does)."""
    for ch, rel in MANIFESTS.items():
        path = os.path.join(ROOT, rel)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as fh:
            for v in json.load(fh).get("videos", []):
                if v.get("video_id") == video_id:
                    return ch
    return ""


def state_of(video_id: str, channel: str, access: str) -> dict:
    q = urllib.parse.urlencode({"part": "status,snippet", "id": video_id})
    req = urllib.request.Request(f"https://www.googleapis.com/youtube/v3/videos?{q}",
                                 headers={"Authorization": f"Bearer {access}"})
    items = json.load(urllib.request.urlopen(req)).get("items", [])
    return items[0] if items else {}


def make_public(video_id: str, access: str) -> str:
    body = {"id": video_id, "status": {
        "privacyStatus": "public", "selfDeclaredMadeForKids": False,
        "license": "youtube", "embeddable": True, "publicStatsViewable": True}}
    req = urllib.request.Request(
        "https://www.googleapis.com/youtube/v3/videos?part=status",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {access}",
                 "Content-Type": "application/json"}, method="PUT")
    with urllib.request.urlopen(req) as r:
        return json.load(r)["status"]["privacyStatus"]


def sweep(ids: list, apply: bool) -> int:
    """Return the number of clips that are not public."""
    bad = 0
    by_ch = {}
    for vid in ids:
        by_ch.setdefault(owner_of(vid), []).append(vid)
    for ch, vids in by_ch.items():
        if not ch:
            print(f"  {vids}: in no manifest -- skipped (not ours to publish)")
            continue
        access = token(ch)
        for vid in vids:
            it = state_of(vid, ch, access)
            if not it:
                print(f"  {vid} ({ch}): gone (deleted or wrong channel)")
                bad += 1
                continue
            privacy = it["status"]["privacyStatus"]
            title = it["snippet"]["title"][:40]
            if privacy == "public":
                print(f"  OK   {vid} ({ch}) public | {title}")
                continue
            bad += 1
            print(f"  DOWN {vid} ({ch}) {privacy} | {title}")
            if apply:
                now = make_public(vid, access)
                print(f"       -> set {now}")
                bad -= 1 if now == "public" else 0
    return bad


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", required=True, help="comma separated video ids")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--watch", action="store_true")
    ap.add_argument("--interval", type=float, default=300.0)
    ap.add_argument("--hours", type=float, default=6.0)
    a = ap.parse_args()
    ids = [x.strip() for x in a.ids.split(",") if x.strip()]
    end = time.time() + a.hours * 3600
    while True:
        print(f"-- {time.strftime('%H:%M:%S')} {len(ids)} clips", flush=True)
        bad = sweep(ids, a.apply)
        print(f"   not public: {bad}", flush=True)
        if not a.watch or time.time() >= end:
            return 0 if bad == 0 else 1
        time.sleep(a.interval)


if __name__ == "__main__":
    sys.exit(main())
