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

# The knowledge genre's hook floor (pivot 2026-11-16). A five-advisor panel chose
# general knowledge for ch4 and required the Shorts to match the long-form's
# genre, or the mismatch starves the long-form's click-through. A curiosity hook
# ("why is...", "did you know...", "the truth is...") is what makes a knowledge
# Short get tapped; a flat fact statement does not. Enforced in valid().
_CURIOSITY = re.compile(
    r"ทำไม|เพราะอะไร|รู้ไหม|รู้หรือไม่|รู้หรือเปล่า|ความจริง|ที่แท้จริง|ความลับ|"
    r"มหัศจรรย์|เหลือเชื่อ|ไม่น่าเชื่อ|จริงหรือ|เคยสงสัย|คำตอบ")

# The genre a channel has LEFT. ch4 abandoned family stories on 2026-11-16, but
# its committed insights still held family subjects and a rule that carried
# "ทำไม" ("ทำไมพ่อถึงเก็บจานข้าว...", "ระบุคีย์เวิร์ด เรื่องครอบครัว"), which
# passed the curiosity marker and steered the generator straight back to the
# abandoned genre. A retired subject must name a family relationship AND carry a
# story signal (the two lookaheads are an AND): a knowledge subject like
# "ทำไมแม่น้ำจึงไหล" (river, no story signal) or "ท้องฟ้าเป็นสีฟ้าได้อย่างไร"
# (อย่างไร, no story signal) survives. Kept as a config value, not a hardcoded
# check, so a future pivot is a one-line change.
_RETIRED_FAMILY = re.compile(
    r"(?=.*(?:พ่อ|แม่|ยาย|ย่า|ปู่|ครอบครัว|ลูกชาย|ลูกสาว))"
    r"(?=.*(?:ครอบครัว|อบอุ่นใจ|เรื่องเล่า|จากไป|เสียสละ|อภัย|งานศพ|เผาศพ|มรดก|"
    r"น้ำตา|ตาย|เสียชีวิต|ป่วย|วันเกิด|ทิ้งไว้|กลับบ้าน|ค่าเทอม|ความทรงจำ|คิดถึง|"
    r"ผิดหวัง|กอด|ซ่อน|ประสบความสำเร็จ|ปรบมือ))")


