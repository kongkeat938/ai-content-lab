#!/usr/bin/env python3
"""Write a Thai description and tags for each long-form video, from the advisors.

Measured 2026-11-06: every changed video had **zero description and zero tags**.
That is the search surface left completely empty -- a description feeds YouTube
search and the video's own related-video rail, and tags disambiguate the topic.
This is the same free, no-new-consent lever as the titles and thumbnails: writing
`description` and `tags` needs only the `youtube.upload` scope the tokens hold.

The advisor panel (the two measured KEEP entries, gemini and pollinations) writes
a 2-3 sentence Thai description that carries the keyword, a soft call to action,
and 3 hashtags, plus a 10-15 item Thai tag list. The script shows the proposal and
writes it only with --apply.

`videos.update` replaces the whole `snippet` part, so the title and categoryId are
read first and written back unchanged -- a blind write would drop the title we just
set.

    python3 scripts/optimize_seo.py --channel genx --longform
    python3 scripts/optimize_seo.py --channel genx --longform --apply
    python3 scripts/optimize_seo.py --channel genx --ids paEd6W-3k1A --apply
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analytics import CHANNELS, access_token  # noqa: E402
from channel_admin import _get, API  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER = os.path.join(ROOT, "docs", "seo_changes.json")

THEMES = {
    "genx": ("ช่องปรัชญาชีวิตและกำลังใจสำหรับคนวัยกลางคน (Gen X) ข้อคิดการใช้ชีวิต "
             "การปล่อยวาง การพัฒนาตัวเอง และการมองโลกในแง่ดี"),
    "dharma": ("ช่องธรรมะก่อนนอน ฟังแล้วใจสงบ หลับสบาย ปล่อยวางความเครียด "
               "และเรื่องราวธรรมะสอนใจ"),
    "kongkeat": ("ช่องนิทานไทยและเรื่องเล่าการ์ตูนสำหรับเด็กและครอบครัว "
                 "นิทานสอนใจ เรื่องเล่าก่อนนอน และตำนานไทย"),
}

PROMPT = (
    "คุณเป็นผู้เชี่ยวชาญ SEO YouTube ภาษาไทย เขียน 'คำอธิบายคลิป' และ 'แท็ก' "
    "สำหรับคลิปนี้ ให้คนค้นเจอและอยากกดดู ตามเงื่อนไข:\n"
    "- คำอธิบาย: ภาษาไทย 2-3 ประโยค (ประมาณ 200-350 ตัวอักษร) ใส่คำค้นหลัก "
    "1-2 คำจากชื่อคลิป คงความหมายเดิมของคลิป ห้ามสัญญาเกินจริง "
    "ปิดท้ายด้วย 3 hashtag ที่ตรงเนื้อหา\n"
    "- แท็ก: 10-15 คำ ภาษาไทย เป็นคำที่คนค้นหาจริง ตรงกับเนื้อหาคลิปนี้ "
    "(ไม่ใช่คำซ้ำ ๆ ทุกคลิป) แต่ละคำไม่เกิน 30 ตัวอักษร\n"
    'ตอบเป็น JSON เท่านั้น: {{"description": "...", "tags": ["...", "..."]}}\n\n'
    "ช่อง: {theme}\nชื่อคลิป: {title}\n"
)


def _json_of(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return {}


def _seconds(iso: str) -> int:
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not m:
        return 0
    h, mi, s = (int(x) if x else 0 for x in m.groups())
    return h * 3600 + mi * 60 + s


def ask_gemini(prompt: str) -> dict:
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY not set")
    url = ("https://generativelanguage.googleapis.com/v1beta/models/"
           f"gemini-3.5-flash-lite:generateContent?key={key}")
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.6}}
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as fh:
        d = json.load(fh)
    return _json_of(d["candidates"][0]["content"]["parts"][0]["text"])


def ask_pollinations(prompt: str) -> dict:
    body = {"model": "openai-fast", "messages": [{"role": "user", "content": prompt}]}
    req = urllib.request.Request("https://text.pollinations.ai/openai",
                                 data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as fh:
        d = json.load(fh)
    return _json_of(d["choices"][0]["message"].get("content") or "")


ADVISORS = {"gemini": ask_gemini, "pollinations": ask_pollinations}


def _clean_tags(raw) -> list[str]:
    out = []
    for t in raw if isinstance(raw, list) else []:
        t = str(t).strip().lstrip("#")
        if t and len(t) <= 30 and t not in out:
            out.append(t)
    return out[:15]


def propose(title: str, theme: str) -> dict:
    prompt = PROMPT.format(theme=theme, title=title)

    def run(name: str) -> tuple[str, dict]:
        try:
            return name, ADVISORS[name](prompt)
        except Exception as exc:  # noqa: BLE001
            return name, {"error": str(exc)[:120]}

    with ThreadPoolExecutor(max_workers=len(ADVISORS)) as pool:
        got = dict(pool.map(run, list(ADVISORS)))

    for name in ADVISORS:
        d = got.get(name) or {}
        desc = (d.get("description") or "").strip()
        if desc and re.search(r"[\u0E00-\u0E7F]", desc):
            d["tags"] = _clean_tags(d.get("tags"))
            d["by"] = name
            return d
    return {"error": "no usable description", "raw": got}


def write(vid: str, title: str, category: str, desc: str, tags: list[str],
          token: str) -> dict:
    body = {"id": vid, "snippet": {"title": title, "categoryId": category,
                                   "description": desc, "tags": tags}}
    req = urllib.request.Request(API + "videos?part=snippet", data=json.dumps(body).encode(),
                                 method="PUT",
                                 headers={"Authorization": f"Bearer {token}",
                                          "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=40) as fh:
        return json.load(fh)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", default="genx", choices=list(CHANNELS))
    ap.add_argument("--ids", default="")
    ap.add_argument("--longform", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    with open(os.path.join(ROOT, "docs", "title_changes.json"), encoding="utf-8") as fh:
        changes = {c["id"]: c for c in json.load(fh)["changes"]}

    token = access_token(CHANNELS[args.channel][0])
    ids = [x.strip() for x in args.ids.split(",") if x.strip()]
    if not ids:
        if not args.longform:
            sys.exit("give --ids or --longform")
        it = _get("channels", {"part": "contentDetails", "mine": "true"}, token)["items"][0]
        up = it["contentDetails"]["relatedPlaylists"]["uploads"]
        allids, page = [], None
        while True:
            p = {"part": "contentDetails", "playlistId": up, "maxResults": "50"}
            if page:
                p["pageToken"] = page
            r = _get("playlistItems", p, token)
            allids += [x["contentDetails"]["videoId"] for x in r.get("items", [])]
            page = r.get("nextPageToken")
            if not page:
                break
        # only videos over 3 minutes that are also in the title ledger
        lf = []
        for i in range(0, len(allids), 50):
            for v in _get("videos", {"part": "contentDetails",
                                     "id": ",".join(allids[i:i + 50])}, token).get("items", []):
                if _seconds(v["contentDetails"]["duration"]) > 180 and v["id"] in changes:
                    lf.append(v["id"])
        ids = lf
    if args.limit:
        ids = ids[:args.limit]

    vids = _get("videos", {"part": "snippet,contentDetails",
                           "id": ",".join(ids)}, token).get("items", [])
    theme = THEMES.get(args.channel, "")
    print(f"=== {args.channel}: {len(vids)} video(s)")

    done = []
    for v in vids:
        s = v["snippet"]
        prop = propose(s["title"], theme)
        desc = (prop.get("description") or "").strip()
        tags = prop.get("tags") or []
        if not desc:
            print(f"  {v['id']}: no description ({prop.get('error')})")
            continue
        print(f"  {v['id']}  by={prop.get('by')}  desc={len(desc)}ch  tags={len(tags)}")
        print(f"     {desc[:110]}")
        if args.apply:
            try:
                write(v["id"], s["title"], s.get("categoryId", "22"), desc, tags, token)
                done.append({"id": v["id"], "channel": args.channel, "description": desc,
                             "tags": tags, "by": prop.get("by"),
                             "at": datetime.now(timezone.utc).isoformat()})
                print("     -> applied")
            except urllib.error.HTTPError as exc:
                print(f"     -> FAILED HTTP {exc.code}: {exc.read().decode()[:120]}")

    if done:
        os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
        doc = {"changes": []}
        if os.path.exists(LEDGER):
            with open(LEDGER, encoding="utf-8") as fh:
                doc = json.load(fh)
        doc.setdefault("changes", []).extend(done)
        with open(LEDGER, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, ensure_ascii=False, indent=2)
        print(f"applied {len(done)}; ledger {LEDGER}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
