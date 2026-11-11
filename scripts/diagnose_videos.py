#!/usr/bin/env python3
"""Diagnose every Short on a channel and decide what to do about the weak ones.

This exists because the earlier review only looked at the top five videos by
views, so the videos that were actually struggling were never examined -- and the
one conclusion drawn from them ("45 videos have zero views, quality is the
problem") was wrong. Measured 2026-11-07: YouTube Analytics under-reports fresh
Shorts, and the Data API showed those "zero-view" videos had 154, 107 and 75
views. So the diagnosis must use the authoritative view count and the upload
time together, and it must separate "too new to have been distributed" from
"old and still unseen", because only the second is a real failure.

It decides, it does not ask:

  * performing      -- at or above the channel's own working level; leave alone.
  * too-new         -- under the distribution window; the right action is to wait.
  * under-distributed -- past the window with weak reach; worth a metadata retry.
  * dead            -- past the window with no views; the honest fix is to stop
                       spending on it, not to keep re-posting it.

The panel then turns the real numbers into concrete per-video advice and a short
list of rules the generator can apply. Output: content/diagnosis/<channel>.json
and docs/DIAGNOSIS-<channel>.md.

    python3 scripts/diagnose_videos.py --channel ch4
    python3 scripts/diagnose_videos.py --channel ch4 --panel
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = "https://www.googleapis.com/youtube/v3"

sys.path.insert(0, HERE)
import video_review as vr  # noqa: E402

# A Short needs roughly this long before the feed decides whether to show it. Under
# it, a low count is age, not failure.
DISTRIBUTION_HOURS = 48
# At or above this many views the video is doing the channel's ordinary work.
WORKING_VIEWS = 50
# More than this many uploads inside one ten-minute window is a burst. Measured
# 2026-11-07: ch2 published 25 Shorts in the 13:3x window on 2026-11-05 and 20 of
# them sat at zero views, while the ones published one or two at a time reached
# hundreds. The burst, not the script, is what the numbers point at.
BURST_WINDOW_MIN = 10
BURST_MIN = 5


def stats_for(tok: str, ids: list[str]) -> dict[str, dict]:
    """Authoritative statistics/privacy/duration/snippet, 50 ids per call."""
    out: dict[str, dict] = {}
    for i in range(0, len(ids), 50):
        chunk = ids[i:i + 50]
        url = (f"{DATA}/videos?part=statistics,status,contentDetails,snippet&id="
               + ",".join(chunk))
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {tok}"})
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=40) as fh:
                    d = json.load(fh)
                out.update({it["id"]: it for it in d.get("items", [])})
                break
            except urllib.error.HTTPError as exc:
                if exc.code in (403, 429) and attempt < 2:
                    import time
                    time.sleep(15)
                    continue
                print(f"  stats chunk {i}: HTTP {exc.code}", file=sys.stderr)
                break
    return out


def upload_times(manifest_rel: str) -> dict[str, str]:
    """Short id -> ISO upload time, from the manifest's own commit history.

    Locally and in CI the checkout is shallow, so this can be empty; callers treat
    a missing time as unknown rather than guessing.
    """
    try:
        out = subprocess.run(["git", "-C", ROOT, "log", "--format=%cI|%s", "--", manifest_rel],
                             capture_output=True, text=True, timeout=30).stdout
    except (OSError, subprocess.SubprocessError):
        return {}
    times: dict[str, str] = {}
    for line in out.splitlines():
        if "|" not in line:
            continue
        when, msg = line.split("|", 1)
        m = re.search(r"record Short (\S+)", msg)
        if m:
            times.setdefault(m.group(1), when)
    return times


def classify(views: int, age_h: float | None) -> str:
    if views >= WORKING_VIEWS:
        return "performing"
    if age_h is None or age_h < DISTRIBUTION_HOURS:
        return "too-new"
    if views == 0:
        return "dead"
    return "under-distributed"


def diagnose(channel: str, use_panel: bool) -> dict:
    token_env, _scripts, manifest_rel = vr.CHANNELS[channel]
    tok = vr.access_token(token_env)
    man = json.load(open(os.path.join(ROOT, manifest_rel), encoding="utf-8"))["shorts"]
    ids = [rec["video_id"] for rec in man.values() if rec.get("video_id")]
    if not ids:
        raise SystemExit(f"{channel}: no published videos in {manifest_rel}")
    stats = stats_for(tok, ids)
    times = upload_times(manifest_rel)
    now = dt.datetime.now(dt.timezone.utc)

    rows = []
    for sid, rec in man.items():
        vid = rec.get("video_id")
        st = stats.get(vid)
        if not st:
            continue
        views = int(st["statistics"].get("viewCount", 0))
        # Prefer YouTube's own publishedAt: it is exact and present in CI, where a
        # shallow checkout leaves the manifest history empty.
        when = st.get("snippet", {}).get("publishedAt") or times.get(sid)
        age_h = None
        if when:
            try:
                age_h = (now - dt.datetime.fromisoformat(when.replace("Z", "+00:00"))).total_seconds() / 3600
            except ValueError:
                age_h = None
        rows.append({
            "short": sid, "video": vid, "title": rec.get("title", "")[:80],
            "views": views, "privacy": st["status"]["privacyStatus"],
            "duration": st["contentDetails"]["duration"],
            "uploaded": when or "", "age_hours": round(age_h, 1) if age_h is not None else None,
            "state": classify(views, age_h),
        })
    rows.sort(key=lambda r: (r["state"] != "dead", r["state"] != "under-distributed", r["views"]))

    # Mark the upload bursts: a burst is the one condition that measurably tracks a
    # zero-view cluster, so each video needs to carry it into the report.
    bursts = detect_bursts([r for r in rows if r["uploaded"]])
    for r in rows:
        r["burst"] = bursts.get(r["video"], 0)

    counts: dict[str, int] = {}
    for r in rows:
        counts[r["state"]] = counts.get(r["state"], 0) + 1

    diagnosis = {
        "channel": channel, "generated": now.isoformat(timespec="seconds"),
        "distribution_hours": DISTRIBUTION_HOURS, "working_views": WORKING_VIEWS,
        "burst_window_min": BURST_WINDOW_MIN, "burst_min": BURST_MIN,
        "counts": counts, "videos": rows,
    }
    if use_panel:
        diagnosis["panel"] = ask_panel(channel, rows, counts)
    return diagnosis


def detect_bursts(rows: list[dict]) -> dict[str, int]:
    """video id -> how many videos share its ten-minute upload window.

    Only windows at or above BURST_MIN are returned, so a zero means "published on
    its own". The window is aligned to the clock (13:30-13:39), not to the first
    upload in it, so the same burst is one bucket no matter which run sees it.
    """
    buckets: dict[str, list[str]] = {}
    for r in rows:
        try:
            when = dt.datetime.fromisoformat(r["uploaded"].replace("Z", "+00:00"))
        except ValueError:
            continue
        key = when.strftime("%Y-%m-%dT%H:") + f"{when.minute // BURST_WINDOW_MIN * BURST_WINDOW_MIN:02d}"
        buckets.setdefault(key, []).append(r["video"])
    out: dict[str, int] = {}
    for key, vids in buckets.items():
        if len(vids) >= BURST_MIN:
            for vid in vids:
                out[vid] = len(vids)
    return out


def ask_panel(channel: str, rows: list[dict], counts: dict) -> dict:
    """One question, grounded in the measured table: what do we do about each group."""
    try:
        import advise
    except ImportError:
        return {}
    weak = [r for r in rows if r["state"] in ("dead", "under-distributed")][:12]
    if not weak:
        return {}
    table = "\n".join(
        f"- {r['short']} | {r['views']} views | {r['age_hours']}h old | burst={r.get('burst') or 0} | {r['title']}"
        for r in weak)
    burst_n = sum(1 for r in rows if r.get("burst"))
    q = (
        f"ช่อง {channel}: สรุปสถานะคลิป = {counts}\n"
        f"พบว่า {burst_n} คลิปถูกอัปโหลดเป็น 'คลื่น' (≥5 คลิปใน 10 นาที) และคลิปในคลื่น\n"
        "ส่วนใหญ่ได้ 0 วิว ขณะที่คลิปที่ปล่อยทีละ 1-2 ได้ 100-1,000 วิว\n"
        "คลิปที่ยังไม่ perform (เลย 48 ชม.):\n" + table + "\n\n"
        "คุณคือผู้จัดการช่อง YouTube. ตอบสั้น ๆ เป็นข้อ:\n"
        "1) สาเหตุที่เป็นไปได้ที่สุดที่คลิปกลุ่มนี้ไม่ถูกแจกจ่าย (อ้างจากตัวเลข burst)\n"
        "2) สิ่งที่ต้องทำกับ 'แต่ละกลุ่ม' (ปล่อยไว้/รอ/แก้ชื่อ-ปก-คำอธิบาย/หยุดทำต่อ) — ห้ามแนะนำให้ลบ\n"
        "3) RULES: กฎ 3 ข้อสำหรับสคริปต์ใหม่ (สั้น กระชับ ใช้ได้จริง)\n"
    )
    # Only the fast, free advisors, each under a hard cap: a diagnosis that blocks a
    # CI run for 20 minutes waiting on a slow poll is worse than no diagnosis. The
    # numbers carry the finding; the panel only phrases it.
    out: dict[str, str] = {}
    for name in advise.LIGHT:
        res = _with_timeout(advise.advisor(name), (q,), 90)
        if res is None:
            out[name] = "(timed out)"
            continue
        out[name] = str(res).strip()
    return out


def _with_timeout(fn, args, seconds: int):
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(fn, *args)
        try:
            return fut.result(timeout=seconds)
        except Exception:  # noqa: BLE001
            return None


def report_md(d: dict) -> str:
    burst_n = sum(1 for r in d["videos"] if r.get("burst"))
    lines = [f"# วินิจฉัยคลิป — {d['channel']}", f"", f"สร้างเมื่อ {d['generated']}",
             f"", f"**สรุปสถานะ:** " + ", ".join(f"{k} {v}" for k, v in d["counts"].items()),
             f"**คลิปที่อยู่ในคลื่นถล่ม (อัป ≥{d.get('burst_min', 5)} คลิปใน "
             f"{d.get('burst_window_min', 10)} นาที):** {burst_n}",
             f"", "| Short | วิว | อายุ(ชม.) | สถานะ | คลื่น | ชื่อ |", "|---|---|---|---|---|---|"]
    for r in d["videos"]:
        lines.append(f"| {r['short']} | {r['views']} | {r['age_hours']} | {r['state']} | "
                     f"{r.get('burst') or '-'} | {r['title'][:34]} |")
    for name, text in d.get("panel", {}).items():
        lines += ["", f"## ความเห็นจาก {name}", "", text]
    rules = parse_rules(d.get("panel", {}))
    if rules:
        lines += ["", "## RULES ที่ดึงออกมา", ""] + [f"- {r}" for r in rules]
    return "\n".join(lines) + "\n"


def parse_rules(panel: dict) -> list[str]:
    """Pull the generator rules out of the panel's answer.

    The advisors answer in Markdown ("3) **RULES:**" then "* **ข้อ 1 ...:** ..."), so
    the rules are the bullet lines that follow the RULES marker, with the emphasis
    marks stripped. Falls back to any "ข้อ N" bullet when no marker is present.
    """
    out: list[str] = []
    for text in panel.values():
        got: list[str] = []
        lines = str(text).splitlines()
        grab = False
        for line in lines:
            stripped = line.strip()
            if not stripped:
                if grab and got:
                    grab = False
                continue
            head = re.sub(r"[*_`]", "", stripped).strip()
            if re.search(r"RULES", head, re.I):
                grab = True
                tail = re.sub(r"^.*RULES[^:]*:", "", head).strip()
                tail = re.sub(r"^[\d.)\s]+", "", tail).strip()
                if tail and len(tail) > 10 and not re.match(r"^(กฎ|rules)", tail, re.I):
                    got.append(tail)
                continue
            is_bullet = bool(re.match(r"^[-*•]|\d+[.)]", stripped))
            if (grab and is_bullet) or re.match(r"^[-*•]\s*\**ข้อ\s*\d", stripped):
                clean = re.sub(r"[*_`]", "", stripped)
                clean = re.sub(r"^[-*•\d.)\s]+", "", clean).strip()
                if len(clean) > 10:
                    got.append(clean)
        # Use the first advisor that produced rules and stop: mixing two answers
        # interleaves near-duplicates and one of them may be garbled.
        if got:
            out = got
            break
    seen, uniq = set(), []
    for r in out:
        r = re.sub(r"^ข้อ\s*\d+\s*[^:：]*[:：]\s*", "", r).strip()
        r = re.sub(r"^\**\s*", "", r).strip()
        if r and r not in seen:
            seen.add(r)
            uniq.append(r)
    return uniq[:3]


def forward_rules(channel: str, rules: list[str]) -> None:
    """Write the diagnosis rules into the insights file the generator reads.

    Without this the diagnosis is a dead-end report. The generator already reads
    content/insights/<name>.json for rules, so the same door video_review uses is
    the one to use here.
    """
    if not rules:
        return
    name = vr.GEN_ALIAS.get(channel, channel)
    path = os.path.join(ROOT, "content", "insights", f"{name}.json")
    blob = {}
    if os.path.exists(path):
        try:
            blob = json.load(open(path, encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            blob = {}
    existing = [r for r in blob.get("rules", []) if r not in rules]
    blob["rules"] = (rules + existing)[:8]
    blob["diagnosis_generated"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(blob, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    print(f"  forwarded {len(rules)} rules to content/insights/{name}.json")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", required=True, choices=list(vr.CHANNELS))
    ap.add_argument("--panel", action="store_true")
    ap.add_argument("--out", help="write the markdown report here")
    args = ap.parse_args()

    d = diagnose(args.channel, args.panel)
    os.makedirs(os.path.join(ROOT, "content", "diagnosis"), exist_ok=True)
    jpath = os.path.join(ROOT, "content", "diagnosis", f"{args.channel}.json")
    with open(jpath, "w", encoding="utf-8") as fh:
        json.dump(d, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    md = report_md(d)
    out = args.out or os.path.join(ROOT, "docs", f"DIAGNOSIS-{args.channel}.md")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(md)
    print(f"{args.channel}: " + ", ".join(f"{k}={v}" for k, v in d["counts"].items()))
    print(f"  wrote {os.path.relpath(jpath, ROOT)} and {os.path.relpath(out, ROOT)}")
    rules = parse_rules(d.get("panel", {}))
    for r in rules:
        print(f"  rule: {r}")
    forward_rules(args.channel, rules)
    return 0


if __name__ == "__main__":
    sys.exit(main())
