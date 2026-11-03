# GROWTH PLAN — ช่อง Farmmer (@farmmer-n9t) ธรรมะก่อนนอน

Drafted 2026-11-03 with the signed-in ChatGPT tab (`scripts/cdp_chat.py`), fed
with **real numbers** read from YouTube Studio — not impressions.

## The measured starting point (28 days, from Studio)

| metric | value |
|---|---|
| views | 4,185 |
| watch time | 8.5 h |
| subscribers | 11 (+11 in 28 days) |
| subscribers per view | 0.26 % |

| video | length | views |
|---|---|---|
| Shorts "นอนไม่หลับ? ลองทำท่านี้ 10 วินาที" | 0:14 | **1,290** |
| Shorts "เปิดทิ้งไว้ทั้งคืน หลับลึกถึงเช้า" | 0:25 | **1,237** |
| Shorts "ก่อนนอนคืนนี้ ลองปล่อยวางสักเรื่อง" | 0:11 | **1,081** |
| Shorts "นอนไม่หลับ ลองกอดหมอนแน่นๆ" | 0:26 | 334 |
| Shorts "ขอบคุณวันนี้ ก่อนหลับตา" | 0:21 | 317 |
| long "ธรรมะก่อนนอน 90 นาที" | 1:34:09 | 1 |
| long "ปล่อยวาง แล้วใจจะเบา" | 12:00 | 2 |
| long "สะพานใบไม้ที่หายไป" | 16:06 | 5 |

**Diagnosis: this is not a discovery problem, it is a conversion problem.**
Shorts reach 1,000+; the long-form and the subscribe button do not convert.
0.26 % subscriber-per-view is far below the ~1 % a healthy funnel needs.

## Root causes (ChatGPT, on the measured data)

1. **Topic mismatch.** The Short is "a 10-second trick to fall asleep"; the long
   video is general dharma. The need that brought the viewer in is not continued.
2. **The Short finishes the job.** It answers the question, so there is nothing
   left to click for.
3. **No explicit bridge.** "ฝากติดตามด้วยนะ" alone does not work; the Related
   Video link is the lever.
4. **90-minute video is a different behaviour** from a 10-second tip. Pause the
   90-minute production for now.
5. **No reason to return.** The channel needs a nightly promise, not a topic list.

## Positioning (recommended)

> Farmmer — ธรรมะก่อนนอน · "วางความทุกข์ไว้ตรงนี้ แล้วพักใจให้สบาย"
> "ไม่ว่าวันนี้คุณจะเจออะไรมาบ้าง ขอให้คืนนี้เป็นคืนที่ใจคุณได้พัก"

Four content pillars: ปล่อยวาง (40%) · เงิน/งาน/หนี้ (25%) · ความรัก/ครอบครัว
(20%) · สติ/นอนหลับ (15%).

## Shorts that earn a follow — 3 fixed formats

| format | example | goal |
|---|---|---|
| วิธีพักใจ | "ก่อนนอน ทำสิ่งนี้เพื่อหยุดคิดฟุ้งซ่าน" | reach |
| ธรรมะชีวิตจริง | "อย่าเอาความผิดพลาดวันนี้มาตัดสินตัวเอง" | bond |
| ข้อคิดก่อนหลับ | "1 เรื่องที่คุณควรวางลงคืนนี้" | followers |

Rule: every Short gives one usable thing, then leaves one open thread for the
long video, and links it via **Related Video**.

## Long-form titles / thumbnails that make people click

| title | on-thumbnail text (3–5 words) |
|---|---|
| ก่อนนอนคืนนี้ อย่าคิดมาก | หยุดคิด แล้วพักใจ |
| เมื่อชีวิตมีหนี้สิน | อย่าทุกข์จนหมดแรง |
| คนที่ไม่เห็นคุณค่าเรา | ปล่อยเขาไป |
| ความเหนื่อยของชีวิต | พักใจเสียบ้าง |

Thumbnail style (one consistent look): dark blue + gold + warm light,
Buddha image or moon at night, one focal point, 3–5 Thai words in
white/gold. Do not put the whole title on the image.

## 7-day experiment (targets, not promises)

| metric | target |
|---|---|
| new Shorts | 4 |
| new long-form | 2 |
| Related Video | link every relevant Short |
| new subscribers | 5–10 |
| long-form | starts getting views *from* Shorts |

Before blaming a thumbnail, check **Impressions / CTR** — if nobody saw it,
the thumbnail is not the problem. Also read **Shorts → Engaged views,
Stayed to watch, Subscribers gained**, and **Audience → Viewers across
formats**.

## Next data ChatGPT asked for

1. Stayed-to-watch % of the top Shorts.
2. Traffic source of the Shorts viewers (Shorts feed / search / browse).
3. Long-form impressions and CTR.

## ติดตั้งภาพปก — สถานะและวิธีทำต่อ (2026-11-03)

ภาพปก 6 ใบพร้อมแล้วที่ `assets/branding/farmmer/thumbs/` แต่ยังติดตั้งไม่ได้เพราะ
โควตา YouTube Data API ของวันหมด (รีเซ็ตเที่ยงคืนแปซิฟิก = **08:00 UTC**).

รันเองได้ในคำสั่งเดียว เมื่อโควตากลับมา:

```
python3 scripts/set_thumbnails.py            # ตั้งทุกคลิปใน manifest
python3 scripts/set_thumbnails.py --check    # ยืนยันว่าติดตั้งแล้ว
```

หรือรอให้ workflow `.github/workflows/set-thumbnails.yml` รันเอง
(08:07/09:07/10:07/11:07 UTC) — แต่ **cron ของ GitHub ไม่น่าเชื่อถือในโปรเจกต์นี้**
(ทั้ง repo นี้ไม่เคยมี schedule event เลย ดู `actions/runs?event=schedule`)
ถ้าไม่ติดตั้งเองภายในคืนเดียว ให้รันคำสั่งข้างบนจากเซสชันถัดไป

หมายเหตุ: วัดแล้วว่า `thumbnails.set` **ไม่ได้**มีโควตาแยกของตัวเอง — โควตาหมด
ทั้งโปรเจกต์จะได้ `403 quotaExceeded` เหมือนกัน (ต่างจากที่ docstring เดิมเขียนไว้)
