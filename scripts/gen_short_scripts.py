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
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
# Free-tier models come and go; the first that answers wins. Measured 2026-11-04:
# gemini-3.5-flash-lite intermittently 503s, gemini-3.1-flash-lite answered.
MODELS = ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-3-flash-preview"]

# ch4's long-form is dead (measured 2026-11-09: 1-3 views per 120-min file), so a
# CTA that promises a "full clip" is a promise the channel cannot keep. Its Shorts
# also get the worst subs-per-1k on the fleet (1.93). An honest subscribe ask is
# the only funnel that exists, so the broken-promise shape is forbidden there.
_BROKEN_CTA = re.compile(r"คลิปเต็ม|คลิปยาว|วิดีโอตัวเต็ม|คลิปต่อ|เรื่องเต็ม|คลิปถัดไป")

# A tension marker for the hook (measured 2026-11-10). kongkeat's flat "concrete
# scene" hooks (a warm description with no pull) kept only 13.7% mid-retention and
# the Shorts feed stopped showing the channel, while genx/dharma hooks -- a
# question, a hidden truth, a loss -- held 62-68%. A hook must now carry one of
# these, not just a picture. Kept deliberately broad so it catches the shape
# (a question, a secret, a departure, a let-down) without demanding exact words.
_TENSION = re.compile(
    r"ทำไม|ทำไมถึง|หรือเปล่า|ใช่ไหม|ความลับ|ปิดบัง|ซ่อน|ไม่เคยบอก|ไม่รู้ว่า|รู้ทีหลัง|"
    r"เพิ่งรู้|เพิ่งเข้าใจ|จากไป|จากเรา|ทิ้งไว้|ไม่บอกลา|วันสุดท้าย|ครั้งสุดท้าย|"
    r"เสียใจ|ผิดหวัง|เสียสละ|ร้องไห้|น้ำตา|ไม่มี.*อีกแล้ว|ไม่เหลือ|ไม่ทัน|สายไป|"
    r"คำโกหก|คำสัญญา|ไม่กล้า|กลั้น|อดทน")

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
        # The hooks that measured best all carry one of these; valid() enforces
        # it so the pool cannot fill up with the losing shape again.
        "cues": ("ลอง", "คืนนี้", "เปิดทิ้งไว้"),
        "prompt": """คุณคือผู้เขียนสคริปต์ Shorts ภาษาไทยให้ช่อง "Farmmer — ธรรมะก่อนนอน"
กลุ่มเป้าหมาย: คนไทยที่นอนไม่หลับ เครียด คิดมากตอนกลางคืน

เขียน Shorts ใหม่ {count} คลิป เรื่อง: {angles}
(ห้ามซ้ำกับที่เขียนไปแล้ว: {done})

แต่ละคลิปเป็น JSON object:
{{"hook":"ประโยคเปิด 1 บรรทัด (ไม่เกิน 12 คำ)","lines":["...","...","...","...","...","...","...","...","..."],"cta":"ประโยคปิดชวนติดตาม 1 บรรทัด"}}

กติกา:
- lines 8-9 บรรทัด แต่ละบรรทัด 6-12 คำ รวมแล้วพูดได้ประมาณ 50-60 วินาที
- hook บังคับ: ต้องมีคำใดคำหนึ่งในนี้ "ลอง" หรือ "คืนนี้" หรือ "เปิดทิ้งไว้" และต้องบอก
  สิ่งที่ทำได้จริงคืนนี้ เช่น "คืนนี้ลองวางมือบนท้องแล้วหายใจช้า ๆ"
  ห้ามเขียนฮุกที่เป็นแค่การทวนปัญหาว่า "ทำไมนอนไม่หลับ" เด็ดขาด
  (วัดจริง: ฮุกที่บอกให้ลงมือทำได้ 300-570 วิว/วัน ฮุกที่ทวนปัญหาได้ 74-173 วิว/วัน)
- ชื่อเรื่อง (angles) เป็นแค่ "หัวข้อ" ไม่ใช่ตัวฮุก ให้เปลี่ยนหัวข้อนั้นให้เป็นคำแนะนำที่ลงมือทำได้
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
        "cues": ("มีสิทธิ์", "ไม่ต้อง", "อนุญาต"),
        "prompt": """คุณคือผู้เขียนสคริปต์ Shorts ภาษาไทยให้ช่อง "ตาต้า GenX — ปรัชญาชีวิต"
