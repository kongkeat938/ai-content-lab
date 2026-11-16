#!/usr/bin/env python3
"""Generate a general-knowledge content set for the ch4 long-form rail.

Why the genre changed (measured, 2026-11-11): ch4's family-moment long-form
measured 0.7 long-form watch-hours in 28 days -- 0.2% of the YPP bar and the
worst on the fleet. A five-advisor panel (scripts/advise.py, run three times)
ranked the owner's three candidate genres and general knowledge won on votes; a
live YouTube Data API pull (region TH) confirmed the demand side -- the genre's
top-10 long-form median was 3.2M views, and its recent-60-day median was 7.5k
with five distinct channels, i.e. room for a new entrant. Food was rejected on
*feasibility*, not demand: its visuals need real cooking footage, which a
CPU-only runner cannot produce.

So each piece is a "why" question answered as a short story, not a list of
facts -- the panel's second finding was that a bare fact list reads as filler
and bleeds retention. Pieces keep the same gates as the other generators (Thai
only, no digits, no emoji) and the `NN_name.txt` layout, so `build_night.py`
picks the set up unchanged.

    python3 scripts/gen_knowledge_scripts.py --theme "ทำไมร่างกายเราทำแบบนี้" \
        --out content/ch4_know_01 --count 12
    python3 scripts/gen_knowledge_scripts.py --theme "..." --dry-run

Needs GEMINI_API_KEY. Free tier; the lite models answer on this key.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

MODELS = ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-3-flash-preview"]

# How many times to re-ask for a piece that fails a gate before dropping it. A
# single re-ask is enough: the failures are transient (a short or over-long
# answer), not a systematically unanswerable question.
GATE_TRIES = 3

# One question per piece, walking from the everyday outward, so the set has an
# arc instead of twelve unrelated trivia cards. Each entry is (name, the question
# the piece must answer, the angle that keeps it a story rather than a list).
ARC = [
    ("sky", "ทำไมท้องฟ้าจึงเป็นสีฟ้า", "พาไปยืนมองฟ้า แล้วค่อยเฉลยว่ามันเกี่ยวกับแสง"),
    ("sea", "ทำไมน้ำทะเลจึงเค็ม", "เล่าเป็นเรื่องราวของฝนและหินที่กินเวลานับล้านปี"),
    ("yawn", "ทำไมเราจึงหาวตามคนอื่น", "เริ่มจากวันที่เราหาวในที่ประชุมโดยไม่ตั้งใจ"),
    ("cat", "ทำไมแมวจึงชอบกล่อง", "เล่าจากมุมของแมวที่กำลังหาที่ปลอดภัย"),
    ("finger", "ทำไมนิ้วจึงย่นเมื่อแช่น้ำนาน", "เริ่มจากตอนอาบน้ำแล้วมองมือตัวเอง"),
    ("thunder", "ทำไมเราเห็นฟ้าแลบก่อนได้ยินเสียงฟ้าร้อง", "เล่าเป็นประสบการณ์ในคืนฝนตก"),
    ("bird", "ทำไมนกจึงบินเป็นตัววี", "พาไปนั่งดูฝูงนกบนท้องฟ้ายามเย็น"),
    ("moon", "ทำไมเราจึงเห็นดวงจันทร์บางวันก็เต็มบางวันก็เว้า", "เล่าจากการนอนดูพระจันทร์ตอนเด็ก"),
    ("honey", "ทำไมน้ำผึ้งจึงไม่เสียแม้ทิ้งไว้นาน", "เริ่มจากขวดน้ำผึ้งในตู้ที่ลืมไว้นาน"),
    ("ice", "ทำไมน้ำแข็งจึงลอยน้ำได้", "เล่าจากการหย่อนน้ำแข็งลงแก้วแล้วสังเกต"),
    ("echo", "ทำไมเราจึงได้ยินเสียงสะท้อนในที่โล่ง", "พาไปตะโกนในหุบเขาหรือห้องโถงใหญ่"),
    ("sleep", "ทำไมเราจึงฝัน", "เริ่มจากความฝันแปลก ๆ ที่เราจำได้ตอนตื่น"),
    ("salt", "ทำไมเกลือจึงละลายน้ำได้แต่ทรายไม่ละลาย", "เล่าจากการทำอาหารในครัว"),
    ("rainbow", "ทำไมรุ้งจึงมีเจ็ดสี", "พาไปยืนมองรุ้งหลังฝนหยุดตก"),
]

_FOREIGN = re.compile(
    r"[^\u0e00-\u0e7f\s.,!?%\-–—:;()\u2018\u2019\u201c\u201d\u2026/]")


def prompt_for(theme: str, name: str, question: str, angle: str) -> str:
    return f"""คุณคือนักเล่าเรื่องความรู้รอบตัวภาษาไทย ให้ช่อง "เกร็ดความรู้รอบตัว"
กลุ่มเป้าหมาย: คนไทยทั่วไปที่อยากรู้เรื่องน่ารอบตัวแบบเข้าใจง่าย

ธีมของชุดนี้: "{theme}"
ท่อนนี้ต้องตอบคำถาม: {question}
แนวทางเล่า: {angle}

