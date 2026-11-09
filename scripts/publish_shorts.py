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
import re
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
# The beds are CC0 (Openverse/Freesound), so credit is an ask, not a condition.
# The AERIS pack that stood here first was replaced on 2026-11-07: it measured as
# test tones, not music (see scripts/test_music_beds.py).
MUSIC_CREDIT = "\n\n🎵 ดนตรีประกอบ: CC0 (Openverse / Freesound)"


def art_ledger_path(channel: str) -> str:
    return os.path.join(ROOT, "content", f"art_ledger_{channel}.json")


def bed_ledger_path(channel: str) -> str:
    return os.path.join(ROOT, "content", f"bed_ledger_{channel}.json")


LONG_PLAYLIST = "PLBpZCGnd7Q5Y"   # "หลับลึกทั้งคืน — ฟังยาว"

# One rail, several channels. The body below reads these rather than the module
# constants, so adding a channel is a data change, not a code change.
CHANNELS = {
    "dharma": {
        "scripts": SCRIPTS, "manifest": MANIFEST, "channel_id": CHANNEL_ID,
        "token": TOKEN_ENV, "work": os.path.join(ROOT, "work", "ch2_shorts"),
        "art": os.path.join(ROOT, "assets", "art", "ch2"),
        "art_style": "dharma",
        "music_dir": os.path.join(ROOT, "assets", "music"),
        "mood": "calm",
        "tags": ["ธรรมะก่อนนอน", "นอนไม่หลับ", "ปล่อยวาง", "ธรรมะ", "สมาธิ",
                 "คลายเครียด", "ฟังก่อนนอน", "Farmmer", "Shorts"],
        "category": "22",
        # Hooks carrying one of these words name something the viewer can do
        # tonight, which is the shape that measured 300-570 views/day against
        # 74-173 for the restating-the-problem shape (docs/HOOKS-MEASURED.md).
        # _winning_first() publishes these ahead of the others.
        "cues": ("ลอง", "คืนนี้", "เปิดทิ้งไว้"),
        # The funnel points at the *playlist*, not only the single 120-min file:
        # the playlist is durable (it survives a deleted video) and it autoplays
        # into the next long file, so one tap earns more watch-hours than one video.
        "tail": (f"\n\nฟังเวอร์ชันเต็ม 120 นาทีได้ที่นี่ → {LONG_URL}\n"
                 f"ฟังยาว ๆ ทั้งคืน (รวมทุกตอน) → "
                 f"https://www.youtube.com/playlist?list={LONG_PLAYLIST}\n\n"
                 "#ธรรมะก่อนนอน #นอนไม่หลับ #ปล่อยวาง"),
    },
    "genx": {
        "scripts": os.path.join(ROOT, "content", "ch1_shorts", "scripts.json"),
        "manifest": os.path.join(ROOT, "content", "ch1_shorts.json"),
        "channel_id": "UCI6EfsgM1HNjrYarvigxyrQ",
        "token": "YT_CH1_REFRESH_TOKEN",
        "work": os.path.join(ROOT, "work", "ch1_shorts"),
        "art": os.path.join(ROOT, "assets", "art", "ch1"),
        "art_style": "genx",
        "music_dir": os.path.join(ROOT, "assets", "music"),
        "mood": "hopeful",
        "tags": ["ปรัชญาชีวิต", "ข้อคิด", "แง่คิด", "กำลังใจ", "ชีวิต", "GenX",
                 "ตาต้าGenX", "Shorts"],
        "category": "22",
        # ch1's winning shape is permission, not an instruction -- see the same
        # table. These hooks measured 310-373 views/day.
        "cues": ("มีสิทธิ์", "ไม่ต้อง", "อนุญาต"),
        "tail": ("\n\nรวมข้อคิดปรัชญาชีวิตไว้ให้แล้ว → "
                 "https://www.youtube.com/playlist?list=PLXEV3B3DcgsU\n"
                 "ทุกตอนอยู่ในช่องเดียว → https://www.youtube.com/@tatagenxgeny\n\n"
                 "#ปรัชญาชีวิต #ข้อคิด #แง่คิด"),
    },
    "kongkeat": {
        "scripts": os.path.join(ROOT, "content", "ch4_shorts", "scripts.json"),
        "manifest": os.path.join(ROOT, "content", "ch4_shorts.json"),
        "channel_id": "UC7gCIu4G_7QCEJ8hJ-34zoQ",
        "token": "YT_CH4_REFRESH_TOKEN",
        "work": os.path.join(ROOT, "work", "ch4_shorts"),
        "art": os.path.join(ROOT, "assets", "art", "ch4"),
        "art_style": "family",
        "music_dir": os.path.join(ROOT, "assets", "music"),
        "mood": "warm",
        "tags": ["เรื่องเล่า", "อบอุ่นใจ", "ครอบครัว", "ความทรงจำ", "เรื่องเล่าอบอุ่นใจ",
                 "คิดถึงบ้าน", "พ่อแม่", "Shorts"],
        "category": "24",
        # The channel pivoted to family moments (docs/STORY-CHANNEL-PIVOT.md):
        # a specific relationship plus a physical act measured 460-1,083 views
        # against 1-6 for the classical-tale shape. Publish these first.
        "cues": ("พ่อ", "แม่", "พี่", "ยาย", "ตา", "ป้า", "น้า", "ลูก"),
        "tail": ("\n\nรวมเรื่องเล่าครอบครัวทุกตอน → "
                 "https://www.youtube.com/playlist?list=PLU4aztRNvt28\n\n"
                 "#เรื่องเล่า #ครอบครัว #อบอุ่นใจ"),
    },
}


