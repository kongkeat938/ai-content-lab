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

# The committed manifests that map video_id -> the title we uploaded. They are the
# fallback when the Data API quota is spent: videos.list (needed only for titles)
# 403s on most days here, and without them every winner reads "(title
# unavailable)", so the panel judges a channel it cannot see and returns generic
# filler subjects that flow into gen_short_scripts. Measured 2026-11-09: all three
# channels wrote "(title unavailable)" for every winner.
TITLE_MANIFESTS = {
    "ch1": ("content/ch1_shorts.json", "content/ch1_publish.json"),
    "ch2": ("content/ch2_shorts.json", "content/ch2_publish.json"),
    "ch3": ("content/ch3_shorts.json", "content/ch3_publish.json"),
    "ch4": ("content/ch4_shorts.json", "content/ch4_publish.json"),
}

# The publish manifests list the LONG-FORM uploads -- the only videos that count
# toward YPP watch-hours. Their ids let the learning loop tell a long-form winner
# from a Short. Without this the "winners" were whatever had the most *views*,
# which is always the Shorts: a Short can out-view a long-form a hundred to one
# while contributing zero YPP watch-hours, so the panel learned from the wrong
# videos and the long-form rail (the one that gates the business) learned nothing.
LONGFORM_MANIFESTS = {
    "ch1": "content/ch1_publish.json",
    "ch2": "content/ch2_publish.json",
    "ch3": "content/ch3_publish.json",
    "ch4": "content/ch4_publish.json",
}


def longform_ids(channel: str) -> set:
    """video_ids of this channel's long-form uploads (the YPP-qualifying ones)."""
    rel = LONGFORM_MANIFESTS.get(channel)
    path = os.path.join(ROOT, rel) if rel else ""
    if not path or not os.path.exists(path):
        return set()
    try:
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
    except (json.JSONDecodeError, OSError):
        return set()
    return {v.get("video_id") for v in doc.get("videos", [])
            if v.get("video_id") and v.get("state") == "published"}


def rank_winners(per_video: list[dict], longform: list[dict] | None) -> list[str]:
    """The videos the learning loop should learn from: the long-form ones, ranked
    by the watch time they actually earned. Falls back to top-by-views only when a
    channel has no long-form at all (so the loop still runs on a Shorts-only one).
    """
    if longform:
        return [r["title"] for r in longform[:6]]
    return [r["title"] for r in per_video[:6]]



def manifest_titles(channel: str) -> dict[str, str]:
    """video_id -> title, from committed sources (no API, no quota).

    Sources, later winning over earlier: the per-channel learned cache
    (content/titles/<ch>.json, written whenever the live API does answer), the
    upload manifests, and the SEO title ledger. All offline, so a spent quota
    still yields real titles.
    """
    out: dict[str, str] = {}
    # The learned cache first, so a title once seen is never lost to a later quota
    # day. It is per channel, so the parallel studio-ai jobs cannot race on it.
    cache = os.path.join(ROOT, "content", "titles", f"{channel}.json")
    if os.path.exists(cache):
        try:
            with open(cache, encoding="utf-8") as fh:
                for vid, title in json.load(fh).items():
                    if vid and title:
                        out[vid] = title
        except (json.JSONDecodeError, OSError):
            pass
    for rel in TITLE_MANIFESTS.get(channel, ()):
        path = os.path.join(ROOT, rel)
        if not os.path.exists(path):
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                blob = json.load(fh)
        except (json.JSONDecodeError, OSError):
            continue
        for rec in (blob.get("shorts") or {}).values():
            if rec.get("video_id") and rec.get("title"):
                out[rec["video_id"]] = rec["title"]
        for rec in blob.get("videos") or []:
            if rec.get("video_id") and rec.get("title"):
                out[rec["video_id"]] = rec["title"]
    tc = os.path.join(ROOT, "docs", "title_changes.json")
    if os.path.exists(tc):
        try:
            with open(tc, encoding="utf-8") as fh:
                for rec in json.load(fh).get("changes", []):
                    if rec.get("id") and rec.get("new_title"):
                        out[rec["id"]] = rec["new_title"]
        except (json.JSONDecodeError, OSError):
            pass
    return out