กลุ่มเป้าหมาย: คนไทยวัยผู้ใหญ่ (Gen X) ที่เหนื่อยกับชีวิต คิดมาก กำลังหาความหมาย

เขียน Shorts ใหม่ {count} คลิป เรื่อง: {angles}
(ห้ามซ้ำกับที่เขียนไปแล้ว: {done})

แต่ละคลิปเป็น JSON object:
{{"hook":"ประโยคเปิด 1 บรรทัด เป็นความจริงที่คนอ่านแล้วสะดุด (ไม่เกิน 12 คำ)","lines":["...","...","...","...","...","...","...","...","..."],"cta":"ประโยคปิดชวนติดตาม 1 บรรทัด"}}

กติกา:
- lines 8-9 บรรทัด แต่ละบรรทัด 6-12 คำ รวมแล้วพูดได้ประมาณ 50-60 วินาที
- hook บังคับ: ต้องมีคำใดคำหนึ่งในนี้ "มีสิทธิ์" หรือ "ไม่ต้อง" หรือ "อนุญาต" และต้องให้
  "ความปลดปล่อย" หรือ "การอนุญาต" แก่คนอ่าน เช่น "คุณมีสิทธิ์พักโดยไม่ต้องขอโทษใคร"
  ห้ามเขียนฮุกที่เป็นแค่การทวนความจริงเฉย ๆ เด็ดขาด
  (วัดจริง: ฮุกแบบให้สิทธิ์ได้ 310-373 วิว/วัน ฮุกแบบทวนความจริงได้ต่ำกว่ามาก)
- ชื่อเรื่อง (angles) เป็นแค่ "หัวข้อ" ไม่ใช่ตัวฮุก ให้เปลี่ยนหัวข้อนั้นให้เป็นคำอนุญาตที่ลงมือทำได้
- เนื้อหาต้องมี "สิ่งที่ทำได้จริง" หนึ่งอย่าง และทิ้งปมให้อยากรู้ต่อ
- โทนเสียงสงบ จริงใจ ไม่เทศนา ไม่ตัดสิน
- ห้ามใช้เลขอารบิกหรือเลขไทย ให้เขียนเป็นคำเสมอ
- ไม่มี emoji ไม่มี markdown

