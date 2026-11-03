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
MODEL = "gemini-3.5-flash-lite"

CHANNELS = {
    "dharma": {
        "path": os.path.join(ROOT, "content", "ch2_shorts", "scripts.json"),
        "angles": [
            "ความคิดเรื่องงานพรุ่งนี้", "ตาสว่างทั้งที่ง่วง", "แบกเรื่องคนอื่นมาคิด",
            "กังวลเรื่องเงินตอนดึก", "คิดถึงความผิดพลาดในอดีต", "คิดวนซ้ำเรื่องเดิม",
            "กลัวอนาคต", "โกรธคนหนึ่งคนจนนอนไม่หลับ", "เปรียบเทียบตัวเองกับคนอื่น",
            "รู้สึกเหงาในคืนที่เงียบ", "กดดันเรื่องที่ยังไม่เกิดขึ้น", "เสียใจที่พูดผิดไปแล้ว",
            "ผัดวันประกันพรุ่งแล้วนอนไม่สบายใจ", "ร่างกายเกร็งเพราะความเครียดสะสม",
            "อยากหลับแต่สมองไม่ยอมหยุด", "กลัวตื่นมาสาย", "ไม่กล้าปล่อยวางเรื่องที่คุมไม่ได้",
            "คิดมากเรื่องสุขภาพ", "รู้สึกผิดกับคนในครอบครัว", "ทนเก็บความน้อยใจไว้คนเดียว",
            "ตื่นมาแล้วยังเหนื่อย", "ใจสั่นตอนตีสาม", "คิดถึงคนที่จากไป", "รู้สึกผิดที่ได้พักผ่อน",
            "ทำงานหนักจนหลับไม่สนิท", "เปรียบเทียบชีวิตกับคนอื่นตอนดึก", "กลัวแก่ตัว",
            "ความโกรธที่เก็บไว้ทั้งวัน", "กังวลแบบไม่มีเหตุผล", "รู้สึกตัวคนเดียวในโลก",
            "ฝันร้ายซ้ำ ๆ", "นอนดึกเพราะมือถือ", "ความเครียดสะสมในร่างกาย",
            "อยากหนีไปเริ่มใหม่", "กลัวตัดสินใจผิด", "รู้สึกว่าตัวเองไม่พอ",
            "ต้องการการยอมรับจากคนอื่น", "คิดถึงบ้านและพ่อแม่", "เหงาในคืนวันหยุด",
            "กลัวว่าพรุ่งนี้จะแย่กว่าเดิม", "ไม่กล้าบอกใครว่าไม่ไหว",
        ],
        "prompt": """คุณคือผู้เขียนสคริปต์ Shorts ภาษาไทยให้ช่อง "Farmmer — ธรรมะก่อนนอน"
กลุ่มเป้าหมาย: คนไทยที่นอนไม่หลับ เครียด คิดมากตอนกลางคืน

เขียน Shorts ใหม่ {count} คลิป เรื่อง: {angles}
(ห้ามซ้ำกับที่เขียนไปแล้ว: {done})

แต่ละคลิปเป็น JSON object:
{{"hook":"ประโยคเปิด 1 บรรทัด (ไม่เกิน 12 คำ)","lines":["...","...","...","...","...","...","...","...","..."],"cta":"ประโยคปิดชวนติดตาม 1 บรรทัด"}}

กติกา:
- lines 8-9 บรรทัด แต่ละบรรทัด 6-12 คำ รวมแล้วพูดได้ประมาณ 50-60 วินาที
- hook ต้องมี "สิ่งที่ทำได้คืนนี้" เป็นรูปธรรม เช่น ชวนทำท่านี้ เปิดคลิปทิ้งไว้ ลองหายใจแบบหนึ่ง
  ห้ามเป็นแค่การทวนปัญหาว่านอนไม่หลับ (ข้อมูลจริง: ฮุกที่บอกให้ลงมือทำได้ 1000+ วิว
  ฮุกที่แค่ทวนปัญหาได้ไม่ถึง 300)
- เนื้อหาธรรมะใช้ได้จริง มี "หนึ่งสิ่งที่ทำได้จริง" แล้วทิ้งปมให้ไปดูคลิปยาว
- ห้ามใช้เลขอารบิกหรือเลขไทย ให้เขียนเป็นคำเสมอ
- ไม่มี emoji ไม่มี markdown

ตอบเป็น JSON array เท่านั้น""",
    },
    "genx": {
        "path": os.path.join(ROOT, "content", "ch1_shorts", "scripts.json"),
        "angles": [
            "ความจริงที่คนไม่อยากยอมรับ", "ความเชื่อที่ทำให้ชีวิตติดอยู่ที่เดิม",
            "คำถามที่คนวัยผู้ใหญ่ไม่กล้าถามตัวเอง", "ความเงียบที่สอนอะไรบางอย่าง",
            "การให้อภัยตัวเอง", "ความคาดหวังของคนอื่น", "การปล่อยวางสิ่งที่คุมไม่ได้",
            "ความเหนื่อยที่ไม่มีใครเห็น", "การเริ่มต้นใหม่ตอนอายุมาก",
            "ความหมายของการมีชีวิตอยู่", "การยอมรับความไม่สมบูรณ์แบบ",
            "การไม่ต้องอธิบายตัวเองให้ทุกคนเข้าใจ", "ความกลัวที่ซ่อนอยู่หลังความโกรธ",
            "บทเรียนจากความล้มเหลว", "การอยู่กับปัจจุบัน",
            "การยอมรับว่าตัวเองก็เหนื่อย", "ความสัมพันธ์ที่ต้องปล่อยไป",
            "การไม่เปรียบเทียบตัวเองกับคนอื่น", "ความสำเร็จที่ไม่ได้ทำให้มีความสุข",
            "การดูแลตัวเองก่อนดูแลคนอื่น", "การขอโทษตัวเอง",
            "ความกล้าที่จะปฏิเสธ", "การอยู่คนเดียวอย่างมีความสุข",
            "การยอมรับความแก่มากขึ้น", "ความหมายของการให้อภัยคนที่ทำร้ายเรา",
            "การไม่ต้องพิสูจน์ตัวเอง", "ความสงบที่หาได้ในใจ",
            "การปล่อยความโกรธ", "การยอมรับสิ่งที่เปลี่ยนแปลงไม่ได้",
            "การเห็นคุณค่าในสิ่งเล็ก ๆ", "ความกล้าที่จะเริ่มใหม่",
            "การไม่จมอยู่กับอดีต", "ความสุขที่ไม่ต้องรอใคร",
        ],
        "prompt": """คุณคือผู้เขียนสคริปต์ Shorts ภาษาไทยให้ช่อง "ตาต้า GenX — ปรัชญาชีวิต"
กลุ่มเป้าหมาย: คนไทยวัยผู้ใหญ่ (Gen X) ที่เหนื่อยกับชีวิต คิดมาก กำลังหาความหมาย

เขียน Shorts ใหม่ {count} คลิป เรื่อง: {angles}
(ห้ามซ้ำกับที่เขียนไปแล้ว: {done})

แต่ละคลิปเป็น JSON object:
{{"hook":"ประโยคเปิด 1 บรรทัด เป็นความจริงที่คนอ่านแล้วสะดุด (ไม่เกิน 12 คำ)","lines":["...","...","...","...","...","...","...","...","..."],"cta":"ประโยคปิดชวนติดตาม 1 บรรทัด"}}

กติกา:
- lines 8-9 บรรทัด แต่ละบรรทัด 6-12 คำ รวมแล้วพูดได้ประมาณ 50-60 วินาที
- hook ต้องเป็นความจริงที่ท้าทายความเชื่อเดิมของคนวัยผู้ใหญ่ ไม่ใช่คำคมลอย ๆ
- เนื้อหาต้องมี "สิ่งที่ทำได้จริง" หนึ่งอย่าง และทิ้งปมให้อยากรู้ต่อ
- โทนเสียงสงบ จริงใจ ไม่เทศนา ไม่ตัดสิน
- ห้ามใช้เลขอารบิกหรือเลขไทย ให้เขียนเป็นคำเสมอ
- ไม่มี emoji ไม่มี markdown

ตอบเป็น JSON array เท่านั้น""",
    },
}