def is_retired(topic: str, pattern) -> bool:
    """True if a subject or rule uses a genre the channel has left."""
    return bool(pattern and pattern.search(topic))


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
        # PIVOT 2026-11-16: ch4's long-form moved from warm family stories to
        # general knowledge (a five-advisor panel chose the genre; the long-form
        # measured 0.7 watch-hours/28d and the family Shorts, though they drew
        # 460-1,083 views, converted only 1.93 subs/1k -- worst on the fleet). The
        # panel's second finding was that the Shorts must share the long-form's
        # genre: a viewer pulled in by a family story does not click a knowledge
        # long-form, so a mismatched Shorts feed starves the very rail it feeds.
        "angles": [
            "ทำไมท้องฟ้าจึงเป็นสีฟ้า", "ทำไมน้ำทะเลจึงเค็ม", "ทำไมเราจึงหาวตามคนอื่น",
            "ทำไมแมวจึงชอบกล่อง", "ทำไมนิ้วจึงย่นเมื่อแช่น้ำนาน", "ทำไมเราเห็นฟ้าแลบก่อนได้ยินฟ้าร้อง",
            "ทำไมนกจึงบินเป็นตัววี", "ทำไมดวงจันทร์เปลี่ยนรูปร่าง", "ทำไมน้ำผึ้งจึงไม่เสีย",
            "ทำไมน้ำแข็งจึงลอยน้ำได้", "ทำไมเราจึงได้ยินเสียงสะท้อน", "ทำไมเราจึงฝัน",
            "ทำไมรุ้งจึงมีเจ็ดสี", "ทำไมท้องฟ้าจึงเป็นสีแดงยามเย็น", "ทำไมใบไม้จึงเป็นสีเขียว",
            "ทำไมเราจึงจาม", "ทำไมสัตว์บางชนิดจำศีล", "ทำไมเกลือละลายน้ำได้", "ทำไมเราจึงเมาเครื่องบิน",
            "ทำไมเราจึงมองเห็นดาวตก", "ทำไมเสียงจึงดังในที่แคบ", "ทำไมน้ำจึงเดือดที่ยอดเขา",
            "ทำไมคนเราจึงมีลายนิ้วมือไม่เหมือนกัน", "ทำไมดอกไม้จึงมีกลิ่น", "ทำไมลมจึงพัด",
        ],
        # The curiosity cues and the hook floor. A knowledge Short is tapped
        # because the hook opens a question, so both the cue list and the required
        # marker ask for that shape; a flat fact statement is rejected in valid().
        "cues": ("ทำไม", "รู้ไหม", "เพราะอะไร", "ความจริง", "เคยสงสัย"),
        "require": _CURIOSITY,
        # The genre this channel left (family stories). Learned topics and rules
        # that use it are dropped, so the committed family insights cannot steer
        # the pool back after the pivot.
        "retired": _RETIRED_FAMILY,
        # The channel's long-form gets few views, so a "go watch the full clip"
        # CTA still sends viewers to a dead end. Enforced by valid().
        "forbid_cta": _BROKEN_CTA,
        "prompt": """คุณคือผู้เขียนสคริปต์ Shorts ภาษาไทยให้ช่อง "เกร็ดความรู้รอบตัว"
กลุ่มเป้าหมาย: คนไทยทั่วไปที่ชอบเรื่องน่ารู้สั้น ๆ เข้าใจง่าย

เขียน Shorts ใหม่ {count} คลิป เรื่อง: {angles}
(ห้ามซ้ำกับที่เขียนไปแล้ว: {done})

แต่ละคลิปเป็น JSON object:
{{"hook":"ประโยคเปิด 1 บรรทัด (ไม่เกิน 12 คำ)","lines":["...","...","...","...","...","...","...","...","..."],"cta":"ประโยคปิดชวนติดตาม 1 บรรทัด"}}

กติกา:
- lines 8-9 บรรทัด แต่ละบรรทัด 6-12 คำ รวมแล้วพูดได้ประมาณ 50-60 วินาที
- hook บังคับ: ต้องเป็นคำถามหรือความอยากรู้ ภายใน 12 คำแรก ต้องมีคำอย่าง "ทำไม"
  หรือ "รู้ไหม" หรือ "ความจริง" ตัวอย่างที่ดี:
  "ทำไมท้องฟ้าจึงเป็นสีฟ้า ทั้งที่อวกาศเป็นสีดำ"
  "รู้ไหมว่าน้ำผึ้งแท้ไม่มีวันเสีย แม้ทิ้งไว้เป็นพันปี"
  ห้ามเขียนฮุกที่เป็นแค่การทวนความจริงเฉย ๆ เช่น "ท้องฟ้าเป็นสีฟ้า"
- เนื้อหา: อธิบายเหตุผลหรือกลไกทางวิทยาศาสตร์แบบง่าย ๆ ให้ความรู้ที่ถูกต้องจริง
- โครงเรื่อง: เปิดด้วยคำถาม -> เผยคำตอบทีละนิด -> จบด้วยเกร็ดที่ทำให้ร้องอ๋อ
- cta: ชวนติดตามอย่างเดียว ห้ามสัญญาว่า "มีคลิปเต็ม/คลิปยาว/วิดีโอตัวเต็ม/ไปดูต่อ"
  ให้เขียนแบบ "กดติดตามไว้ รับเกร็ดความรู้แบบนี้ทุกวัน"
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
    # The channel's hook floor (a curiosity marker). Measured 2026-11-10: without it
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


def fresh_angles(cfg: dict, seen: str, learned: list[str]) -> list[str]:
    """Learned subjects first, then the curated list minus what is already used.

    The overlap floor is 8 for BOTH. A loose 3-char floor rejected every curated
    angle on a channel whose pool is already full (measured 2026-11-16: dharma 0
    of 41, genx 0 of 33, kongkeat 2 of 25) -- Thai shares 3-char runs constantly,
    so the curated list silently went dead and the channel only ever used learned
    subjects.
    """
    return learned + [a for a in cfg["angles"] if not _overlaps(a, seen, 8)]


def ask_angles(key: str, channel: str, seen: str, want: int) -> list[str]:
    """Ask Gemini for new one-line subjects when the curated list is used up.

    Without this the pool starves the moment every curated angle is taken: the
    dharma list was fully used by 2026-11-03 and the generator would have had
    nothing to write about.
    """
    who = {"dharma": "คนไทยที่นอนไม่หลับ เครียด คิดมากตอนกลางคืน",
           "genx": "คนไทยวัยผู้ใหญ่ (Gen X) ที่เหนื่อยกับชีวิตและกำลังหาความหมาย",
           "kongkeat-story": "คนไทยที่ชอบเรื่องน่ารู้รอบตัวแบบสั้น ๆ เข้าใจง่าย"}[channel]
    # The subject domain follows the channel's genre. The old one asked for topics
    # "about life, thoughts, feelings", which is the dharma/genx framing -- measured
    # 2026-11-16 it steered ch4's post-pivot pool toward philosophical hooks
    # ("why do we miss the past") instead of knowledge subjects.
    subject = {"dharma": "ความคิด ความรู้สึกในชีวิตประจำวัน",
               "genx": "แง่คิดการใช้ชีวิตของผู้ใหญ่",
               "kongkeat-story": "ปรากฏการณ์ธรรมชาติ วิทยาศาสตร์ในชีวิตประจำวัน "
                                 "เกร็ดน่ารู้รอบตัว"}[channel]
    prompt = (f"กลุ่มเป้าหมาย: {who}\n"
              f"เสนอหัวข้อ Shorts ใหม่ {want} หัวข้อ ที่ยังไม่ซ้ำกับหัวข้อที่ใช้แล้ว\n"
              f"หัวข้อที่ใช้แล้ว (ห้ามซ้ำ): {seen[-2000:]}\n"
              f"แต่ละหัวข้อเป็นวลีสั้น 4-10 คำ เกี่ยวกับ{subject}\n"
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

    paused_path = os.path.join(ROOT, "content", "PAUSED")
    try:
        with open(paused_path, encoding="utf-8") as fh:
            paused = {ln.strip() for ln in fh if ln.strip() and not ln.startswith("#")}
    except OSError:
        paused = set()
    if args.channel in paused:
        print(f"{args.channel} is paused (content/PAUSED); not growing its pool")
        return 0

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
            # Drop learned subjects that lack the channel's hook marker: measured
            # 2026-11-10, kongkeat's insights still listed the flat scenes (coffee,
            # housework) that got its feed withdrawn, and putting them first steered
            # the batch back to the losing shape.
            _req = cfg.get("require")
            _retired = cfg.get("retired")
            learned = [t for t in blob.get("topics", [])
                       if not _overlaps(t, seen, 8) and (not _req or _req.search(t))
                       and not is_retired(t, _retired)]
            rules = [r for r in blob.get("rules", []) if isinstance(r, str)
                     and not is_retired(r, _retired)][:3]
        except (json.JSONDecodeError, OSError):
            learned = []
    angles = fresh_angles(cfg, seen, learned)
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

    # De-duplicate within the batch: measured 2026-11-10 the same subject came back
    # three times in one run (three coffee hooks, three house-cleaning hooks), and a
    # channel that posts the same story shape back to back is what reads as spam.
    kept: list[dict] = []
    for s in fresh:
        if any(_overlaps(s["hook"], k["hook"], 12) for k in kept):
            continue
        kept.append(s)
        if len(kept) >= args.count:
            break
    fresh = kept
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