def access_token(spec: dict) -> str:
    cid, sec = os.environ.get("YT_CLIENT_ID"), os.environ.get("YT_CLIENT_SECRET")
    rt = os.environ.get(spec["token"])
    if not (cid and sec and rt):
        sys.exit(f"Missing credentials: need YT_CLIENT_ID, YT_CLIENT_SECRET and {spec['token']}")
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
# How long a real ceiling refusal parks the rail before it probes again.
# Shorter than the daily reset, because the reset clock is unreliable.
PROBE_HOURS = 3

# A ceiling of our own, on top of YouTube's. Measured 2026-11-07: ch4 published 37
# Shorts in about two days (the workflow is triggered on every scripts.json push,
# so each pool grow fired the rail again) and 45 of its videos now sit at zero
# views while the 17 that got a slow drip reached up to 1,088. The push trigger is
# what let the flood through, so the cap lives here where no trigger can bypass it.
DAILY_CAP = 3

# Minimum hours between two uploads on one channel. The daily cap alone still let a
# run post its two or three back to back; the burst is what the zero-view clusters
# have in common (measured 2026-11-07), so the spacing is enforced separately.
MIN_GAP_HOURS = 2.0

# The upload ledger the cap counts. Kept separate from upload_limit.json, which
# records a ceiling refusal, not a normal upload.
UPLOAD_LOG = os.path.join(ROOT, "content", "upload_log.json")


def _load_upload_log() -> dict:
    d = load(UPLOAD_LOG, {})
    if not isinstance(d, dict) or "channels" not in d:
        return {"channels": {}}
    return d


def _prune(stamps: list[str]) -> list[str]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    out = []
    for ts in stamps:
        try:
            if datetime.fromisoformat(str(ts).replace("Z", "+00:00")) > cutoff:
                out.append(ts)
        except ValueError:
            continue
    return out


