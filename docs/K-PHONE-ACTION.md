# ไม่ต้องทำอะไรบนมือถือ — "rogue uploader" คือ rail เก่าของเราเอง (แก้แล้ว)

อัปเดต **2026-11-15 โดย `ak`** — แทนที่ใบสั่งงานเดิมฉบับ 2026-11-15 ที่ **ผิด** และถ้า K ทำตามจะ
ทำให้ rail เราพัง (สั่งให้หมุน client secret ทั้งที่ไม่มีอะไรหลุด).

## สรุปสั้น ๆ (วัดสดแล้ว)
- "rogue uploader" ไม่มีอยู่จริง — มันคือ **`kongkeat938/ax-workspace` workflow `auto-shorts`**
  ซึ่งเป็น **repo เก่าของ K เอง** (รุ่นก่อนของ ai-content-lab). มันโพสต์ Short เข้า **ช่องเดียวกัน**
  (genx/dharma/kongkeat-story) ด้วย **secret ชุดเดียวกัน** (`YT_CH1/CH2/CH4_REFRESH_TOKEN`) และ
  บันทึกไว้แค่ใน `docs/published.json` ของมันเอง → audit ของเราจึงมองเป็น "คลิปที่ repo ไม่รู้จัก".
- หลักฐานชี้ขาด: `docs/published.json` ของ ax-workspace ลงท้ายด้วย id ที่ issue #30 เรียกว่า rogue เป๊ะ
  (`1zuI63MdHpQ`, `toEJM3ighAA`, `Ft32OE0BIsA`, `Mi0wQOTixQo`) และมันยังรันอยู่จริง
  (รอบล่าสุด 2026-11-15T13:20Z, ทุก ~30 นาที).
- **ไม่ใช่ผู้โจมตีภายนอก และไม่มี credential หลุด.** panel 5/5 เห็นตรงกัน.

## ak แก้เองครบแล้ว (K ไม่ต้องล็อกอิน)
1. **ปิด rail ต้นเหตุ** ผ่าน GitHub API: `auto-shorts` + `channel-monitor` ของ ax-workspace =
   `disabled_manually` (reversible).
2. **ตัดราก**: ลบ secret YouTube ทั้ง 5 ตัวออกจาก ax-workspace → ต่อให้มีคนเปิด workflow ใหม่
   ก็ **อัปโหลดไม่ได้** (ค่าเดียวกันยังอยู่ใน ai-content-lab, ไม่มีอะไรสูญหาย).
3. **บันทึกเป็นของเรา**: `content/known_uploads.json` เก็บ upload 75 รายการของ rail นั้น →
   audit รู้จักแล้ว ไม่ตีเป็น rogue อีก.
4. **คืนคลิปที่ถูกซ่อนผิด**: `scripts/restore_wrongly_hidden.py` + rail
   `restore-wrongly-hidden.yml` (รัน 08:22 UTC หลัง quota reset) — 25 ตัวถูกลบไปแล้ว (กู้ไม่ได้),
   5 ตัวยังแค่ถูกซ่อน (จะคืนให้อัตโนมัติ).

## ที่ K "อาจ" อยากทำ (ทางเลือก ไม่บังคับ)
- ถ้าต้องการให้ทุกอย่างสะอาดเชิงบัญชีจริง ๆ: ที่ **myaccount.google.com → Security →
  Third-party apps** ถอดแอปที่ชื่อเหมือน **"Dharma Bedtime Publisher"** ออก **เฉพาะบัญชีที่ไม่ได้
  ใช้ทำช่องเราแล้ว** — **ห้ามถอดบัญชีของ genx/dharma/kongkeat-story** เพราะ rail เรายังใช้อยู่
  (ถ้าถอด ต้อง re-consent ใหม่ทันที ไม่งั้นช่องหยุดโพสต์).
- ทางที่ปลอดภัยและไม่ต้องแตะมือถือเลย: ไม่ต้องทำอะไร — ต้นเหตุถูกตัดแล้ว.

## ตัววัดว่าสำเร็จจริง (ak ยืนยันสดให้)
- `ax-workspace` ไม่มี run ใหม่หลังเวลาที่ปิด (ตรวจ Actions API แล้ว: หยุดจริง).
- `scripts/rogue_watch_rss.py` ขึ้น "no live rogue upload" (ใช้ RSS, ไม่กิน quota).
- RSS: คลิปใหม่ในช่อง ต้องตรงกับ manifest ของเราเสมอ.
