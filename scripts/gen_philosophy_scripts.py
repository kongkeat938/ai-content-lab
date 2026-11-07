#!/usr/bin/env python3
"""Generate a fresh GenX life-philosophy content set for the genx long-form rail.

The dharma rail has `gen_night_scripts.py` and the ch4 rail has
`gen_family_scripts.py`; genx -- the channel with the most Shorts (52) and the
highest Shorts reach -- had no long-form at all, so every one of its Shorts
pointed its funnel at an empty playlist (measured 2026-11-07). This writes the
content set that fills it.

The advisor panel (2026-11-07) agreed genx is the biggest gap: 68.3 watch-hours
from Shorts alone, 0 from long-form, and the YPP threshold counts only long-form
watch-hours. The panel disagreed on length; the set is length-agnostic (a piece
is a piece), so this can feed a 30-minute trial or a longer file without change.

Same gates as the Shorts pool (Thai only, no digits, no emoji), same
`NN_name.txt` layout, so `build_night.py` picks the set up unchanged.

    python3 scripts/gen_philosophy_scripts.py --theme "ให้สิทธิ์ตัวเองได้พัก" \
        --out content/ch1_long_01 --count 10
    python3 scripts/gen_philosophy_scripts.py --theme "..." --dry-run

Needs GEMINI_API_KEY. Free tier; gemini-3.5-flash-lite answers on this key.
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

# The beats a GenX life-philosophy set walks through, one piece each: the same
# "permission" arc the channel's winning Shorts use (hooks that grant permission
# measured 310-373 views/day vs. lower for problem-restating hooks). A set walks
# from giving permission, through releasing what was carried, to a quiet close.
ARC = [
    ("permission", "ให้สิทธิ์ตัวเองได้พัก โดยไม่ต้องขอโทษใคร"),
    ("enough", "พอแล้วกับสิ่งที่ทำมาทั้งชีวิต ไม่ต้องพิสูจน์อะไรอีก"),
    ("others", "ปล่อยความคาดหวังของคนอื่นที่แบกมานาน"),
    ("compare", "เลิกเปรียบเทียบชีวิตตัวเองกับคนอื่น"),
    ("forgive", "ให้อภัยความผิดพลาดในอดีตของตัวเอง"),
    ("anger", "วางความโกรธที่เก็บไว้ข้างในลง"),
    ("alone", "อยู่คนเดียวได้อย่างสงบ ไม่ต้องกลัวความเหงา"),
    ("body", "ฟังร่างกายที่เหนื่อยมากับเรามาทั้งชีวิต"),
    ("present", "กลับมาอยู่กับวันนี้ ไม่จมกับอดีตหรือกลัวอนาคต"),
    ("kindness", "ใจดีกับตัวเองก่อนจะใจดีกับคนอื่น"),
    ("meaning", "ความหมายของชีวิตไม่ได้อยู่ที่ความสำเร็จ"),
    ("rest", "อนุญาตให้ตัวเองพักผ่อนอย่างเต็มที่"),
]

_FOREIGN = re.compile(
    r"[^\u0e00-\u0e7fA-Za-z0-9\s.,!?%\-–—:;()\u2018\u2019\u201c\u201d\u2026/&']")


def prompt_for(theme: str, beat: str, want: str) -> str:
    return f"""คุณคือนักเขียนบทบรรยายภาษาไทย ให้ช่อง "ตาต้า GenX — ปรัชญาชีวิต"
กลุ่มเป้าหมาย: คนไทยวัยผู้ใหญ่ (Gen X) ที่เหนื่อยกับชีวิต คิดมาก กำลังหาความหมาย

ธีมของชุดนี้: "{theme}"
ท่อนนี้รับผิดชอบช่วง: {beat} ({want})

เขียนบทบรรยาย 1 ท่อน รูปแบบบรรทัดละหนึ่งวลีสั้น ๆ (เหมือนกวี) เว้นบรรทัดว่างระหว่างจังหวะ
ความยาว 22-28 บรรทัด (พูดประมาณ 1.5-2 นาที)
โทน: สงบ จริงใจ ให้ "การอนุญาต" แก่ผู้ฟัง ห้ามเทศนา ห้ามตัดสิน ห้ามสั่ง
ถ้าเป็นท่อนสุดท้ายของชุด ให้ปิดอย่างอ่อนโยน ทิ้งความสบายใจไว้

กติกาเด็ดขาด:
- ห้ามใช้เลขอารบิกหรือเลขไทย ให้เขียนเป็นคำเสมอ
- ไม่มี emoji ไม่มี markdown ไม่มีหัวข้อ ไม่มีเครื่องหมายคำพูดครอบ
- ภาษาไทยล้วน ห้ามมีคำอังกฤษปน
- ตอบเป็นข้อความบรรยายเท่านั้น ไม่ต้องมีคำอธิบาย"""


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
    """(ok, reason). The same gates the Shorts pool uses: Thai only, no digits."""
    if not text:
        return False, "empty"
    if re.search(r"[0-9๐-๙]", text):
        return False, "has digits"
    if _FOREIGN.search(text):
        return False, "foreign script"
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) < 12:
        return False, f"too short ({len(lines)} lines)"
    if len(lines) > 40:
        return False, f"too long ({len(lines)} lines)"
    return True, "ok"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--theme", required=True, help="the set's theme, in Thai")
    ap.add_argument("--out", required=True, help="output directory (content/ch1_long_XX)")
    ap.add_argument("--count", type=int, default=len(ARC),
                    help=f"how many pieces (default {len(ARC)}, one per arc stage)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    key = (os.environ.get("GEMINI_API_KEY") or "").strip()
    if not key:
        raise SystemExit("Set GEMINI_API_KEY.")

    stages = ARC[:a.count]
    pieces, skipped = [], []
    for i, (name, want) in enumerate(stages, 1):
        text = ask(key, prompt_for(a.theme, name, want))
        ok, reason = valid(text)
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

    os.makedirs(a.out, exist_ok=True)
    for name, text in pieces:
        with open(os.path.join(a.out, name + ".txt"), "w", encoding="utf-8") as fh:
            fh.write(text.rstrip() + "\n")
    print(f"wrote {len(pieces)} pieces to {a.out}"
          + (f" (skipped {len(skipped)})" if skipped else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
