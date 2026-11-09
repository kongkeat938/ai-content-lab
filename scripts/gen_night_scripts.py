#!/usr/bin/env python3
"""Generate a fresh dharma-before-sleep content set for the long-form rail.

The advisor panel's lever #1 is more 2-4 hour loopable long-form on the dharma
channel. `build_night.py` turns a directory of numbered `.txt` pieces into one
verified compilation, but the rail is only as good as the pieces it is handed,
and hand-writing a new set every week does not scale. This writes one.

It asks the free Gemini text model for a set of short narrated pieces on a theme,
keeps the ones that pass the same shape checks the Shorts generator uses (Thai
only, no digits, no emoji), and writes them as `NN_name.txt` so `build_night.py`
picks them up unchanged.

    python3 scripts/gen_night_scripts.py --theme "ปล่อยวางความกังวลเรื่องเงิน" \
        --out content/night_dharma_02 --count 8
    python3 scripts/gen_night_scripts.py --theme "..." --dry-run

Needs GEMINI_API_KEY. Free tier; gemini-3.5-flash-lite is the model that answers
on this key (measured 2026-11-05).
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

# Free-tier models come and go; the first that answers wins.
MODELS = ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-3-flash-preview"]

# The angles a sleep set walks through, in the order a listener should hear them:
# settle the body, release what was carried, then hand the mind to sleep. A set
# is generated one piece per angle so the compilation has a real arc rather than
# eight variations on the same thought.
ARC = [
    ("open", "เปิดคืนนี้แบบเจาะจง: เรียกคนที่นอนไม่หลับ แล้วชวนทำสิ่งที่ลงมือได้ทันที "
             "(วางมือบนท้อง หายใจเข้าลึก ๆ แล้วปล่อยยาว) ก่อนค่อย ๆ ผ่อนคลาย"),
    ("body", "ผ่อนคลายร่างกายทีละส่วน ตั้งแต่ศีรษะถึงปลายเท้า"),
    ("breath", "ตามดูลมหายใจ ไม่บังคับ แค่รู้ตัวว่าหายใจ"),
    ("letgo", "วางสิ่งที่ถือมาทั้งวัน ความกังวลและความผิดหวัง"),
    ("forgive", "ให้อภัยตัวเองในเรื่องที่ยังค้างใจ"),
    ("gratitude", "ขอบคุณสิ่งเล็ก ๆ ที่มีในวันนี้"),
    ("impermanence", "ทุกอย่างผ่านไป ไม่มีอะไรต้องยึดไว้"),
    ("metta", "ส่งความปรารถนาดีให้ตัวเอง แล้วค่อยแผ่ไปให้คนอื่น"),
    ("release", "ปล่อยทุกอย่างลง แล้วปล่อยให้ใจได้พัก"),
    ("sleep", "พาใจเข้านอนอย่างอ่อนโยน ปล่อยให้ง่วงได้เต็มที่"),
]

_FOREIGN = re.compile(
    r"[^\u0e00-\u0e7fA-Za-z0-9\s.,!?%\-–—:;()\u2018\u2019\u201c\u201d\u2026/&']")


def learned(channel: str) -> dict:
    """Read content/insights/<channel>.json -- the themes and rules the analytics
    loop learned. Empty on any error, so generation never depends on it existing."""
    path = os.path.join(ROOT, "content", "insights", f"{channel}.json")
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return {}


def prompt_for(theme: str, angle: str, want: str, rules: list[str] | None = None) -> str:
    rule_block = ""
    if rules:
        rule_block = ("\n\nกฎที่เรียนรู้จากคลิปยาวที่ทำผลงานดี/แย่ของช่องนี้ (ต้องทำตาม):\n- "
                      + "\n- ".join(rules))
    return f"""คุณคือผู้เขียนบทบรรยาย "ธรรมะก่อนนอน" ภาษาไทย ให้ช่อง Farmmer — ธรรมะก่อนนอน
กลุ่มเป้าหมาย: คนไทยที่นอนไม่หลับ เครียด คิดมากตอนกลางคืน

ธีมของชุดนี้: "{theme}"
ท่อนนี้รับผิดชอบช่วง: {angle} ({want}){rule_block}

