#!/usr/bin/env python3
"""A cloud stand-in for the YouTube Studio "Inspiration" tab.

Measured 2026-11-07: YouTube Studio cannot be driven from the cloud at all --
studio.youtube.com redirects to the Google login on every path (pod, cloud
browser, and a bare curl all get a 302 to accounts.google.com), and the Data API
has no endpoint for the Inspiration tab. What *does* work from the cloud is the
**YouTube Analytics API** with the channel's own refresh token: per-video views,
watch time and average view duration all come back.

So this tool reads the real numbers, ranks the videos, and hands that measured
picture to the advisor panel, which returns a concrete content plan. That is the
same job the Studio tab does, done with data the cloud can actually reach.

    python3 scripts/studio_ai.py --channel ch4
    python3 scripts/studio_ai.py --channel ch4 --days 28 --panel
    python3 scripts/studio_ai.py --channel ch4 --panel --out docs/STUDIO-AI-ch4.md
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TOKEN_URL = "https://oauth2.googleapis.com/token"
ANALYTICS = "https://youtubeanalytics.googleapis.com/v2/reports"
DATA = "https://www.googleapis.com/youtube/v3"

CHANNELS = {
    "ch1": "YT_CH1_REFRESH_TOKEN",
    "ch2": "YT_CH2_REFRESH_TOKEN",
    "ch3": "YT_CH3_REFRESH_TOKEN",
    "ch4": "YT_CH4_REFRESH_TOKEN",
}

# The generator names its channels differently; map them so one insights file
# serves both.
GEN_ALIAS = {"ch1": "genx", "ch2": "dharma", "ch4": "kongkeat-story"}


def access_token(env: str) -> str:
    data = urllib.parse.urlencode({
        "client_id": os.environ["YT_CLIENT_ID"], "client_secret": os.environ["YT_CLIENT_SECRET"],
        "refresh_token": os.environ[env], "grant_type": "refresh_token"}).encode()
    with urllib.request.urlopen(urllib.request.Request(TOKEN_URL, data=data), timeout=30) as fh:
        return json.load(fh)["access_token"]


def report(tok: str, q: dict) -> dict:
    url = f"{ANALYTICS}?{urllib.parse.urlencode(q)}"
    with urllib.request.urlopen(urllib.request.Request(
            url, headers={"Authorization": f"Bearer {tok}"}), timeout=60) as fh:
        return json.load(fh)


def rows(d: dict) -> list[dict]:
    cols = [h["name"] for h in d.get("columnHeaders", [])]
    return [dict(zip(cols, r)) for r in d.get("rows", [])]


def titles_for(tok: str, ids: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for i in range(0, len(ids), 50):
        chunk = ids[i:i + 50]
        url = (f"{DATA}/videos?part=snippet&id={','.join(chunk)}")
        try:
            with urllib.request.urlopen(urllib.request.Request(
                    url, headers={"Authorization": f"Bearer {tok}"}), timeout=40) as fh:
                for it in json.load(fh).get("items", []):
                    out[it["id"]] = it["snippet"]["title"]
        except urllib.error.HTTPError:
            continue
    return out


def gather(tok: str, days: int) -> dict:
    end = dt.date.today()
    start = end - dt.timedelta(days=days)
    base = {"ids": "channel==MINE", "startDate": str(start), "endDate": str(end)}
    per_video = rows(report(tok, {**base, "metrics":
        "views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage",
        "dimensions": "video", "sort": "-views", "maxResults": "50"}))
    by_day = rows(report(tok, {**base, "metrics": "views,estimatedMinutesWatched",
                               "dimensions": "day", "sort": "day"}))
    names = titles_for(tok, [r["video"] for r in per_video])
    for r in per_video:
        r["title"] = names.get(r["video"], "(title unavailable)")
    return {"start": str(start), "end": str(end), "per_video": per_video, "by_day": by_day}


def brief(data: dict) -> str:
    pv = data["per_video"]
    tv = sum(r["views"] for r in pv)
    tw = sum(r["estimatedMinutesWatched"] for r in pv)
    top = pv[:12]
    lines = [
        f"ช่วงข้อมูล {data['start']}..{data['end']} (28 วันล่าสุด)",
        f"ยอดวิวรวม {tv:,} · นาทีดูรวม {tw:,}",
        "12 คลิปยอดวิวสูงสุด (views | นาทีดู | ดูเฉลี่ยวินาที | ดูจบ %):",
    ]
    for r in top:
        lines.append(f"  - {r['views']:>5} | {r['estimatedMinutesWatched']:>5} | "
                     f"{r['averageViewDuration']:>3} | {r['averageViewPercentage']:>5}% | {r['title'][:60]}")
    return "\n".join(lines)


def ask_panel(question: str, extra: str) -> dict[str, str]:
    sys.path.insert(0, HERE)
    import advise  # noqa: PLC0415 - local module, imported lazily
    out: dict[str, str] = {}
    for name in ("gemini", "pollinations"):
        fn = advise.ADVISORS.get(name)
        if not fn:
            continue
        try:
            out[name] = fn(f"{extra}\n\n{question}\n\n{advise.SYSTEM}").strip()
        except Exception as exc:  # noqa: BLE001 - a dead advisor must not stop the run
            out[name] = f"(unavailable: {str(exc)[:160]})"
    return out


QUESTION = (
    "จากตัวเลขจริงของช่องข้างบน จงตอบ 3 ข้อสั้น ๆ เป็นภาษาไทย:\n"
    "1) คลิปแบบไหนทำผลงานดีที่สุด (ดูจากชื่อ+ตัวเลข) และเพราะอะไร\n"
    "2) 3 ธีมที่ควรทำต่อ เรียงตามโอกาส\n"
    "3) hook 3 วินาทีแรกควรพูดอะไร\n"
    "จากนั้นบรรทัดสุดท้าย ให้เขียนหัวข้อ Shorts ใหม่ 8 หัวข้อ ที่ต่อยอดจากคลิปที่ทำได้ดี "
    "ในรูปบรรทัดเดียว ขึ้นต้นด้วย 'TOPICS:' แล้วคั่นแต่ละหัวข้อด้วย ' | '")


def parse_topics(text: str) -> list[str]:
    """Pull the generator's next subjects out of a panel answer."""
    for line in reversed(text.splitlines()):
        if "TOPICS:" in line:
            blob = line.split("TOPICS:", 1)[1]
            items = [t.strip(" -*\t") for t in blob.replace("|", "\n").splitlines()]
            return [t for t in items if 4 <= len(t) <= 80][:8]
    return []


