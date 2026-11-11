# บรีฟรอบ 2: บั๊กที่ 2 — advisor "gemini" ไม่มีในทะเบียน (2026-11-11)

ตอบภาษาไทย กระชับ เรียงตามผลตอบแทนต่อแรง อ้างตัวเลขในบรีฟ บอกตรง ๆ ว่าอะไร "ไม่ควรทำ" เพราะอะไร

## บั๊กที่ 1 (แก้แล้ว): คำใบ้ปมตึงไม่ถูกส่งให้ panel
- `studio_ai.TOPICS_HINT` คีย์ `"kongkeat"` แต่ถูกเรียกด้วย `"ch4"` → คำใบ้ปมตึงไม่ถูกส่ง →
  panel เสนอหัวข้อแบน → `content/insights/ch4.json` แบน → CI `selftest` FAILED (2026-11-11T09:44Z).
- แก้: คีย์เป็น `"ch4"` + resolve ผ่าน alias สองทาง + เพิ่ม `filter_topics()` กรองหัวข้อที่ไม่มี
  marker ก่อนเขียนไฟล์ (มี fallback) + เทสต์ `test_insights_wiring.py` (พิสูจน์ว่า FAIL บนโค้ดเก่า).

## บั๊กที่ 2 (เพิ่งเจอ — วัดสด): `advise.ADVISORS` ไม่มีคีย์ `"gemini"`
- `advise.py` นิยาม `ADVISORS` ด้วยคีย์: `gemini-3.5`, `gemini-3.1`, `gemini-flash`,
  `gemini-preview`, `openrouter`, `pollinations`, `openhands`, ... — **ไม่มีคีย์ `"gemini"`**.
- แต่ 4 สคริปต์เรียกชื่อ advisor ว่า `"gemini"` ตรง ๆ:
  - `studio_ai.py:308` → `for name in ("gemini", "pollinations")` (สมองเรียนลูป)
  - `video_review.py:281` → เหมือนกัน (ให้เกรด A–D + 3 กฎ)
  - `diagnose_videos.py:223` → เหมือนกัน
  - `panel_scorecard.py:110` → `fast = ["gemini", "pollinations"]`
- ทุกที่ใช้ `advise.ADVISORS.get(name)` + `if not fn: continue` → ชื่อ `"gemini"` ไม่เจอ →
  **ถูกข้ามเงียบ ๆ** → กรรมการเหลือแค่ **pollinations ตัวเดียว** (vendor เดียว, ช้า ~66 วิ).
- **หลักฐานสด:** `docs/STUDIO-AI-ch4.md` (รัน 2026-11-11T01:28Z) มีหัวข้อแค่ `### pollinations`
  — ไม่มี gemini เลย. `docs/REVIEW-ch4.md` ก็เช่นกัน. เอกสารเคยอ้าง "panel" แต่จริง ๆ มีกรรมการเดียว.
- ซ้ำร้าย: มีเทสต์ `test_advise_panel.py` ที่เขียนไว้กันบั๊กคลาสนี้พอดี (คอมเมนต์ในไฟล์:
  "The panel once shipped a name (`gemini-latest`) that was missing from ADVISORS, so a slot
  silently degraded") — **แต่เทสต์เช็คแค่ FAST/FAST_PLUS/BROAD/DEEP ไม่เช็คชื่อที่สคริปต์
  เรียกจริง** → บั๊กนี้รอด.

## คำถาม

1. ต้นเหตุถูกต้องไหม? การที่ "กรรมการเหลือ 1 ตัว" ทำให้คุณภาพการเรียนของลูป (หัวข้อ/กฎ)
   เสียหายแค่ไหน และกระทบ dharma (ช่องที่แบก YPP 98.6%) ไหม?
2. วิธีแก้: (ก) เพิ่มคีย์ `"gemini"` เข้า `ADVISORS` (alias ของ `gemini-3.5-flash-lite`) แก้ทีเดียว
   4 ที่; หรือ (ข) เปลี่ยนสคริปต์ทั้ง 4 ให้ใช้ชื่อที่มีอยู่ (`gemini-3.5`); หรือ (ค) ให้ light panel
   ใช้ทีมเต็ม (`advise.FAST`) แทน 2 ตัว. ผมควรทำแบบไหน และเพราะอะไร?
3. ควรเพิ่ม guard อะไรที่ "ล้มได้" เพื่อกันบั๊กชื่อกรรมการหลุดแบบนี้ซ้ำ (เช่น บังคับให้
   ชื่อ advisor ทุกตัวที่สคริปต์เรียกอยู่ใน `ADVISORS`, หรือห้าม `.get(name)` + `continue` เงียบ ๆ)?
4. มีความเสี่ยงอื่นในระบบที่ "ชื่อ/คีย์ไม่ตรงกันแล้วถูกข้ามเงียบ ๆ" (silent skip) ที่ผมควรกวาดหาไหม?