def oembed_titles(ids: list[str], cap: int = 50) -> dict[str, str]:
    """Titles from YouTube's oEmbed endpoint -- no auth, no Data API quota.

    The last resort for a video the Data API cannot answer for and the committed
    manifests do not know (e.g. a legacy Short uploaded before the manifest
    existed). One small HTTP call per id, capped so a run cannot fan out.
    """
    out: dict[str, str] = {}
    for vid in ids[:cap]:
        url = "https://www.youtube.com/oembed?" + urllib.parse.urlencode(
            {"url": f"https://www.youtube.com/watch?v={vid}", "format": "json"})
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as fh:
                title = json.load(fh).get("title", "")
            if title:
                out[vid] = title
        except Exception:  # noqa: BLE001 - a missing title is cosmetic
            continue
    return out


def remember_titles(channel: str, titles: dict[str, str]) -> None:
    """Persist live-resolved titles to the per-channel cache so a later quota day
    cannot lose them again. One writer per channel (its own matrix job)."""
    if not titles:
        return
    d = os.path.join(ROOT, "content", "titles")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, f"{channel}.json")
    cache: dict[str, str] = {}
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as fh:
                cache = json.load(fh)
        except (json.JSONDecodeError, OSError):
            cache = {}
    cache.update({k: v for k, v in titles.items() if k and v})
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(cache, fh, ensure_ascii=False, indent=1, sort_keys=True)


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


def gather(tok: str, days: int, channel: str = "") -> dict:
    end = dt.date.today()
    start = end - dt.timedelta(days=days)
    base = {"ids": "channel==MINE", "startDate": str(start), "endDate": str(end)}
    per_video = rows(report(tok, {**base, "metrics":
        "views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage",
        "dimensions": "video", "sort": "-views", "maxResults": "50"}))
    by_day = rows(report(tok, {**base, "metrics": "views,estimatedMinutesWatched",
                               "dimensions": "day", "sort": "day"}))
    # The long-form-only view. This is the one the learning loop must use: watch
    # time on the videos that count toward YPP, ranked by watch time (not views).
    lf_ids = longform_ids(channel)
    longform: list[dict] = []
    if lf_ids:
        try:
            lf = rows(report(tok, {**base, "metrics":
                "views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage",
                "dimensions": "video", "filters": "video==" + ",".join(sorted(lf_ids)),
                "sort": "-estimatedMinutesWatched", "maxResults": "50"}))
            # Keep the watch-time order; the report already sorts by it.
            longform = [r for r in lf if r["video"] in lf_ids]
        except Exception:  # noqa: BLE001 - no long-form data must not break the run
            longform = []
    # Committed manifests first, live Data API second: the API 403s on a spent
    # quota (most days), and a title we uploaded is better evidence than none.
    try:
        live = titles_for(tok, [r["video"] for r in per_video])
    except Exception:  # noqa: BLE001 - titles are cosmetic; the grades still count
        live = {}
    fill_titles(channel, per_video, live)
    fill_titles(channel, longform, live)
    # Remember only the titles we had to resolve beyond the committed manifests
    # (live API + oEmbed), so a later quota day cannot lose them. The manifests
    # stay authoritative; the cache only fills their gaps.
    known = manifest_titles(channel)
    remember_titles(channel, {r["video"]: r["title"] for r in per_video
                              if r["title"] != "(title unavailable)" and r["video"] not in known})
    return {"start": str(start), "end": str(end), "per_video": per_video,
            "longform": longform, "by_day": by_day}