def write_insights(channel: str, per_video: list[dict], answers: dict[str, str]) -> str:
    """Feed the generator: the winning hooks plus the panel's next subjects."""
    top = [r for r in per_video[:6]]
    winners = [r["title"] for r in top]
    topics: list[str] = []
    for ans in answers.values():
        for t in parse_topics(ans):
            if t not in topics:
                topics.append(t)
        if topics:
            # First vendor that yields usable subjects wins. Later vendors only
            # pad the list if the first returned nothing usable (measured
            # 2026-11-07: Gemini gave clean subjects, Pollinations was garbled).
            break
    if not topics:
        topics = winners[:5]
    blob = {"generated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "winners": winners, "topics": topics}
    # Write under the channel id and under the generator's own name, so
    # gen_short_scripts.py finds it without a copy step.
    names = {channel, GEN_ALIAS.get(channel, channel)}
    out = ""
    for name in names:
        path = os.path.join(ROOT, "content", "insights", f"{name}.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(blob, fh, ensure_ascii=False, indent=1)
        out = path
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--channel", default="ch4", choices=sorted(CHANNELS))
    ap.add_argument("--days", type=int, default=28)
    ap.add_argument("--panel", action="store_true", help="also ask the advisor panel")
    ap.add_argument("--out", default="", help="write the report to this path")
    a = ap.parse_args()

    tok = access_token(CHANNELS[a.channel])
    data = gather(tok, a.days)
    text = brief(data)
    print(text)

    answers: dict[str, str] = {}
    if a.panel:
        print("\n== panel ==")
        answers = ask_panel(QUESTION, "ข้อมูลจริง:\n" + text)
        for name, ans in answers.items():
            print(f"\n### {name}\n{ans}")
            text += f"\n\n### {name}\n{ans}"
        ins = write_insights(a.channel, data["per_video"], answers)
        print(f"\nwrote {ins}")

    if a.out:
        path = a.out if os.path.isabs(a.out) else os.path.join(ROOT, a.out)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(f"# Studio AI (cloud) — {a.channel}\n\n{text}\n")
        print(f"\nwrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
