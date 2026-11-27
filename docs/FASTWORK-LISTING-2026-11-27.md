# Fastwork listing — paste-ready sheet (2026-11-27)

Why this file exists: every sales asset is already built (`docs/OFFER-2026-11-25.md`, the public page
`docs/portfolio/index.html`, two demo releases, 126 live requests in `content/prospects_external.json`),
and **none of it has ever been sent**. The only missing step is a seller account, and that needs K's own
identity. This sheet turns that step into ~15 minutes of copying and pasting instead of an afternoon of
writing.

Status: **account not created.** Prices below are generated from `content/packages.json`
(guarded by `scripts/test_portfolio_prices.py`) — never retype them from memory.

## 1. What K has to do (the part ak cannot do)

| # | step | why it is K's |
|---|---|---|
| 1 | sign up at Fastwork as a **seller** | ak never signs up as K; the account carries K's name and ID |
| 2 | verify identity + add the bank account for payouts | money must land in K's account, not an agent's |
| 3 | paste the fields in §2, upload the cover image | copy is ready below |
| 4 | publish the gig, then tell ak the gig URL | ak keeps the reply log and the 30-day clock |

If Fastwork rejects the account (no ID, no bank, category closed) — **stop and tell ak**; the stop rule in
`docs/OFFER-2026-11-25.md` §8 says a channel that cannot be opened is a blocker to report, not to work around.

## 2. The fields to paste

**Service title (≤ 70 chars):**
> รับตัดคลิปสั้น 9:16 จากวิดีโอของคุณ — พาดหัว + คำบรรยาย + thumbnail

**Category:** the closest video-editing / short-video category the site offers (the Thai names change;
pick the one that says ตัดต่อวิดีโอ / วิดีโอสั้น, not "AI").

**Description (paste as-is):**
> ผมรับตัดคลิปสั้นแนวตั้ง 9:16 จากไฟล์วิดีโอที่คุณมีอยู่แล้ว — คลิป 30–60 วินาที พร้อมพาดหัวไทย/อังกฤษ
> คำบรรยายใต้ภาพ และ thumbnail 1 ใบต่อคลิป
>
> ส่งงาน 1–2 วันทำการหลังได้รับไฟล์ต้นฉบับ (งาน 5–10 คลิป) · แก้ไข 2 ครั้ง/คลิป
> ไฟล์ที่ส่งมอบ: MP4 1080x1920, เสียงปรับให้ใกล้ -14 LUFS (ค่าที่แพลตฟอร์มใช้ normalize เสียงอัตโนมัติ)
>
> ตัวอย่างงานจริงที่ผมผลิตเอง (ไม่ใช่งานลูกค้ารายใด):
> https://github.com/kongkeat938/ai-content-lab/releases/tag/demo-shorts-2026-11-25
>
> อยากดูก่อนตัดสินใจ: ทำตัวอย่างให้ 1 คลิป 20 วินาที 720x1280 มีลายน้ำ "ตัวอย่าง" (1 คลิป/ลูกค้า/ช่อง)
>
> ข้อตกลง: คุณยืนยันว่าเป็นเจ้าของหรือมีสิทธิ์ในภาพ เสียง และเพลงที่ส่งมา — ผมตรวจเฉพาะว่าไฟล์เปิดได้
> และสเปกถูกต้อง ไม่รับตรวจลิขสิทธิ์แทน · ไฟล์เก็บ 30 วันแล้วลบ · ใช้เป็นผลงานตัวอย่างได้เมื่อคุณอนุญาตเป็นลายลักษณ์อักษร

**Tags:** ตัดต่อวิดีโอ, คลิปสั้น, shorts, reels, tiktok, คำบรรยาย, thumbnail, วิดีโอแนวตั้ง

**Packages (copy exactly from `content/packages.json`):**

| แพ็ก | จำนวน | ราคา | ต่อคลิป |
|---|---|---|---|
| **A · ทดลอง 5 คลิป** | 5 คลิป | **490 บาท** | 98.0 |
| **B · แพ็กหลัก 10 คลิป** | 10 คลิป | **750 บาท** | 75.0 |
| **C · 20 คลิป** | 20 คลิป | **1,590 บาท** | 79.5 |

