# คุณภาพเท่า Gemini — ทุกอย่างฟรี (K, 2026-11-18)

คำถาม K: *"ทำยังไงให้ได้คุณภาพเหมือน gemini ทุกอย่างฟรี"*
คำตอบสั้น: **ให้ Gemini (ฟรี) เป็นคนตัดสินคุณภาพทุกจุด และให้เครื่องมือฟรีเป็นคนผลิต**
ไม่ใช่พยายามรันโมเดลระดับ Gemini ใน pod (ทำไม่ได้ — pod ไม่มี GPU/จอ)

## 1) คุณภาพมาจากไหน — Gemini ฟรี คือ "ผู้ตรวจ"

ทุกจุดที่ตัดสินว่า "งานดีหรือไม่" ให้ **ถาม Gemini** (`scripts/advise.py`, free
`GEMINI_API_KEY`). นี่คือที่มาของคุณภาพ — ไม่ใช่ตัว renderer.

| ขั้น | ใครตัดสิน | ฟรีไหม |
|---|---|---|
| คิดหัวข้อ/มุมเรื่อง | Gemini (`team.py run researcher`) | ฟรี |
| เขียนบท | Gemini (`team.py run scriptwriter`) | ฟรี |
| ตรวจบท (เกรด A-D) | Gemini (`team.py run critic`) | ฟรี |
| แพ็กเกจ (ชื่อ/แท็ก/ปก) | Gemini (`team.py run packager`) | ฟรี |
| **งานไม่ผ่าน → วิธีแก้** | Gemini (`scripts/fix_with_gemini.py`) | ฟรี |

## 2) งานไม่ผ่าน → ถาม Gemini ทันที (wired แล้ว)

`scripts/fix_with_gemini.py` รับงานที่ **ไม่ผ่าน gate** พร้อม "เหตุผลที่วัดได้" แล้วส่งให้
Gemini ขอวิธีแก้ + ของที่แก้แล้ว. ต่อเข้า 2 gate:

* `qa_gate.py` veto (คลิปยาว) → `add_release_to_manifest.py` เรียก `ask_gemini_for_fix()`
* `short_standard.py` hold (Shorts) → `publish_shorts.py` เรียก `_ask_gemini_for_fix()`

**กฎที่ยึด:** คำตัดสินของ gate **ไม่เปลี่ยน** เพราะคำแนะนำของ LLM (LLM ไม่ใช่ primary
source) — งานยังถูกกักไว้ จนกว่าจะแก้แล้ววัดใหม่ผ่าน. ถ้า Gemini ล่ม → บันทึก error แล้ว
gate ยัง veto ต่อ (ไม่ false pass).

ผลลัพธ์ถูกเขียนที่ `content/fixes/<kind>_<key>.json` (ไม่ commit — กัน rail แข่งกันเขียน).

## 3) สแต็กฟรีทั้งหมด (ที่ใช้จริง)

| ส่วน | เครื่องมือ | หมายเหตุ |
|---|---|---|
| ตัดต่อ/เรนเดอร์ | `ffmpeg` | crf18, yuv420p tv/bt709 |
| ภาพเคลื่อนไหวจริง | Coverr b-roll (`fetch_broll.py`) | keyless |
| เสียงบรรยาย | edge-tts (house voice) | ฟรี; Fish voice (K) เสริมได้ |
| เพลง | CC0 (`fetch_music.py`) | ฟรี |
| ภาพนิ่ง | Wikimedia / Pollinations | keyless fallback |
| **สมอง (คุณภาพ)** | **Gemini free tier** | `GEMINI_API_KEY` |

## 4) ข้อจำกัดที่บอกตรง ๆ

* **รันโมเดลเท่า Gemini ใน pod ไม่ได้** — pod headless ไม่มี GPU; ทางเดียวคือ *เรียก*
  Gemini ผ่าน API (ฟรี) ไม่ใช่ก็อปโมเดลมา.
* **Gemini ฟรีมีโควตา** — นาทีที่คนใช้เยอะจะ 503 บ้าง; `ask_gemini` ไล่ลองหลายโมเดล
  (`gemini-3.5-flash-lite` → `gemini-3.1-flash-lite` → `gemini-flash-lite-latest`) ก่อนยอมแพ้.
* **ช่องว่างเดียวที่ยังไม่ฟรี = presenter (คนพูดจริง)** — ที่เหลือทำได้ฟรีครบ.

Guard: `scripts/test_fix_with_gemini.py` (FAIL ได้ — prompt ที่ทิ้งเหตุผล, advisor ตาย,
หรือ reply ที่ไม่ใช่สคริปต์ ต้องถูกจับ).
