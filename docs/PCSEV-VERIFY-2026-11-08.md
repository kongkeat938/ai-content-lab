# PCSEV — "verifi จากอะไร" (2026-11-08)

K ถาม: *"ตามหลัก pcsev เราจะ verifi จากอะไรดี"*
**PCSEV = Problem → Cause → Solution → Execute → Verify.**
คำถามคือขั้น **V** — เราตรวจ "ว่ามันได้ผลจริง" จาก **แหล่งไหน**.

คำตอบสั้น: **verifi จาก "แหล่งที่วัดได้จริง ณ ปัจจุบัน" ไม่ใช่จากเอกสารของเราเอง**
เพราะเอกสารที่ commit ไว้ก็คือ "คำอ้าง" อีกชั้นหนึ่ง — มันเก่าได้ และผิดได้.

---

## หลักการ: ลำดับความน่าเชื่อถือของแหล่ง

| ระดับ | แหล่ง | ใช้กับ | น้ำหนัก |
|---|---|---|---|
| 1 (แรงสุด) | **API สด** (Analytics/Data API) | ตัวเลขผู้ชม, retention | วัดใหม่ทุกครั้ง |
| 2 | **ไฟล์ผลลัพธ์จริง** (ffprobe/ebur128) | LUFS, TP, ความยาว, color range | receipt ของไฟล์นั้น |
| 3 | **เทสต์ที่ล้มได้** (guard test) | "rail ยังทำงานไหม" | fail ได้ = พิสูจน์ได้ |
| 4 (อ่อนสุด) | **เอกสารที่ commit ไว้** | อย่างอื่นทั้งหมด | **ไม่ใช่คำตอบปัจจุบัน** |

> **กฎ:** เอกสารบอก "ให้ไปวัดที่ไหน" — ไม่ใช่ "คำตอบคืออะไร".

---

## หลักฐานที่วัดวันนี้ (2026-11-08) — ทำไมเรื่องนี้สำคัญ

### P — ปัญหา
`scripts/report_reach.py` เขียนไว้ (2026-11-03) ว่า:
> "Retention and impressions are **NOT available**: the refresh tokens carry the
> `youtube` scope only ... so the Analytics API refuses them."

### C — สาเหตุ/ความจริง
**วัดจริง 3 ช่อง → token เรียก Analytics API ได้ทั้งหมด** (เอกสารผิด).
และ snapshot ที่ commit ไว้ (`docs/watch_hours.json`, 2026-11-06) **คลาดเคลื่อน
52-244%** จากของจริงในหน้าต่างเวลาเดียวกัน:

| ช่อง | snapshot (commit) | live (วัดวันนี้, หน้าต่างเดิม) | delta |
|---|---|---|---|
| genx | 5,743 วิว / 24.2 ชม. | **19,760 วิว / 86.5 ชม.** | +244% |
| dharma | 7,018 วิว / 39.4 ชม. | **10,861 วิว / 56.5 ชม.** | +55% |
| kongkeat | 3,695 วิว / 15.5 ชม. | **5,645 วิว / 19.3 ชม.** | +53% |

**สาเหตุจริง (วัดแล้ว ไม่เดา):** ไม่ใช่ snapshot "ผิด" — มันคือตัวเลข **ก่อนบูม**.
daily ของ genx: 10-31=1,624 · 11-03=3,111 · **11-04=8,823** · 11-05=5,216
(ก่อน 10-31 วิวน้อยมาก). snapshot ถูกถ่ายตอน 11-06 15:48 แต่ API รายงานย้อนหลัง
ช้ากว่าที่ควร + มีคลิปไวรัลหลัง snapshot.

⇒ **verifi จาก snapshot = verifi จากอดีต.** ต้อง verifi จาก live API.

### S/E — แก้ + ทำ
- **`scripts/verify_claims.py` (ใหม่)** — วัดซ้ำทุกช่องจาก live API ในหน้าต่างเดียวกับ
  snapshot แล้วเทียบ; ถ้าต่างเกิน 5% → `DIVERGED` → **exit 1** (ทำให้ job ล้ม ไม่เงียบ).
- **แก้ docstring ที่ผิด** ใน `report_reach.py` ให้ตรงความจริง (retention **มี**, แต่
  `impressions`/CTR **ไม่มี** ทาง API — 400 "Unknown identifier").
- **`scripts/test_verify_claims.py` (ใหม่)** — ป้อน snapshot ที่เก่าจริง แล้วต้อง
  รายงาน DIVERGED; snapshot ที่ตรงต้องผ่าน; API ล่มต้องไม่ถูกตีเป็น "match".

### V — ตรวจ
- `python3 scripts/verify_claims.py` → **STALE 3 ช่อง, exit 1** (ตามคาด)
- เทสต์ **10/10 ผ่าน** (รวม `test_verify_claims`)

---

## ตารางสรุป: แต่ละคำถาม verifi จากไหน

| คำถาม | verifi จาก | เครื่องมือ |
|---|---|---|
| "ยอดดู/ชม.ดู เท่าไหร่" | Analytics API สด | `verify_claims.py`, `analytics.py` |
| "retention/AVD เท่าไหร่" | Analytics API (`averageViewPercentage`, `audienceWatchRatio`) | `studio_ai.py` |
| "impressions/CTR เท่าไหร่" | **Studio UI เท่านั้น** (API ไม่มี) | K เปิด Studio (หรือปล่อย) |
| "รายได้เท่าไหร่" | **ยังไม่มี** (scope ไม่พอ: "Insufficient permission") | ต้อง re-consent |
| "วิดีโอถูกล็อคไหม/ยาวเท่าไหร่" | receipt ของไฟล์ (ffprobe) | `qa_gate.py` |
| "rail ยังทำงานไหม" | guard test | `scripts/test_*.py` |
| "ออโตเมชันครบไหม" | `foreman --dry-run` + `test_watchdog` | ทุก workflow ถูกขับ |
| "เรื่องนี้จริงไหม" | **อย่าเชื่อเอกสาร — ไปวัดที่ API** | `verify_claims.py` |

---

## บทเรียนถาวร

1. **ตัวเลขทุกตัวในเอกสารมี "วันหมดอายุ"** — ต้องมีเครื่องมือวัดซ้ำได้เสมอ.
2. **API มี 2 ชนิดที่ scope ต่างกัน** — Data API (วิว) vs Analytics API (ชม.ดู/retention);
   ต้องวัดว่า token ตัวไหนได้อะไร **อย่าเชื่อ docstring**.
3. **ความจริงที่ขัดกับเอกสาร = หลักฐานว่าถึงเวลาวัดใหม่** — เจอวันนี้ 2 จุด.
4. **"Verify" ที่ดีต้องล้มได้** — เครื่องมือที่ไม่มีทาง fail = ไม่ได้พิสูจน์อะไร
   (จึงมี `test_verify_claims.py`).