ตอบเป็น JSON array เท่านั้น""",
    },
    "kongkeat-story": {
        "path": os.path.join(ROOT, "content", "ch4_shorts", "scripts.json"),
        "angles": [
            "ความลับที่แม่ปิดบังเรื่องเงินในบ้าน", "คืนที่พ่อจากไปโดยไม่บอกลา",
            "วันที่ฉันเข้าใจความเสียสละของแม่ที่สายไป", "ความจริงที่ยายเพิ่งเล่าในวันสุดท้าย",
            "คำพูดของพ่อที่ฉันเพิ่งเข้าใจตอนท่านไม่อยู่แล้ว", "วันที่พี่สาวเลือกครอบครัวแทนความฝัน",
            "ความผิดหวังที่ซ่อนอยู่ใต้รอยยิ้มของแม่", "จดหมายที่พ่อทิ้งไว้ก่อนจากไป",
            "ทำไมคนที่เสียสละให้บ้านมากที่สุด ถึงถูกมองข้ามเสมอ", "ความเงียบในมื้อเย็นที่ไม่มีพ่อ",
            "วันสุดท้ายที่ฉันได้กอดยาย", "เรื่องที่แม่ไม่เคยบอกใครเรื่องงานของพ่อ",
            "ตอนที่ฉันรู้ว่าบ้านไม่เหลืออะไรแล้ว", "รอยยิ้มของแม่ที่กลบความเหนื่อยทั้งชีวิต",
            "คำขอร้องสุดท้ายของพ่อที่ฉันยังไม่ได้ทำ", "วันที่พี่ชายต้องเลือกระหว่างฉันกับอนาคตตัวเอง",
            "ความจริงในกล่องไม้เก่าของตา", "ตอนที่แม่ร้องไห้คนเดียวในครัว",
            "ทำไมเราถึงรู้ค่าของคนที่จากไปแล้วเสมอ", "คำโกหกครั้งสุดท้ายที่พ่อบอกเพื่อปกป้องฉัน",
        ],
        "cues": ("พ่อ", "แม่", "พี่", "ยาย", "ตา", "ป้า", "น้า", "ลูก"),
        # The measured hook floor for this channel. Measured 2026-11-10: the flat
        # "concrete scene" hooks (the old rule) kept only 13.7% mid-retention vs
        # genx 62% / dharma 68%, and the feed stopped showing the channel. A hook
        # must now carry a tension marker (a question, a hidden truth, a loss, a
        # let-down), not just a warm description. Enforced in valid(), so a draft
        # cannot drift back to the flat shape.
        "require": _TENSION,
        # The channel has no reachable long-form (its 120-min files get 1-3 views),
        # so a "go watch the full clip" CTA sends viewers to a dead end. Enforced by
        # valid(), not just asked for in the prompt.
        "forbid_cta": _BROKEN_CTA,
        "prompt": """คุณคือผู้เขียนสคริปต์ Shorts ภาษาไทยให้ช่อง "เรื่องเล่าอบอุ่นใจ"
กลุ่มเป้าหมาย: คนไทยที่ชอบเรื่องเล่าอบอุ่นใจเกี่ยวกับครอบครัว

เขียน Shorts ใหม่ {count} คลิป เรื่อง: {angles}
(ห้ามซ้ำกับที่เขียนไปแล้ว: {done})

แต่ละคลิปเป็น JSON object:
{{"hook":"ประโยคเปิด 1 บรรทัด (ไม่เกิน 12 คำ)","lines":["...","...","...","...","...","...","...","...","..."],"cta":"ประโยคปิดชวนติดตาม 1 บรรทัด"}}

กติกา:
- lines 8-9 บรรทัด แต่ละบรรทัด 6-12 คำ รวมแล้วพูดได้ประมาณ 50-60 วินาที
- hook บังคับ: ต้องเปิดด้วย "ปมตึง" ในครอบครัว ภายใน 12 คำแรก มีคำเรียกความสัมพันธ์
  (พ่อ/แม่/พี่/ยาย/ตา) และต้องมีปมอย่างน้อยหนึ่งอย่าง: เป็นคำถาม (ทำไม...), ความลับที่ถูกปิดบัง,
  การจากลา/การสูญเสีย, หรือความผิดหวัง/ความเสียใจ
  ตัวอย่างที่ดี: "ทำไมลูกที่เสียสละให้บ้านมากที่สุด ถึงเป็นคนที่พ่อแม่เกรงใจน้อยที่สุด"
                "พ่อพับนกกระดาษทิ้งไว้ ก่อนจะจากเราไปโดยไม่บอกลาสักคำ"
  ห้ามเขียนฮุกที่เป็นแค่การบรรยายฉากอบอุ่นราบเรียบ เช่น "บ่ายวันเสาร์พ่อจูงมือไปพับนกกระดาษ"
  (วัดจริง 2026-11-10: ฮุกบรรยายฉากได้ opening 104% แต่ดูต่อกลางเรื่องเพียง 13.7%;
   ฮุกที่มีปมตึงของช่องอื่นได้กลางเรื่อง 62-68%)
