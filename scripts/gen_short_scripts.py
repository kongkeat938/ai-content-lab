#!/usr/bin/env python3
"""Generate fresh Shorts scripts with Gemini, so the pool never runs dry.

A publishing rail is useless without a supply of new material. This asks the free
Gemini text model for N new scripts, keeps the ones that pass a shape check, and
appends them to content/ch2_shorts/scripts.json without touching ids that are
already live. It knows what it already wrote, so it asks for new angles instead
of repeating itself.

    python3 scripts/gen_short_scripts.py --count 6
    python3 scripts/gen_short_scripts.py --count 6 --dry-run

Needs GEMINI_API_KEY. Free tier; gemini-3.5-flash-lite is the only model that
answers on this key (measured 2026-11-03).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SCRIPTS = os.path.join(ROOT, "content", "ch2_shorts", "scripts.json")
MODEL = "gemini-3.5-flash-lite"

ANGLES = [
    "ความคิดเรื่องงานพรุ่งนี้", "ตาสว่างทั้งที่ง่วง", "แบกเรื่องคนอื่นมาคิด",
    "กังวลเรื่องเงินตอนดึก", "คิดถึงความผิดพลาดในอดีต", "คิดวนซ้ำเรื่องเดิม",
    "กลัวอนาคต", "โกรธคนหนึ่งคนจนนอนไม่หลับ", "เปรียบเทียบตัวเองกับคนอื่น",
    "รู้สึกเหงาในคืนที่เงียบ", "กดดันเรื่องที่ยังไม่เกิดขึ้น", "เสียใจที่พูดผิดไปแล้ว",
    "ผัดวันประกันพรุ่งแล้วนอนไม่สบายใจ", "ร่างกายเกร็งเพราะความเครียดสะสม",
    "อยากหลับแต่สมองไม่ยอมหยุด", "กลัวตื่นมาสาย", "ไม่กล้าปล่อยวางเรื่องที่คุมไม่ได้",
    "คิดมากเรื่องสุขภาพ", "รู้สึกผิดกับคนในครอบครัว", "ทนเก็บความน้อยใจไว้คนเดียว",
]

PROMPT = """คุณคือผู้เขียนสคริปต์ Shorts ภาษาไทยให้ช่อง "Farmmer — ธรรมะก่อนนอน"
กลุ่มเป้าหมาย: คนไทยที่นอนไม่หลับ เครียด คิดมากตอนกลางคืน

เขียน Shorts ใหม่ {count} คลิป เรื่อง: {angles}
(ห้ามซ้ำกับที่เขียนไปแล้ว: {done})

แต่ละคลิปเป็น JSON object:
{{"hook":"ประโยคเปิด 1 บรรทัด หยุดนิ้วคนดู (ไม่เกิน 12 คำ)","lines":["...","...","...","..."],"cta":"ประโยคปิดชวนติดตาม 1 บรรทัด"}}

กติกา:
- lines 4-5 บรรทัด แต่ละบรรทัดสั้น 4-9 คำ
- เนื้อหาธรรมะใช้ได้จริง มี "หนึ่งสิ่งที่ทำได้จริง" แล้วทิ้งปมให้ไปดูคลิปยาว
- ห้ามใช้เลขอารบิกหรือเลขไทย ให้เขียนเป็นคำเสมอ (เช่น "หนึ่ง" ไม่ใช่ "1")
- ไม่มี emoji ไม่มี markdown

ตอบเป็น JSON array เท่านั้น"""


def ask(key: str, prompt: str) -> list:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={key}"
    body = json.dumps({"contents": [{"parts": [{"text": prompt}]}],
                       "generationConfig": {"responseMimeType": "application/json"}}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as fh:
        txt = json.load(fh)["candidates"][0]["content"]["parts"][0]["text"]
    return json.loads(txt)


def valid(s: dict) -> bool:
    if not isinstance(s, dict):
        return False
    if not s.get("hook") or not isinstance(s.get("lines"), list) or not s.get("cta"):
        return False
    if len(s["lines"]) < 3:
        return False
    joined = " ".join([s["hook"], *s["lines"], s["cta"]])
    # Digits must already be Thai words: edge-tts has no Thai number dictionary.
    return not re.search(r"[0-9๐-๙]", joined)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=6)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        sys.exit("GEMINI_API_KEY is not set")

    existing = []
    if os.path.exists(SCRIPTS):
        with open(SCRIPTS, encoding="utf-8") as fh:
            existing = json.load(fh)
    done = [s["hook"] for s in existing]

    angles = [a for a in ANGLES if a not in done][:max(args.count, 4)]
    fresh = ask(key, PROMPT.format(count=args.count, angles=", ".join(angles) or "เรื่องใหม่",
                                   done="; ".join(done[-12:]) or "ไม่มี"))
    fresh = [s for s in fresh if valid(s)]

    next_id = max([int(s["id"]) for s in existing] + [0]) + 1
    added = []
    for s in fresh[:args.count]:
        sid = f"{next_id:02d}"
        next_id += 1
        added.append({"id": sid, "hook": s["hook"], "lines": s["lines"], "cta": s["cta"]})

    print(f"{len(existing)} existing, {len(added)} new")
    for s in added:
        print(f"  {s['id']}: {s['hook']}")
    if args.dry_run or not added:
        return 0
    with open(SCRIPTS, "w", encoding="utf-8") as fh:
        json.dump(existing + added, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
