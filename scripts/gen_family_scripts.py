#!/usr/bin/env python3
"""Generate a fresh family-story content set for the ch4 long-form rail.

The dharma rail has `gen_night_scripts.py` to feed it; the ch4 rail
(`ch4-longform.yml`, the เรื่องเล่าอบอุ่นใจ family-moment channel) had none, so its
content was written by hand and the rail only ran when someone remembered. This
writes a set in the shape the channel's audience actually watches -- measured
2026-11-05: the family-moment Shorts did 460-1,083 views while the classical
tales did 1-6, so the pieces are warm, concrete, first-person memories, not
folklore.

Same gates as the Shorts pool (Thai only, no digits, no emoji), same
`NN_name.txt` layout, so `build_night.py` picks the set up unchanged.

    python3 scripts/gen_family_scripts.py --theme "ความรักของแม่" \
        --out content/ch4_family_02 --count 10
    python3 scripts/gen_family_scripts.py --theme "..." --dry-run

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

# The beats a family-moment set walks through, one piece each: a memory that
# opens, then the small acts that carry the feeling, then a quiet close. The set
# is generated one piece per beat so the compilation has an arc, not ten
# variations on the same scene.
ARC = [
    ("bike", "ครั้งแรกที่พ่อ/แม่สอนอะไรบางอย่าง แล้วเรากลัวแต่เขาจับไว้"),
    ("kitchen", "อาหารเช้าที่พ่อ/แม่ตื่นทำก่อนเราเสมอ เรามักไม่ทันสังเกต"),
    ("grandma", "คืนหนึ่งที่ยาย/ตาเล่าเรื่องให้ฟัง และเราหลับคาตัก"),
    ("sibling", "พี่หรือน้องที่คอยปกป้องเราโดยไม่พูด"),
    ("broken", "ของเล่นหรือของรักที่พัง แล้วพ่อ/แม่ซ่อมให้เงียบ ๆ"),
    ("rain", "วันที่ฝนตก เราเห็นคนในบ้านวิ่งมารับ"),
    ("garden", "สวนหรือกิจกรรมที่ตา/ยายสอนให้เรารู้จักความอดทน"),
    ("homework", "การบ้านที่เราทำไม่ได้ แล้วมีคนนั่งเป็นเพื่อนจนเข้าใจ"),
    ("mistake", "วันที่เราทำผิด กลัวถูกดุ แต่กลับได้กอด"),
    ("growup", "วันที่เรารู้ว่าพ่อ/แม่แก่ลง และเราอยากดูแลท่านตอบ"),
    ("letter", "ข้อความหรือคำพูดสั้น ๆ ของพ่อ/แม่ที่เราจำได้จนวันนี้"),
    ("home", "วันที่เรากลับบ้าน และรู้ว่าบ้านคือที่ที่ยังมีคนรอ"),
]

_FOREIGN = re.compile(
    r"[^\u0e00-\u0e7fA-Za-z0-9\s.,!?%\-–—:;()\u2018\u2019\u201c\u201d\u2026/&']")


def prompt_for(theme: str, beat: str, want: str) -> str:
    return f"""คุณคือนักเขียนเรื่องเล่าสั้นภาษาไทย ให้ช่อง "เรื่องเล่าอบอุ่นใจ"
กลุ่มเป้าหมาย: คนไทยวัยทำงาน ที่คิดถึงบ้านและครอบครัว

ธีมของชุดนี้: "{theme}"
ท่อนนี้รับผิดชอบฉาก: {beat} ({want})

เขียนเรื่องเล่าสั้น 1 เรื่อง เล่าเป็นความเรียงจากมุมมอง "ผม" หรือ "ฉัน"
รูปแบบ: บรรทัดละหนึ่งประโยคสั้น ๆ ความยาว 8-12 บรรทัด
โทน: อบอุ่น จริงใจ เห็นภาพชัด มีรายละเอียดเล็ก ๆ ที่คนอ่าน "เออ เหมือนบ้านเราเลย"
ต้องมีหักมุมเล็ก ๆ หรือประโยคปิดที่ทำให้ใจอุ่น (ไม่ต้องเศร้าเกินไป)
จบด้วยประโยคที่ทิ้งความรู้สึกอบอุ่นไว้

กติกาเด็ดขาด:
- ห้ามใช้เลขอารบิกหรือเลขไทย ให้เขียนเป็นคำเสมอ
- ไม่มี emoji ไม่มี markdown ไม่มีหัวข้อ ไม่มีเครื่องหมายคำพูดครอบ
- ภาษาไทยล้วน ห้ามมีคำอังกฤษปน (ยกเว้นคำที่คนไทยใช้จริงแต่ให้เขียนทับศัพท์ไทย)
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
    """(ok, reason). The same gates the Shorts pool uses: Thai only, no digits."""
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
    ap.add_argument("--out", required=True, help="output directory (content/ch4_family_XX)")
    ap.add_argument("--count", type=int, default=len(ARC),
                    help=f"how many pieces (default {len(ARC)}, one per beat)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    key = (os.environ.get("GEMINI_API_KEY") or "").strip()
    if not key:
        raise SystemExit("Set GEMINI_API_KEY.")

    beats = ARC[:a.count]
    pieces, skipped = [], []
    for i, (name, want) in enumerate(beats, 1):
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
