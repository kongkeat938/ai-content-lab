# Which hooks win — measured, not guessed

Source: `scripts/report_reach.py` (views ÷ days the video has been up), run
2026-11-03 on the live channels. Views/day is the reach signal.

> **Correction (2026-11-04):** an earlier version of this file claimed the refresh
> tokens cannot read the YouTube Analytics API. That was **wrong** — the granted
> `https://www.googleapis.com/auth/youtube` scope is accepted by the Analytics API.
> `scripts/analytics.py` now reads real watch-hours and average view percentage per
> video, so reach (views) and hold (watch time) can be judged together. The tables
> below stay useful as the views/day record; the watch-time winners are in
> `docs/ANALYTICS-2026-11-04.md`.

## ch1 — ตาต้า GenX (ปรัชญาชีวิต)

| hook | views | days | /day |
|---|---|---|---|
| เราไม่ต้องเก่งที่สุด แค่ต้องอยู่ให้ถึงพรุ่งนี้ | 1171 | 3.1 | **373** |
| ก้าวเล็ก ๆ ที่ไม่มีใครเห็น | 926 | 3.0 | **310** |
| เติบโตมาจนพบว่าบ้านคือเงาของเราเอง | 202 | 1.4 | 148 |
| เมื่อถึงเวลาขอบคุณตัวเองที่สู้มานาน | 190 | 1.5 | 124 |

**Formula:** give relief and permission. "You do not have to be the best" and
"small steps nobody sees" beat a neutral observation. The viewer is tired and
wants to be told they are allowed to rest, not lectured.

## ch2 — Farmmer (ธรรมะก่อนนอน)

| hook | views | days | /day |
|---|---|---|---|
| เปิดทิ้งไว้ทั้งคืน หลับลึกถึงเช้า | 1237 | 2.2 | **574** |
| นอนไม่หลับ? ลองทำท่านี้ 10 วินาที | 1290 | 3.3 | **393** |
| นอนไม่หลับ ลองกอดหมอนแน่น ๆ ดูนะ | 342 | 0.9 | 361 |
| ก่อนนอนคืนนี้ ลองปล่อยวางสักเรื่อง | 1083 | 3.3 | **329** |
| ขอบคุณวันนี้ ก่อนหลับตา | 317 | 3.0 | 105 |
| ความคิดเรื่องงานพรุ่งนี้กำลังขโมยการนอนของคุณ | 74 | 0.4 | 173 |
| สมองไม่ยอมหยุดคิดเรื่องแย่ ๆ ซ้ำไปมา | 42 | 0.4 | 99 |

**Formula:** name one thing the viewer can *do tonight*. Among clips of the same
age, the actionable hooks run three to five times the restating-the-problem ones.
A hook that only says "you cannot sleep because of X" is the losing shape.

## ch4 — kongkeat pratumma (เรื่องเล่าการ์ตูน)

| hook | views | days | /day |
|---|---|---|---|
| พ่อกอดลูกชายในวันที่สอบตก | 1002 | 1.5 | **673** |
| พี่ชายตักข้าวให้ผมในวันที่เหนื่อย | 234 | 0.4 | 631 |
| คืนนั้นแม่ทำกับข้าวให้เขา กินข้าวด้วยกันที่โต๊ะ | 1079 | 5.3 | 203 |
| เขาคุกเข่าลงต่อหน้ารูปพ่อ แล้วขอโทษซ้ำ ๆ | 459 | 5.3 | 86 |
| แม่น้ำที่ไหลไม่หยุด | 102 | 2.4 | 42 |
| เมล็ดที่รออยู่ใต้ดิน | 107 | 3.1 | 35 |

**Formula:** a specific family moment with a named relationship (พ่อ / แม่ /
พี่ชาย / พี่สาว) and one physical action (กอด / ตักข้าว / คุกเข่า). Abstract
titles ("แม่น้ำที่ไหลไม่หยุด", "ไผ่ที่รอสี่ปี") do not travel.

## What this changed

- `scripts/gen_short_scripts.py` dharma prompt now requires a concrete
  tonight-action in the hook, and states the measured contrast.
- Same file, genx prompt already asks for a belief-challenge; the measured
  winners are the *relief* form of that, so the prompt says so.
- Both prompts reject digit characters (edge-tts has no Thai number dictionary).

## The number we still cannot see

Retention and impressions need the `yt-analytics.readonly` scope. Re-consenting
the three channels with that scope added is a K task; until then this file is the
best available read.