เขียนเป็นเรื่องเล่าความรู้ 1 เรื่อง ความยาว 8-12 บรรทัด บรรทัดละหนึ่งประโยคสั้น ๆ
โทน: เล่าเหมือนเพื่อนคุยกัน เริ่มจากภาพในชีวิตประจำวัน แล้วค่อย ๆ เปิดคำตอบ
ให้ความรู้ที่ถูกต้องจริง อธิบายกลไกหรือเหตุผลด้วยภาษาง่าย ๆ ที่คนทั่วไปเข้าใจ
ห้ามเป็นรายการหัวข้อ ให้เป็นเนื้อเรื่องที่ไหลต่อเนื่อง
ปิดท้ายด้วยประโยคที่ทำให้ผู้อ่านรู้สึกว่า "เพิ่งได้เรียนรู้อะไรใหม่"

กติกาเด็ดขาด:
- ห้ามใช้เลขอารบิกหรือเลขไทย ให้เขียนจำนวนเป็นคำเสมอ (เช่น เจ็ด ไม่ใช่ 7)
- ไม่มี emoji ไม่มี markdown ไม่มีหัวข้อ ไม่มีเครื่องหมายคำพูดครอบ
- ภาษาไทยล้วน ห้ามมีคำอังกฤษปน (ยกเว้นคำที่คนไทยใช้จริงแต่ให้เขียนทับศัพท์ไทย)
- ข้อมูลต้องถูกต้องตามหลักวิทยาศาสตร์ ไม่แต่งเรื่องเกินจริง
- ตอบเป็นเรื่องเล่าเท่านั้น ไม่ต้องมีคำอธิบาย"""


def ask(key: str, prompt: str) -> str:
    body = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode()
    last = "no model answered"
    for model in MODELS:
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"{model}:generateContent?key={key}")
        req = urllib.request.Request(url, data=body,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=120) as fh:
                return json.load(fh)["candidates"][0]["content"]["parts"][0]["text"].strip()
        except urllib.error.HTTPError as e:
            last = f"{model} HTTP {e.code}"
        except Exception as e:  # noqa: BLE001
            last = f"{model} {type(e).__name__}"
        time.sleep(2)
    raise RuntimeError(last)


def valid(text: str) -> tuple:
    """(ok, reason). Same gates as the other generators: Thai only, no digits."""
    if not text:
        return False, "empty"
    if re.search(r"[0-9๐-๙]", text):
        return False, "has digits"
    if _FOREIGN.search(text):
        return False, "foreign script"
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) < 6:
        return False, f"too short ({len(lines)} lines)"
    if len(lines) > 16:
        return False, f"too long ({len(lines)} lines)"
    return True, "ok"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--theme", required=True, help="the set's theme, in Thai")
    ap.add_argument("--out", required=True, help="output directory (content/ch4_know_XX)")
    ap.add_argument("--count", type=int, default=len(ARC),
                    help=f"how many pieces (default {len(ARC)})")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    key = (os.environ.get("GEMINI_API_KEY") or "").strip()
    if not key:
        raise SystemExit("Set GEMINI_API_KEY.")

    beats = ARC[:a.count]
    pieces, skipped = [], []
    for i, (name, question, angle) in enumerate(beats, 1):
        # A piece that fails a gate is retried, not dropped on the first try: the
        # gate rejects a transient short/long answer (measured 2026-11-16: one
        # 3-line "sea" answer blocked all 12 pieces), and a retry has a real
        # chance of passing. The set is still refused if it never passes -- this
        # retries the piece, it does not accept a partial set.
        text, ok, reason = "", False, "no attempt"
        for attempt in range(GATE_TRIES):
            text = ask(key, prompt_for(a.theme, name, question, angle))
            ok, reason = valid(text)
            if ok:
                break
            if attempt + 1 < GATE_TRIES:
                print(f"  {i:02d}_{name}: {reason}; retry "
                      f"{attempt + 1}/{GATE_TRIES - 1}", flush=True)
                time.sleep(3)
        if not ok:
            skipped.append((name, reason))
            print(f"  {i:02d}_{name}: SKIP ({reason})", flush=True)
            continue
        pieces.append((f"{i:02d}_{name}", text))
        n = len([ln for ln in text.splitlines() if ln.strip()])
        print(f"  {i:02d}_{name}: {n} lines", flush=True)

    if a.dry_run:
        for name, text in pieces:
            print(f"\n===== {name} =====\n{text}")
        return 0

    # A generator that can drop a piece must FAIL, not write a partial set: a set
    # short of --count would silently shorten the long-form below its floor.
    if len(pieces) < a.count:
        print(f"only {len(pieces)}/{a.count} pieces passed the gates "
              f"(skipped {skipped}); refusing to write a partial set",
              file=sys.stderr)
        return 1

    os.makedirs(a.out, exist_ok=True)
    for name, text in pieces:
        with open(os.path.join(a.out, name + ".txt"), "w", encoding="utf-8") as fh:
            fh.write(text.rstrip() + "\n")
    print(f"wrote {len(pieces)} pieces to {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