ANGLES = CHANNELS["dharma"]["angles"]
PROMPT = CHANNELS["dharma"]["prompt"]
SCRIPTS = CHANNELS["dharma"]["path"]


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


def _overlaps(angle: str, text: str, floor: int = 3) -> bool:
    """True if a run of `floor`+ characters from the angle already appears in text.

    Thai is written without spaces, so a word list is the wrong tool; a shared
    3-character run is enough to call two subjects the same.
    """
    a = re.sub(r"\s+", "", angle)
    t = re.sub(r"\s+", "", text)
    return any(a[i:i + floor] in t for i in range(len(a) - floor + 1))


def ask_angles(key: str, channel: str, seen: str, want: int) -> list[str]:
    """Ask Gemini for new one-line subjects when the curated list is used up.

    Without this the pool starves the moment every curated angle is taken: the
    dharma list was fully used by 2026-11-03 and the generator would have had
    nothing to write about.
    """
    who = {"dharma": "คนไทยที่นอนไม่หลับ เครียด คิดมากตอนกลางคืน",
           "genx": "คนไทยวัยผู้ใหญ่ (Gen X) ที่เหนื่อยกับชีวิตและกำลังหาความหมาย"}[channel]
    prompt = (f"กลุ่มเป้าหมาย: {who}\n"
              f"เสนอหัวข้อ Shorts ใหม่ {want} หัวข้อ ที่ยังไม่ซ้ำกับหัวข้อที่ใช้แล้ว\n"
              f"หัวข้อที่ใช้แล้ว (ห้ามซ้ำ): {seen[-2000:]}\n"
              "แต่ละหัวข้อเป็นวลีสั้น 4-10 คำ เกี่ยวกับชีวิต ความคิด ความรู้สึก\n"
              "ตอบเป็น JSON array ของสตริงเท่านั้น")
    out = ask(key, prompt)
    return [x for x in out if isinstance(x, str) and x.strip()]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", default="dharma", choices=list(CHANNELS))
    ap.add_argument("--count", type=int, default=6)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    cfg = CHANNELS[args.channel]
    scripts_path = cfg["path"]
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        sys.exit("GEMINI_API_KEY is not set")

    existing = []
    if os.path.exists(scripts_path):
        with open(scripts_path, encoding="utf-8") as fh:
            existing = json.load(fh)
    done = [s["hook"] for s in existing]
    # An angle was compared to a hook, which never matches, so the same subjects
    # came back every call (measured 2026-11-03: five of the dharma hooks were the
    # work-tomorrow angle). Thai has no word spaces, so compare character bigrams.
    seen = " ".join(done)
    angles = [a for a in cfg["angles"] if not _overlaps(a, seen)]
    if not angles:
        # Every curated subject is used; ask for more rather than repeat them.
        angles = ask_angles(key, args.channel, seen, max(args.count, 8))
        print(f"  curated angles exhausted; Gemini proposed {len(angles)} new ones")
    if not angles:
        sys.exit("no fresh angles available and Gemini returned none")

    fresh = ask(key, cfg["prompt"].format(count=args.count, angles=", ".join(angles[:args.count + 4]),
                                          done="; ".join(done[-12:]) or "ไม่มี"))
    fresh = [s for s in fresh if valid(s)]

    next_id = max([int(s["id"]) for s in existing] + [0]) + 1
    added = []
    for s in fresh[:args.count]:
        sid = f"{next_id:02d}"
        next_id += 1
        added.append({"id": sid, "hook": s["hook"], "lines": s["lines"], "cta": s["cta"]})

    print(f"{args.channel}: {len(existing)} existing, {len(added)} new")
    for s in added:
        print(f"  {s['id']}: {s['hook']}")
    if args.dry_run or not added:
        return 0
    os.makedirs(os.path.dirname(scripts_path), exist_ok=True)
    with open(scripts_path, "w", encoding="utf-8") as fh:
        json.dump(existing + added, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
