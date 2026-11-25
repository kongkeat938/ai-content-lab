#!/usr/bin/env python3
"""Cut a vertical Short out of a finished long-form clip, pointing at the long video.

K (2026-11-21): "เอาคลิปยาวไปตัดเป็น short ... ดึงคนเข้าช่องมาดูคลิปยาว อย่าลืมแปะลิงค์"

    python3 scripts/shorts_from_long.py --video clip.mp4 --start 2 --dur 46 \
        --title "ปล่อยวางก่อนหลับ" --cta "ฟังเต็ม 11 นาที · ลิงก์ในคำอธิบาย" \
        --out work/shorts/x.mp4 --thumb work/shorts/x.jpg

The 16:9 frame keeps its whole width and floats on a blurred copy of itself, so a
cut never crops the picture. Thai text is burned in; a Short cannot carry a
clickable link, so the long URL belongs in the description and the burn only
points at it. The build is gated by `short_standard.verify_short` -- a Short that
misses the standard exits 1 instead of being handed to the uploader.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

FONT = os.path.join(ROOT, "assets", "fonts", "Kanit-Bold.ttf")
W, H = 1080, 1920
FG_W, FG_H = 1080, 608
FG_Y = 700
# -4.4, not -3.4: the AAC encode overshoots the float-domain true peak, and one
# clip in five landed at -2.4 dBFS against the -3.0 gate (measured 2026-11-25).
TARGET_I, TARGET_TP = -14.0, -4.4


def run(cmd: list) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, stdin=subprocess.DEVNULL)


def loudness(path: str) -> tuple[float | None, float | None]:
    r = run(["ffmpeg", "-hide_banner", "-nostats", "-i", path,
             "-af", "ebur128=peak=true", "-f", "null", "-"])
    i = tp = None
    for line in r.stderr.splitlines():
        line = line.strip()
        m = re.match(r"I:\s+(-?\d+\.?\d*) LUFS", line)
        if m and i is None:
            i = float(m.group(1))
        m = re.match(r"Peak:\s+(-?\d+\.?\d*) dBFS", line)
        if m:
            tp = float(m.group(1))
    return i, tp


def _measured(video: str, start: float, dur: float) -> dict:
    """Pass 1 of a two-pass loudnorm: the segment's own I/TP/LRA/thresh."""
    r = run(["ffmpeg", "-hide_banner", "-nostats", "-ss", str(start), "-t", str(dur),
             "-i", video, "-vn", "-af",
             f"loudnorm=I={TARGET_I}:TP={TARGET_TP}:LRA=11:print_format=json",
             "-f", "null", "-"])
    blob = r.stderr[r.stderr.rfind("{"):r.stderr.rfind("}") + 1]
    return json.loads(blob)


def _ass(out_video: str, title: str, cta: str) -> str:
    """Burn the Thai text through libass (this ffmpeg build has no drawtext)."""
    path = os.path.splitext(out_video)[0] + ".ass"
    head = ("[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\n\n"
            "[V4+ Styles]\nFormat: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,"
            "OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,"
            "Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding\n"
            "Style: Title,Kanit,62,&H00FFFFFF,&H00FFFFFF,&H80000000,&H00000000,-1,0,0,0,"
            "100,100,0,0,1,4,0,5,40,40,0,1\n"
            "Style: Cta,Kanit,46,&H008BD9F6,&H00FFFFFF,&H80000000,&H00000000,-1,0,0,0,"
            "100,100,0,0,1,4,0,5,40,40,0,1\n\n[Events]\n"
            "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n")
    lines = [
        f"Dialogue: 0,0:00:00.00,9:59:59.00,Title,,0,0,0,,{{\\pos(540,450)}}{title}",
        f"Dialogue: 0,0:00:00.00,9:59:59.00,Cta,,0,0,0,,{{\\pos(540,1415)}}{cta}",
        "Dialogue: 0,0:00:00.00,9:59:59.00,Cta,,0,0,0,,{\\pos(540,1500)}กดติดตามช่อง",
    ]
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(head + "\n".join(lines) + "\n")
    return path