- แพ็กหลักที่ควรโปรโมต = **B (10 คลิป)**; แพ็ก C เปิดเมื่อส่งงานจริงได้ 3 ออเดอร์ (เหตุผลใน OFFER §1)
- งานด่วนส่งใน 12 ชม. +100 บาท/ออเดอร์ · แก้เพิ่มรอบที่ 3 ขึ้นไป 50 บาท/คลิป
- **ราคาหักค่าธรรมเนียมแล้วเหลือเท่าไร:** `python3 scripts/net_revenue.py` (อัตราจริงยังไม่ยืนยันจากหน้า Seller — ห้ามเขียนตัวเลขสุทธิในประกาศ)

**Cover image:** ใช้เฟรมจาก `docs/portfolio/media/` (ภาพที่ผลิตเอง) + ข้อความสั้น "คลิปสั้น 9:16 พร้อมพาดหัว"

## 3. FAQ (ตอบในหน้า gig — คำตอบสั้นและไม่สัญญาเกิน)

1. **ใช้ไฟล์ของใคร?** ของคุณเท่านั้น — ผมไม่เอาคลิปไปลงช่องตัวเอง
2. **ได้กี่คลิปจากวิดีโอยาว 10 นาที?** ขึ้นกับจังหวะเนื้อหา — แพ็ก 5 คลิปคือจุดเริ่มที่ปลอดภัย
3. **แก้ได้กี่ครั้ง?** 2 ครั้ง/คลิป รวมอยู่ในราคา
4. **รับประกันยอดวิวไหม?** ไม่ — ผมรับประกันสเปกไฟล์และกำหนดส่ง ไม่รับประกันการเข้าถึงของอัลกอริทึม
5. **เพลงลิขสิทธิ์?** คุณเลือก/ส่งมาเอง หรือใช้เพลงฟรีที่ผมแนะนำ (ระบุในแชทก่อนเริ่ม)

## 4. When the first order arrives (runbook — ทุกขั้นมีของอยู่แล้ว)

1. ขอไฟล์ต้นฉบับ + ยืนยันสิทธิ์เป็นข้อความในแชท (เก็บข้อความไว้)
2. `ffprobe` ไฟล์ที่ได้ → ถ้าเปิดไม่ได้/สเปกไม่ชัด แจ้งลูกค้าก่อนเริ่ม (ไม่คิดเงินถ้ายังไม่เริ่ม)
3. ตัดคลิปด้วยเครื่องมือใน repo; ตรวจทุกไฟล์ด้วย gate ที่ **FAIL ได้** (`short_standard.py`) — 1080x1920, tv/bt709, LUFS ใกล้ -14
4. QC: ดู 1 รอบ/คลิป + เช็คว่าไม่มีไฟล์ซ้ำ (md5)
5. ส่งลิงก์ + แจ้งวันลบไฟล์ (30 วัน) + ขออนุญาตใช้เป็น portfolio (ถ้าไม่ให้ = ไม่ใช้)

## 5. ตัวชี้วัด 30 วัน (อ้าง OFFER §8 — ไม่ตั้งเป้าใหม่)

| ตัวชี้วัด | เป้า | ถ้าไม่ถึง |
|---|---|---|
| ประกาศขายได้ | ≥ 1 ที่ | ติดสิทธิ์บัญชี → แจ้ง K |
| คนสอบถาม | ≥ 3 ราย | 0–1 → แก้ข้อความ/ราคา 1 รอบ |
| งานเสียเงินแรก | ≥ 1 ราย | ไม่มีใน 30 วัน → **หยุดเส้นทางนี้** ตามกติกาเหล็ก |

## 6. ห้ามเขียนในประกาศ (ตรวจโดย `scripts/test_portfolio_prices.py`)

- รีวิว/คำรับรองจากลูกค้าที่ยังไม่มี · ตัวเลขยอดวิวที่รับประกัน · "มาตรฐานแพลตฟอร์ม" (มันคือการ normalize ไม่ใช่ข้อบังคับ)
- ราคาที่ไม่ตรงกับ `content/packages.json`
