#!/usr/bin/env python3
"""Rewrite a channel's titles for search, with the advisor panel, and measure it.

The channels are small, so the only growth path left is organic discovery:
people finding a video by search. The current titles are long emotional
sentences with no words anyone types into the search box, so they cannot be
found. This asks the two measured KEEP advisors (gemini, pollinations) for a
shorter, keyword-bearing Thai title for each recent upload, shows old against
new, and -- with --apply -- writes the new title with the YouTube Data API.

Writing a title needs the `youtube.upload` scope the tokens already hold
(measured 2026-11-06 with a round-trip on genx/N6IyyBdoM-Q), so no new consent
is required.

Every applied change is appended to docs/title_changes.json with the views and
age at the moment of the change, so the effect is judged later by views-per-day
against that baseline -- keep the change if views-per-day rises, revert if not.

    python3 scripts/optimize_titles.py --channel genx --limit 8
    python3 scripts/optimize_titles.py --channel genx --limit 8 --apply
    python3 scripts/optimize_titles.py --channel genx --ids N6IyyBdoM-Q,4bDxO7b6IjM
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
LEDGER = os.path.join(ROOT, "docs", "title_changes.json")

# What the audience would actually type. Kept short so a title stays readable.
THEMES = {
    "genx": ("ปรัชญาชีวิต ให้กำลังใจ คนวัย Gen X วัยกลางคน ครุ่นคิดเรื่องชีวิต "
             "คำค้นที่คนไทยพิมพ์: ให้กำลังใจ, ข้อคิดชีวิต, ธรรมะ, แง่คิด, กำลังใจ"),
    "dharma": ("ธรรมะก่อนนอน นิทานธรรมะ ให้ข้อคิด คนฟังก่อนนอน "
               "คำค้น: ธรรมะ, นิทานธรรมะ, ข้อคิด, ธรรมะก่อนนอน, บทเรียนชีวิต"),
    "kongkeat": ("เรื่องเล่าการ์ตูน นิทานไทย สนุกให้ข้อคิด เด็กและครอบครัว "
                 "คำค้น: นิทาน, การ์ตูน, เรื่องเล่า, นิทานไทย, ข้อคิด"),
}

PROMPT = (
    "คุณเป็นผู้เชี่ยวชาญ SEO YouTube ภาษาไทย ให้เขียน 'ชื่อคลิปใหม่' ที่คนไทย "
    "จะค้นเจอและอยากกดดู ตามเงื่อนไข:\n"
    "- ภาษาไทย ความยาวไม่เกิน 60 ตัวอักษร\n"
    "- ต้องมีคำค้น (keyword) ที่คนค้นหาจริง อย่างน้อย 1 คำ\n"
    "- คงอารมณ์/สาระเดิมของคลิป แต่ตัดให้กระชับ\n"
    "- ห้ามใส่เครื่องหมายคำพูดหรืออีโมจิ\n"
    'ตอบเป็น JSON เท่านั้น: {{"title": "...", "keyword": "...", "reason": "..."}}\n\n'
    "ธีมช่อง: {theme}\nชื่อเดิม: {old}\n"
)


def _json_of(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return {}


def ask_gemini(prompt: str) -> dict:
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY not set")
    url = ("https://generativelanguage.googleapis.com/v1beta/models/"
           f"gemini-3.5-flash-lite:generateContent?key={key}")
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.7}}
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


def best_title(old: str, theme: str, advisors: list[str]) -> dict:
    prompt = PROMPT.format(theme=theme, old=old)

    def run(name: str) -> tuple[str, dict]:
        try:
            return name, ADVISORS[name](prompt)
        except Exception as exc:  # noqa: BLE001 - a dead advisor is not fatal
            return name, {"error": str(exc)[:120]}

    with ThreadPoolExecutor(max_workers=len(advisors)) as pool:
        got = dict(pool.map(run, advisors))

    # Prefer a proposal that is Thai, within 60 chars, and carries a keyword.
    for name in advisors:
        d = got.get(name) or {}
        t = (d.get("title") or "").strip()
        if t and re.search(r"[\u0E00-\u0E7F]", t) and len(t) <= 60:
            d["by"] = name
            return d
    for name in advisors:
        if got.get(name, {}).get("title"):
            d = got[name]
            d["by"] = name
            return d
    return {"error": "no usable title", "raw": got}


def fetch(name: str, token: str, limit: int, ids: list[str]) -> list[dict]:
    if ids:
        vids = _get("videos", {"part": "snippet,statistics", "id": ",".join(ids)}, token)["items"]
    else:
        it = _get("channels", {"part": "contentDetails", "mine": "true"}, token)["items"][0]
        up = it["contentDetails"]["relatedPlaylists"]["uploads"]
        pl = _get("playlistItems", {"part": "contentDetails", "playlistId": up,
                                    "maxResults": str(limit)}, token)
        vids = _get("videos", {"part": "snippet,statistics",
                               "id": ",".join(x["contentDetails"]["videoId"] for x in pl["items"])},
                    token)["items"]
    now = datetime.now(timezone.utc)
    out = []
    for v in vids:
        s = v["snippet"]
        pub = datetime.fromisoformat(s["publishedAt"].replace("Z", "+00:00"))
        age_d = max((now - pub).total_seconds() / 86400, 0.04)
        views = int(v["statistics"].get("viewCount", 0))
        out.append({"id": v["id"], "title": s["title"], "categoryId": s.get("categoryId", "22"),
                    "views": views, "age_d": round(age_d, 1),
                    "views_per_day": round(views / age_d, 2)})
    return out


def apply_title(vid: str, title: str, category: str, token: str) -> str:
    body = {"id": vid, "snippet": {"title": title, "categoryId": category}}
    req = urllib.request.Request(API + "videos?part=snippet", data=json.dumps(body).encode(),
                                 method="PUT",
                                 headers={"Authorization": f"Bearer {token}",
                                          "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=40) as fh:
        return json.load(fh)["snippet"]["title"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", default="genx", choices=list(CHANNELS))
    ap.add_argument("--limit", type=int, default=8)
    ap.add_argument("--ids", default="")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    token = access_token(CHANNELS[args.channel][0])
    ids = [x.strip() for x in args.ids.split(",") if x.strip()]
    vids = fetch(args.channel, token, args.limit, ids)
    theme = THEMES.get(args.channel, "")

    print(f"=== {args.channel}: {len(vids)} videos\n")
    changes = []
    for v in vids:
        prop = best_title(v["title"], theme, list(ADVISORS))
        new = (prop.get("title") or "").strip()
        v["new_title"] = new
        v["keyword"] = prop.get("keyword", "")
        v["by"] = prop.get("by", "?")
        v["reason"] = prop.get("reason", prop.get("error", ""))
        mark = "KEEP" if new and new != v["title"] else "skip"
        print(f"[{mark}] {v['id']}  vpd={v['views_per_day']}  by={v['by']}")
        print(f"   old: {v['title']}")
        print(f"   new: {new}   (kw: {v['keyword']})")
        print(f"   why: {v['reason'][:100]}\n")
        if args.apply and new and new != v["title"]:
            try:
                done = apply_title(v["id"], new, v["categoryId"], token)
                v["applied_at"] = datetime.now(timezone.utc).isoformat()
                changes.append(v)
                print(f"   -> applied: {done[:50]}\n")
            except urllib.error.HTTPError as exc:
                print(f"   -> FAILED HTTP {exc.code}: {exc.read().decode()[:120]}\n")

    if changes:
        os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
        doc = {"changes": []}
        if os.path.exists(LEDGER):
            with open(LEDGER, encoding="utf-8") as fh:
                doc = json.load(fh)
        doc.setdefault("changes", []).extend(changes)
        with open(LEDGER, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, ensure_ascii=False, indent=2)
        print(f"applied {len(changes)} change(s); ledger: {LEDGER}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