def build(video: str, start: float, dur: float, title: str, cta: str, out: str) -> None:
    ass_path = _ass(out, title, cta)
    m = _measured(video, start, dur)
    loud = (f"loudnorm=I={TARGET_I}:TP={TARGET_TP}:LRA=11"
            f":measured_I={m['input_i']}:measured_TP={m['input_tp']}"
            f":measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}"
            f":offset={m['target_offset']}:linear=true,aresample=48000,"
            # loudnorm cannot hold TP in linear mode, and this segment already
            # peaks at -3.3 dBFS before any gain (measured 2026-11-25). level=0
            # is required: the default auto-level raises the peak to 0 dBFS.
            f"alimiter=limit=0.50:level=0")
    fc = (
        f"[0:v]trim=start=0:duration={dur},setpts=PTS-STARTPTS,fps=25,"
        f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
        f"gblur=sigma=26,eq=brightness=-0.10[bgsrc];"
        f"[0:v]trim=start=0:duration={dur},setpts=PTS-STARTPTS,fps=25,"
        f"scale={FG_W}:{FG_H}[fg];"
        f"[bgsrc][fg]overlay=0:{FG_Y}[base];"
        f"[base]ass={ass_path}:fontsdir={os.path.join(ROOT, 'assets', 'fonts')}[v]"
    )
    # Seek on the input, not in the filter graph: trimming at t=start made ffmpeg
    # decode every frame from 0, so a cut at minute 22 of a 26-min talk cost 62 s
    # against 30 s at minute 2 (measured 2026-11-25).
    cmd = ["ffmpeg", "-y", "-v", "error", "-ss", str(start), "-i", video,
           "-filter_complex", fc, "-map", "[v]", "-map", "0:a:0",
           "-af", loud,
           "-t", str(dur), "-c:v", "libx264", "-preset", "medium", "-crf", "18",
           "-pix_fmt", "yuv420p", "-color_range", "tv", "-colorspace", "bt709",
           "-color_primaries", "bt709", "-color_trc", "bt709", "-r", "25",
           "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", out]
    r = run(cmd)
    if r.returncode != 0:
        sys.exit(f"ffmpeg failed:\n{r.stderr[-1200:]}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", default="")
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--dur", type=float, default=46.0)
    ap.add_argument("--title", required=True)
    ap.add_argument("--cta", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--thumb", required=True)
    ap.add_argument("--upload", action="store_true",
                    help="upload the gated Short public, with the long link in the description")
    ap.add_argument("--channel", default="", choices=["", "genx", "dharma"])
    ap.add_argument("--long-url", default="", help="public URL of the long video this Short points at")
    ap.add_argument("--ledger-key", default="")
    ap.add_argument("--reuse", action="store_true",
                    help="gate + upload an existing build instead of cutting it again")
    args = ap.parse_args()

    if args.reuse:
        missing = [p for p in (args.out, args.thumb) if not os.path.exists(p)]
        if missing:
            sys.exit(f"--reuse needs an existing build: missing {missing}")
    else:
        if not args.video:
            sys.exit("--video is needed unless --reuse")
        if not os.path.exists(args.video):
            # BLIND, not a crash: a missing input must say so, not raise a JSON
            # error from the empty loudnorm output (measured 2026-11-25).
            print(f"BLIND: no such input file: {args.video}", file=sys.stderr)
            sys.exit(2)
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        build(args.video, args.start, args.dur, args.title, args.cta, args.out)
        i, tp = loudness(args.out)
        if i is not None:
            print(f"  loudness: {i} LUFS" + (f", TP {tp} dBTP" if tp is not None else ""))
        r = run([sys.executable, os.path.join(HERE, "make_short_thumbnail.py"),
                 "--video", args.out, "--hook", args.title, "--out", args.thumb])
        if r.returncode != 0:
            print(r.stderr[-600:], file=sys.stderr)
    import short_standard
    ok, reasons, metrics = short_standard.verify_short(args.out, args.thumb,
                                                       profile="client")
    print(json.dumps({"verdict": "pass" if ok else "fail", "reasons": reasons,
                      "metrics": metrics}, ensure_ascii=False, indent=1))
    if not ok:
        return 1
    if args.upload:
        return upload(args, metrics)
    return 0


CH = {
    "genx": ("YT_CH1_REFRESH_TOKEN", "UCI6EfsgM1HNjrYarvigxyrQ", "content/ch1_shorts.json",
             "ฝากกดติดตามช่อง ตาต้า GenX — ปรัชญาชีวิต เพื่อรับข้อคิดใหม่ ๆ ทุกวัน",
             "#Shorts #ปรัชญาชีวิต #ข้อคิดชีวิต"),
    "dharma": ("YT_CH2_REFRESH_TOKEN", "UCM3QO5L_pmj34n1JVlbhh-w", "content/ch2_shorts.json",
               "ฝากกดติดตามช่อง Farmmer — ธรรมะก่อนนอน เพื่อรับธรรมะกล่อมใจทุกคืน",
               "#Shorts #ธรรมะก่อนนอน #ปล่อยวาง"),
}


DAILY_CAP = 3          # same ceiling as publish_shorts.py -- one place owns the number
MIN_GAP_HOURS = 2.0    # the burst, not the count, is what leaves videos at zero views


def cap_block(channel_id: str, log: dict, now=None) -> str | None:
    """None = the channel may upload now; a string = why it must wait.

    The log is injected so a test can prove a refusal without touching the real ledger.
    """
    from datetime import datetime, timedelta, timezone

    now = now or datetime.now(timezone.utc)
    stamps = []
    for ts in (log.get("channels", {}) or {}).get(channel_id, []):
        try:
            t = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        except ValueError:
            continue
        if now - t <= timedelta(hours=24):
            stamps.append(t)
    if len(stamps) >= DAILY_CAP:
        return f"daily cap {DAILY_CAP} reached ({len(stamps)} uploads in 24 h)"
    if stamps:
        gap = (now - max(stamps)).total_seconds() / 3600
        if gap < MIN_GAP_HOURS:
            return f"only {gap:.2f} h since the last upload (min {MIN_GAP_HOURS} h)"
    return None


def upload(args, metrics: dict) -> int:
    import json as _json
    from datetime import datetime, timezone

    from analytics import access_token
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    env, channel_id, ledger_path, blurb, hashtags = CH[args.channel]
    if not args.long_url:
        sys.exit("--upload needs --long-url (a private video cannot be linked to)")
    log_path = os.path.join(ROOT, "content", "upload_log.json")
    log = _json.load(open(log_path, encoding="utf-8"))
    hold = cap_block(channel_id, log)
    if hold:
        print(f"  HOLD: {hold} -- not uploading (gate the queue, do not flood)")
        return 0
    yt = build("youtube", "v3", credentials=Credentials(access_token(env)),
               cache_discovery=False)
    title = f"{args.title} #Shorts"[:100]
    description = (f"{args.cta}\n\nฟังเต็ม ๆ ได้ที่นี่ → {args.long_url}\n\n"
                   f"{blurb}\n\n{hashtags}")
    body = {"snippet": {"title": title, "description": description,
                        "tags": ["ปรัชญาชีวิต", "ข้อคิดชีวิต", "ปล่อยวาง", "ธรรมะก่อนนอน",
                                 "ฟังก่อนนอน", "Shorts"],
                        "categoryId": "22"},
            "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False,
                       "license": "youtube", "embeddable": True}}
    media = MediaFileUpload(args.out, mimetype="video/mp4", chunksize=-1, resumable=True)
    resp = yt.videos().insert(part="snippet,status", body=body, media_body=media).execute()
    vid = resp["id"]
    yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(args.thumb)).execute()
    print(f"  uploaded https://youtu.be/{vid} (public, thumbnail set)")

    led = _json.load(open(ledger_path, encoding="utf-8"))
    key = args.ledger_key or os.path.splitext(os.path.basename(args.out))[0]
    led["shorts"][key] = {"video_id": vid, "url": f"https://youtu.be/{vid}", "title": title,
                          "posted_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                          "source": args.video, "start": args.start,
                          "long_url": args.long_url, "gate": metrics}
    _json.dump(led, open(ledger_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    log.setdefault("channels", {}).setdefault(channel_id, []).append(
        datetime.now(timezone.utc).isoformat())
    _json.dump(log, open(log_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