def fill_titles(channel: str, per_video: list[dict], live: dict[str, str]) -> None:
    """Set r['title'] for each row: live Data API title, else the committed manifest,
    else YouTube oEmbed (no quota) for the stragglers.

    The first two are offline; only ids still unknown reach oEmbed, so a normal run
    makes no extra calls.
    """
    names = manifest_titles(channel)
    names.update(live)
    unknown = [r["video"] for r in per_video if r["video"] not in names]
    if unknown:
        names.update(oembed_titles(unknown))
    for r in per_video:
        r["title"] = names.get(r["video"], "(title unavailable)")


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
    lf = data.get("longform") or []
    if lf:
        lines.append("")
        lines.append("คลิปยาว (นับเข้า YPP) เรียงตามนาทีดู — นี่คือคลิปที่ต้องเรียนแบบ:")
        for r in lf[:8]:
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
    "จากนั้นให้เขียน 2 บรรทัดสุดท้าย:\n"
    "- ขึ้นต้นด้วย 'THEMES:' แล้วตามด้วย 3 ธีมสำหรับ 'คลิปยาวธรรมะก่อนนอน' "
    "(บรรยาย 20-120 นาที) คั่นด้วย ' | ' — ธีมที่คนนอนไม่หลับอยากฟังจริง\n"
    "- ขึ้นต้นด้วย 'TOPICS:' แล้วตามด้วยหัวข้อ Shorts ใหม่ 8 หัวข้อ คั่นด้วย ' | '")

# Measured 2026-11-10: kongkeat's feed was withdrawn while its pool was full of
# flat warm scenes, so when the panel proposes its next subjects they must carry a
# tension, not another picture. The generator rejects a flat hook regardless; this
# keeps the *subjects* from steering it back to the shape that lost the feed.
TOPICS_HINT = {
    "kongkeat": ("หัวข้อ Shorts ใหม่ 8 หัวข้อ ที่มี 'ปมตึง' ในครอบครัว: เป็นคำถาม "
                 "(ทำไม...), ความลับที่ถูกปิดบัง, การจากลา/การสูญเสีย, หรือความผิดหวัง "
                 "(ห้ามเป็นฉากอบอุ่นราบเรียบ เช่น ทำกับข้าวด้วยกัน)"),
}


def question_for(channel: str) -> str:
    hint = TOPICS_HINT.get(channel)
    if not hint:
        return QUESTION
    return QUESTION.replace(
        "หัวข้อ Shorts ใหม่ 8 หัวข้อ คั่นด้วย ' | '", hint + " คั่นด้วย ' | '")


def parse_topics(text: str) -> list[str]:
    """Pull the generator's next subjects out of a panel answer."""
    return _parse_tagged(text, "TOPICS:", 4, 80, 8)


def parse_themes(text: str) -> list[str]:
    """Pull long-form night-set themes out of a panel answer (20-80 chars)."""
    return _parse_tagged(text, "THEMES:", 6, 80, 3)


def _parse_tagged(text: str, tag: str, lo: int, hi: int, cap: int) -> list[str]:
    for line in reversed(text.splitlines()):
        if tag in line:
            blob = line.split(tag, 1)[1]
            items = [t.strip(" -*\t") for t in blob.replace("|", "\n").splitlines()]
            return [t for t in items if lo <= len(t) <= hi][:cap]
    return []


def write_insights(channel: str, per_video: list[dict], answers: dict[str, str],
                   longform: list[dict] | None = None) -> str:
    """Feed the generator: the winning hooks plus the panel's next subjects.

    The winners are the **long-form** videos ranked by watch time, not the top
    videos by views. Views always crown the Shorts, which contribute zero YPP
    watch-hours; learning from them taught the long-form rail nothing. When a
    channel has no long-form yet, this falls back to top-by-views so the loop
    still runs.
    """
    winners = rank_winners(per_video, longform)
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
    themes: list[str] = []
    for ans in answers.values():
        for t in parse_themes(ans):
            if t not in themes:
                themes.append(t)
        if themes:
            break
    blob = {"generated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "winners": winners, "topics": topics}
    if themes:
        # Long-form night-set themes for gen_night_scripts.py -- the only content
        # that moves YPP watch-hours. Kept separate from the Shorts topics above.
        blob["themes"] = themes
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
    data = gather(tok, a.days, a.channel)
    text = brief(data)
    print(text)

    answers: dict[str, str] = {}
    if a.panel:
        print("\n== panel ==")
        answers = ask_panel(question_for(a.channel), "ข้อมูลจริง:\n" + text)
        for name, ans in answers.items():
            print(f"\n### {name}\n{ans}")
            text += f"\n\n### {name}\n{ans}"
        ins = write_insights(a.channel, data["per_video"], answers, data.get("longform"))
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