def _seed_ledger(channel_id: str, manifest_path: str) -> None:
    """One-time seed of the ledger from the manifest's own commit history.

    Only runs when the ledger has no entry for the channel, so a fresh ledger
    (first run after this code lands) starts from the real recent uploads rather
    than zero -- which would otherwise let a full day's worth through at once.
    """
    log = _load_upload_log()
    if log["channels"].get(channel_id):
        return
    rel = os.path.relpath(manifest_path, ROOT)
    try:
        out = subprocess.run(["git", "-C", ROOT, "log", "--since=24 hours ago",
                              "--format=%cI", "--", rel],
                             capture_output=True, text=True, timeout=30).stdout
    except (OSError, subprocess.SubprocessError):
        return
    stamps = _prune([ln.strip() for ln in out.splitlines() if ln.strip()])
    if not stamps:
        return
    log["channels"][channel_id] = stamps
    _write_upload_log(log)


def _write_upload_log(log: dict) -> None:
    with open(UPLOAD_LOG, "w", encoding="utf-8") as fh:
        json.dump(log, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def uploads_in_last_24h(channel_id: str, manifest_path: str) -> int:
    """Uploads in the last 24 hours, from the committed ledger.

    The ledger, not the manifest's git history, is the source of truth: CI checks
    out a single commit (fetch-depth 1), so counting commits saw one upload and the
    cap silently never tripped -- measured 2026-11-07, when the first capped run
    still published four Shorts. The script writes and commits the ledger itself,
    so it survives that shallow checkout.
    """
    _seed_ledger(channel_id, manifest_path)
    return len(_prune(_load_upload_log()["channels"].get(channel_id, [])))


def hours_since_last_upload(channel_id: str, manifest_path: str) -> float | None:
    """Hours since the most recent upload, or None if there is no record yet."""
    _seed_ledger(channel_id, manifest_path)
    stamps = _prune(_load_upload_log()["channels"].get(channel_id, []))
    if not stamps:
        return None
    newest = max(datetime.fromisoformat(str(s).replace("Z", "+00:00")) for s in stamps)
    return (datetime.now(timezone.utc) - newest).total_seconds() / 3600


def note_upload(channel_id: str) -> None:
    """Record one upload in the ledger so the cap counts it on the next run."""
    log = _load_upload_log()
    keep = _prune(log["channels"].get(channel_id, []))
    keep.append(datetime.now(timezone.utc).isoformat(timespec="seconds"))
    log["channels"][channel_id] = keep
    _write_upload_log(log)


def note_upload_limit(channel_id: str, detail: str = "") -> None:
    """Park the rail for a short probe window after a real ceiling refusal.

    Keyed by channel: one channel hitting its ceiling must not make the other
    look blocked. Without this note the foreman re-dispatches the rail every tick,
    and every tick burns a run to learn the same thing.

    The window is short on purpose. The ceiling's reset is not a clock we can
    trust: measured 2026-11-04, ch2 was recorded as capped at 09:38 UTC, yet it
    accepted an upload at 04:28 the next morning, and a note set to the next
    midnight Pacific sat on 39 ready Shorts for ~19 h. So the note is a probe,
    not a sentence -- it parks the rail for PROBE_HOURS and the next run tries
    again, re-recording only if the channel really is still capped.
    """
    now = datetime.now(timezone.utc)
    midnight = now.replace(hour=8, minute=0, second=0, microsecond=0)
    if midnight <= now:
        midnight = midnight + timedelta(days=1)
    reset = min(midnight, now + timedelta(hours=PROBE_HOURS))
    limits = load(LIMIT_FILE, {})
    if not isinstance(limits, dict) or "channels" not in limits:
        limits = {"channels": {}}
    rec = {"hit_at": now.isoformat(timespec="seconds"),
           "reset_at": reset.isoformat(timespec="seconds"),
           "probe_hours": PROBE_HOURS}
    if detail:
        rec["detail"] = detail[:200]
    limits["channels"][channel_id] = rec
    with open(LIMIT_FILE, "w", encoding="utf-8") as fh:
        json.dump(limits, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    print(f"  recorded upload limit; resets {limits['channels'][channel_id]['reset_at']}")
    commit(LIMIT_FILE, f"publish: record the daily upload limit for {channel_id}")


def _union_resolve_upload_log() -> bool:
    """Union-resolve conflict markers a stash pop left in the ledger.

    The ledger is append-only, so both sides of a conflict are real uploads and
    the merge that keeps both is the correct one. Measured 2026-11-09: a
    `pull --rebase --autostash` in remake-shorts left markers here, the next
    `git add` committed them (612f185), and every foreman run then crashed on the
    unparsable JSON. Returns True when it rewrote the file.
    """
    if not os.path.exists(UPLOAD_LOG):
        return False
    raw = open(UPLOAD_LOG, encoding="utf-8").read()
    if "<<<<<<< " not in raw:
        return False

    def fix(m):
        sides = [ln.strip().rstrip(",") for ln in
                 (m.group(1) + "\n" + m.group(2)).splitlines() if ln.strip()]
        seen, out = set(), []
        for ln in sides:
            if ln not in seen:
                seen.add(ln)
                out.append(ln)
        return ",\n".join(out)

    fixed = re.sub(r"<<<<<<< [^\n]*\n(.*?)=======\n(.*?)>>>>>>> [^\n]*\n",
                   fix, raw, flags=re.S)
    try:
        json.loads(fixed)
    except ValueError:
        return False
    with open(UPLOAD_LOG, "w", encoding="utf-8") as fh:
        fh.write(fixed)
    return True


def commit(path: str, message: str) -> None:
    """Persist the manifest to git the moment an id is known.

    The CI runner is ephemeral: if the run dies before the workflow's commit step
    (a cancel, an upload-limit abort), an id that lives only on the runner is
    lost, and the next run re-uploads the same Short. Committing here makes the
    record survive the run it was made in.
    """
    if not os.environ.get("GITHUB_ACTIONS"):
        return
    gitc = ["git", "-c", "user.name=openhands", "-c", "user.email=openhands@all-hands.dev"]
    try:
        subprocess.run(["git", "add", os.path.relpath(path, ROOT)], cwd=ROOT, check=True)
        subprocess.run(gitc + ["commit", "-q", "-m", message], cwd=ROOT, check=True)
        # Union-merge the append-only ledgers, so a racing job's records are kept
        # instead of leaving conflict markers that lose a live upload id.
        subprocess.run(["git", "config", "merge.unionjson.driver",
                        "python3 scripts/git_union_merge.py %O %A %B"],
                       cwd=ROOT, capture_output=True)
        # Two channel jobs run at once and both commit; without the rebase the
        # second push is rejected and its id is lost (seen 2026-11-03). A plain
        # rebase, not --autostash: a dirty tree must fail loudly rather than let a
        # stash pop leave conflict markers in the ledger (612f185, 2026-11-09).
        subprocess.run(gitc + ["pull", "--rebase", "origin", "main"],
                       cwd=ROOT, check=True, capture_output=True, timeout=120)
        if _union_resolve_upload_log():
            print("  resolved a conflict in the upload ledger (kept both sides)")
            subprocess.run(["git", "add", os.path.relpath(UPLOAD_LOG, ROOT)], cwd=ROOT)
            subprocess.run(gitc + ["commit", "-q", "-m", message], cwd=ROOT)
            subprocess.run(gitc + ["pull", "--rebase", "origin", "main"],
                           cwd=ROOT, capture_output=True, timeout=120)
        subprocess.run(["git", "push"], cwd=ROOT, check=True,
                       capture_output=True, timeout=120)
        print("  manifest committed")
    except subprocess.CalledProcessError as exc:
        print(f"  manifest commit failed (will retry at the workflow step): {exc}",
              file=sys.stderr)


def winning_first(todo: list, cues) -> list:
    """Put the hooks that measured best at the front of the publish queue.

    The pool is ordered by id, so a plain drip spends its first weeks on
    whichever shape happened to be generated first. The winning shape is known
    (docs/HOOKS-MEASURED.md), so order by it: a stable sort keeps the id order
    inside each group. A channel with no cues keeps the old behaviour.
    """
    if not cues:
        return todo
    return sorted(todo, key=lambda s: 0 if any(c in s["hook"] for c in cues) else 1)


def pick_bed(music_dir: str | None, sid: str, mood: str | None = None,
             ledger_path: str | None = None) -> str | None:
    """Choose a bed for a short, preferring one that matches the channel's mood.

    The owner's rule (2026-11-09) is that no two clips share a bed. The old form
    gave every Short of a channel the same mood-matched file (ch4's warm bed ran
    under all of them), which is exactly what was forbidden. So the mood still
    guides the *first* choice, but the ledger is what guarantees no repeat: a bed
    already used by another id is skipped, and only when a channel's mood-matched
    beds run out does it fall through to another mood. The same short keeps the
    same bed across rebuilds because its id is already in the ledger.
    """
    if not music_dir or not os.path.isdir(music_dir):
        return None
    prov = os.path.join(music_dir, "provenance.json")
    mood_of = {}
    if os.path.exists(prov):
        try:
            with open(prov, encoding="utf-8") as fh:
                mood_of = {b["file"]: b.get("mood") for b in json.load(fh).get("beds", [])}
        except (OSError, ValueError):
            mood_of = {}
    # Only beds that passed the music test are in the library: a stray file that
    # never made provenance must not be handed to a clip (it may not even decode).
    pool = sorted(f for f in os.listdir(music_dir)
                  if f.lower().endswith((".mp3", ".wav", ".m4a")) and f in mood_of)
    if not pool:
        pool = sorted(f for f in os.listdir(music_dir)
                      if f.lower().endswith((".mp3", ".wav", ".m4a")))
    if not pool:
        return None
    if mood:
        pool.sort(key=lambda f: 0 if mood_of.get(f) == mood else 1)
    used = {}
    if ledger_path and os.path.exists(ledger_path):
        try:
            with open(ledger_path, encoding="utf-8") as fh:
                used = json.load(fh).get("beds", {})
        except (OSError, ValueError):
            used = {}
    free = [f for f in pool if used.get(f, sid) == sid] or pool
    pick = free[0]
    if ledger_path:
        used[pick] = sid
        tmp = ledger_path + ".part"
        os.makedirs(os.path.dirname(os.path.abspath(ledger_path)), exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"beds": used}, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, ledger_path)
    return os.path.join(music_dir, pick)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", default="dharma", choices=list(CHANNELS))
    ap.add_argument("--dry-run", action="store_true")
    # Default to a small drip, never "all". Measured 2026-11-05: a pool-grow commit
    # triggered this on push with per_run=0 and uploaded 89 Shorts in one day; that
    # day's median views collapsed to 1 (vs 206-1007 on drip days), because the
    # Shorts feed throttles a channel that floods. A missing cap is how that happens,
    # so the safe number is the default and "all" must be asked for explicitly.
    ap.add_argument("--per-run", type=int, default=1,
                    help="upload at most N per run (0 = all due; default 1)")
    ap.add_argument("--privacy", default="public", choices=["private", "unlisted", "public"])
    ap.add_argument("--work", help="override the build dir (default: per channel)")
    args = ap.parse_args()

    spec = CHANNELS[args.channel]
    work = args.work or spec["work"]
    scripts = load(spec["scripts"], [])
    man = load(spec["manifest"], {"channel_slug": args.channel, "channel_id": spec["channel_id"],
                                  "shorts": {}})
    if not scripts:
        sys.exit(f"no scripts at {spec['scripts']}")

    # If a previous run already hit the channel's daily upload ceiling, do not
    # build anything -- the upload cannot succeed until the reset, and a build
    # here costs minutes for nothing.
    lim = load(LIMIT_FILE, {})
    rec = (lim.get("channels", {}) if isinstance(lim, dict) else {}).get(spec["channel_id"], {})
    if (rec.get("reset_at")
            and datetime.fromisoformat(rec["reset_at"].replace("Z", "+00:00")) > datetime.now(timezone.utc)):
        print(f"channel upload limit recorded; resets {rec['reset_at']} -- nothing to do")
        return 0

    todo = [s for s in scripts if not man["shorts"].get(s["id"], {}).get("video_id")]
    todo = winning_first(todo, spec.get("cues"))
    # Hold the channel to a slow drip regardless of how often this was triggered.
    already = uploads_in_last_24h(args.channel, spec["manifest"])
    room = max(DAILY_CAP - already, 0)
    if room == 0:
        print(f"daily cap reached ({already}/{DAILY_CAP} in the last 24h) -- "
              "waiting, a steady drip beats a flood")
        return 0
    since = hours_since_last_upload(args.channel, spec["manifest"])
    if since is not None and since < MIN_GAP_HOURS:
        print(f"only {since:.1f}h since the last upload (need {MIN_GAP_HOURS}h) -- "
              "spacing the posts out, that is what keeps the feed showing them")
        return 0
    if args.per_run:
        todo = todo[:min(args.per_run, room)]
    done = [s["id"] for s in scripts if man["shorts"].get(s["id"], {}).get("video_id")]
    print(f"{len(todo)} to publish, {len(done)} already live, "
          f"{already}/{DAILY_CAP} published in the last 24h")

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

    creds = Credentials(token=access_token(spec), refresh_token=os.environ[spec["token"]],
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

    rc = 0
    for s in todo:
        sid = s["id"]
        # Build if needed (CI has no prebuilt file).
        out = os.path.join(work, sid, f"short_{sid}.mp4")
        if not os.path.exists(out):
            print(f"building {sid} ...")
            cmd = [sys.executable, os.path.join(HERE, "make_short.py"),
                   "--scripts", spec["scripts"], "--index", sid,
                   "--out-dir", work]
            if spec.get("art_style"):
                # One generated image per clip -- no two Shorts share a picture.
                cmd += ["--art-style", spec["art_style"],
                        "--art-dir", spec.get("art", ""),
                        "--art-ledger", art_ledger_path(args.channel)]
            elif spec.get("art") and os.path.isdir(spec["art"]):
                cmd += ["--art-dir", spec["art"]]
            bed = pick_bed(spec.get("music_dir"), sid, spec.get("mood"),
                           bed_ledger_path(args.channel))
            if bed:
                cmd += ["--music", bed]
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
                       (MUSIC_CREDIT if spec.get("music_dir") else ""))
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
            # Two shapes mean the same thing: a per-channel ceiling
            # ("uploadLimitExceeded") and the project-wide daily cap ("Quota exceeded
            # for quota metric 'Video Uploads' ... per day", measured 2026-11-05).
            # Both are an expected end to the day, not a fault: stop without marking
            # the run failed, or every day looks broken and real failures hide.
            if "uploadLimitExceeded" in text or "Video Uploads per day" in text:
                print("  daily upload limit reached; stopping this run", file=sys.stderr)
                note_upload_limit(spec["channel_id"], text)
                break
            rc = 1
            continue
        vid = response["id"]
        man["shorts"][sid] = {"video_id": vid, "url": f"https://youtu.be/{vid}",
                              "title": body["snippet"]["title"]}
        save(man, spec["manifest"])   # record before anything else can fail
        note_upload(args.channel)     # the cap counts this on the next run
        commit(spec["manifest"], f"publish({args.channel}): record Short {sid}")
        commit(UPLOAD_LOG, f"publish({args.channel}): count Short {sid} toward the daily cap")
        print(f"  live: https://youtu.be/{vid}")

    print(f"\n{len([v for v in man['shorts'].values() if v.get('video_id')])}"
          f"/{len(scripts)} shorts live")
    return rc


if __name__ == "__main__":
    sys.exit(main())