- โครงเรื่อง: เปิดด้วยปม/คำถาม -> เผยความจริงทีละนิด -> เฉลยอบอุ่นกินใจตอนจบ (หักมุมได้)
- เรื่องสั้นจบในคลิปเดียว จุดจบอบอุ่น กินใจ ไม่เทศนา
- cta: ชวนติดตามอย่างเดียว ห้ามสัญญาว่า "มีคลิปเต็ม/คลิปยาว/วิดีโอตัวเต็ม/ไปดูต่อ"
  เพราะช่องนี้ยังไม่มีคลิปยาวที่คนดูถึง ให้เขียนแบบ "กดติดตามเพื่อรับเรื่องอบอุ่นใจแบบนี้ทุกวัน"
- ห้ามใช้เลขอารบิกหรือเลขไทย ให้เขียนเป็นคำเสมอ
- ไม่มี emoji ไม่มี markdown

ตอบเป็น JSON array เท่านั้น""",
    },
}

ANGLES = CHANNELS["dharma"]["angles"]
PROMPT = CHANNELS["dharma"]["prompt"]
SCRIPTS = CHANNELS["dharma"]["path"]


def ask(key: str, prompt: str) -> list:
    body = json.dumps({"contents": [{"parts": [{"text": prompt}]}],
                       "generationConfig": {"responseMimeType": "application/json"}}).encode()
    last = "no model answered"
    for model in MODELS:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=120) as fh:
                txt = json.load(fh)["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(txt)
        except urllib.error.HTTPError as e:
            last = f"{model} HTTP {e.code}"
        except Exception as e:  # noqa: BLE001
            last = f"{model} {type(e).__name__}"
        time.sleep(2)
    raise RuntimeError(last)


# Letters outside Thai and Latin mean the model leaked another script (measured
# 2026-11-05: a ch4 hook came back with a Hangul syllable, a ch2 line with Telugu).
# edge-tts reads those as noise, so they must never reach the pool. Latin is kept
# because the channel names (GenX, Farmmer) legitimately appear in the copy.
_FOREIGN = re.compile(
    r"[^\u0e00-\u0e7fA-Za-z0-9\s.,!?%\-–—:;()\u2018\u2019\u201c\u201d\u2026/&']")

# Sermon phrasing the panel flagged: a Short must tell the story, not lecture.
# Measured 2026-11-07: the graded-D video's weak line was "หนึ่งสิ่งที่ทำได้จริงคือ...",
# and a scan found the pattern in 58 of 215 scripts across the three channels.
_PREACHY = re.compile(
    r"หนึ่งสิ่งที่ทำได้|สิ่งที่ทำได้คือ|ข้อคิด|จำไว้ว่า|จง |อย่าลืมว่า|สอนให้รู้ว่า|"
    r"สิ่งสำคัญคือ|บทเรียนที่ได้|ข้อเตือนใจ")


def valid(s: dict, cues=(), forbid=None, require=None) -> bool:
    if not isinstance(s, dict):
        return False
    if not s.get("hook") or not isinstance(s.get("lines"), list) or not s.get("cta"):
        return False
    if len(s["lines"]) < 3:
        return False
    joined = " ".join([s["hook"], *s["lines"], s["cta"]])
    # Digits must already be Thai words: edge-tts has no Thai number dictionary.
    if re.search(r"[0-9๐-๙]", joined):
        return False
    if _FOREIGN.search(joined):
        return False
    if _PREACHY.search(joined):
        return False
    if forbid and forbid.search(joined):
        return False
    # The measured winning hook shape must be present, or the pool drifts back to
    # the shape that got 74-173 views/day. See docs/HOOKS-MEASURED.md.
    if cues and not any(c in s["hook"] for c in cues):
        return False
    # The channel's hook floor (a tension marker). Measured 2026-11-10: without it
    # kongkeat's pool filled with flat scenes and its feed stopped showing the
    # channel, so a draft that lacks the marker is rejected before it is rendered.
    if require and not require.search(s["hook"]):
        return False
    return True


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
           "genx": "คนไทยวัยผู้ใหญ่ (Gen X) ที่เหนื่อยกับชีวิตและกำลังหาความหมาย",
           "kongkeat-story": "คนไทยที่ชอบเรื่องเล่าอบอุ่นใจเกี่ยวกับครอบครัว"}[channel]
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
    ap.add_argument("--vet", dest="vet", action="store_true", default=True,
                    help="filter each draft through the multi-model panel (default on)")
    ap.add_argument("--no-vet", dest="vet", action="store_false")
    ap.add_argument("--vet-rounds", type=int, default=2)
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
    # Close the loop: topics that the Analytics-driven panel proposed are used
    # first, so new scripts follow what actually worked on the channel. They are
    # subjects, not hooks, so the overlap floor is high (8) -- a loose 3-char
    # floor rejected every learned subject on a channel whose pool is already
    # full of family stories (measured 2026-11-07: 0 of 8 survived).
    ins_path = os.path.join(ROOT, "content", "insights", f"{args.channel}.json")
    learned: list[str] = []
    rules: list[str] = []
    if os.path.exists(ins_path):
        try:
            with open(ins_path, encoding="utf-8") as fh:
                blob = json.load(fh)
            learned = [t for t in blob.get("topics", []) if not _overlaps(t, seen, 8)]
            rules = [r for r in blob.get("rules", []) if isinstance(r, str)][:3]
        except (json.JSONDecodeError, OSError):
            learned = []
    angles = learned + [a for a in cfg["angles"] if not _overlaps(a, seen)]
    if learned:
        print(f"  using {len(learned)} topics learned from the channel's own analytics")
    if not angles:
        # Every curated subject is used; ask for more rather than repeat them.
        angles = ask_angles(key, args.channel, seen, max(args.count, 8))
        print(f"  curated angles exhausted; Gemini proposed {len(angles)} new ones")
    if not angles:
        sys.exit("no fresh angles available and Gemini returned none")

    cues = cfg.get("cues", ())
    prompt = cfg["prompt"].format(count=args.count, angles=", ".join(angles[:args.count + 4]),
                                  done="; ".join(done[-12:]) or "ไม่มี")
    if rules:
        prompt += ("\n\nกฎที่เรียนรู้จากคลิปที่ทำได้ดี/แย่ของช่องนี้ (ต้องทำตาม):\n- "
                   + "\n- ".join(rules))
        print(f"  applying {len(rules)} rules learned from the video review")
    forbid = cfg.get("forbid_cta")
    require = cfg.get("require")
    fresh = [s for s in ask(key, prompt) if valid(s, cues, forbid, require)]
    # Gemini sometimes ignores the hook rule; ask once more before giving up, so
    # a thin batch does not silently leave the pool short.
    if len(fresh) < args.count:
        print(f"  only {len(fresh)}/{args.count} passed the hook check; asking again")
        again = [s for s in ask(key, prompt) if valid(s, cues, forbid, require)]
        seen_hooks = {s["hook"] for s in fresh}
        fresh += [s for s in again if s["hook"] not in seen_hooks]

    next_id = max([int(s["id"]) for s in existing] + [0]) + 1
    added = []
    for s in fresh[:args.count]:
        sid = f"{next_id:02d}"
        next_id += 1
        added.append({"id": sid, "hook": s["hook"], "lines": s["lines"], "cta": s["cta"]})

    # Filter every draft through the multi-model panel before it joins the pool,
    # so a weak hook is revised here rather than measured as a losing video later.
    if args.vet and added:
        sys.path.insert(0, HERE)
        try:
            from panel_script import panel as panel_vet
        except Exception as e:  # noqa: BLE001
            print(f"  panel unavailable ({e}); keeping raw drafts")
        else:
            for s in added:
                print(f"  vetting {s['id']}: {s['hook'][:36]}")
                try:
                    res = panel_vet(args.channel, {"hook": s["hook"], "lines": s["lines"],
                                                   "cta": s["cta"]}, args.vet_rounds, key)
                    ch = res["chosen"]
                    if valid(ch, cues, forbid, require):
                        s.update(hook=ch["hook"], lines=ch["lines"], cta=ch["cta"])
                        s["vetted"] = True
                except Exception as e:  # noqa: BLE001
                    print(f"    panel failed for {s['id']} ({type(e).__name__}); keeping draft")

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