เขียนบทบรรยาย 1 ท่อน รูปแบบบรรทัดละหนึ่งวลีสั้น ๆ (เหมือนกวี) เว้นบรรทัดว่างระหว่างจังหวะ
ความยาว 22-28 บรรทัด (พูดประมาณ 1.5-2 นาที)
โทน: นุ่มนวล ปลอบโยน ชวนให้ผ่อนคลาย ห้ามเทศนา ห้ามตัดสิน
ถ้าเป็นท่อนสุดท้ายของชุด ให้พาใจเข้านอนและปิดอย่างอ่อนโยน

กติกาเด็ดขาด:
- ห้ามใช้เลขอารบิกหรือเลขไทย ให้เขียนเป็นคำเสมอ
- ไม่มี emoji ไม่มี markdown ไม่มีหัวข้อ ไม่มีเครื่องหมายคำพูดครอบ
- ภาษาไทยล้วน
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
    ap.add_argument("--theme", default="", help="the set's theme, in Thai (or use --from-insights)")
    ap.add_argument("--out", required=True, help="output directory (content/night_XX)")
    ap.add_argument("--count", type=int, default=len(ARC),
                    help=f"how many pieces (default {len(ARC)}, one per arc stage)")
    ap.add_argument("--channel", default="dharma",
                    help="which insights file to learn from (dharma/ch2/...)")
    ap.add_argument("--from-insights", action="store_true",
                    help="take the theme from the analytics-learned insights if one is "
                         "available, instead of the hardcoded weekly list")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    key = (os.environ.get("GEMINI_API_KEY") or "").strip()
    if not key:
        raise SystemExit("Set GEMINI_API_KEY.")

    ins = learned(a.channel)
    rules = [r for r in ins.get("rules", []) if isinstance(r, str)][:3]
    if a.from_insights and not a.theme:
        themes = [t for t in ins.get("themes", []) if isinstance(t, str)]
        if themes:
            a.theme = themes[0]
            print(f"theme learned from {a.channel} analytics: {a.theme}")
    if not a.theme:
        raise SystemExit("no theme: pass --theme, or --from-insights with a learned theme")
    if rules:
        print(f"applying {len(rules)} rules learned from the channel's long-form review")

    stages = ARC[:a.count]
    pieces, skipped = [], []
    for i, (name, want) in enumerate(stages, 1):
        text, reason = "", "no attempt"
        # Retry: a piece that fails the shape gate must not be silently dropped.
        # Measured 2026-11-09: a set shipped without its 01_open because one
        # response tripped the gate and was skipped -- the cold open is the exact
        # lever the decision named, so a silent drop disarms the fix.
        for attempt in range(3):
            cand = ask(key, prompt_for(a.theme, name, want, rules))
            ok, reason = valid(cand)
            if ok:
                text = cand
                break
            time.sleep(2)
        if not text:
            skipped.append((name, reason))
            print(f"  {i:02d}_{name}: SKIP after 3 tries ({reason})", flush=True)
            continue
        pieces.append((f"{i:02d}_{name}", text))
        n = len([ln for ln in text.splitlines() if ln.strip()])
        print(f"  {i:02d}_{name}: {n} lines", flush=True)

    if a.dry_run:
        for name, text in pieces:
            print(f"\n===== {name} =====\n{text}")
        return 0

    # A set missing its opening (or any stage) would build a shorter talk than the
    # arc intends and, under a --minutes floor, get looped twice. Fail loudly
    # instead of writing a partial set -- the caller can regenerate.
    missing = [name for name, _ in stages if name not in {n.split("_", 1)[1] for n, _ in pieces}]
    if missing:
        raise SystemExit(
            f"could not generate {missing} after retries; refusing to write a "
            f"partial set to {a.out} (skipped: {skipped})")

    os.makedirs(a.out, exist_ok=True)
    for name, text in pieces:
        with open(os.path.join(a.out, name + ".txt"), "w", encoding="utf-8") as fh:
            fh.write(text.rstrip() + "\n")
    print(f"wrote {len(pieces)} pieces to {a.out}"
          + (f" (skipped {len(skipped)})" if skipped else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
