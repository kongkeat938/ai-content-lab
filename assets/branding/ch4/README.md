# PCSEV (ch4 @PCSEV) — ภาพแบรนด์ช่อง

> ชื่อช่องบน YouTube = **PCSEV** (handle `@PCSEV`) วัดสด 2026-11-17 จาก 3 แหล่ง
> (RSS feed, หน้า channel, oEmbed). เดิมทีชื่อเป็น "เกร็ดความรู้รอบตัว" ซึ่งเป็น
> ชื่อ *ธีมคอนเทนต์* ไม่ใช่ชื่อช่อง — `set_channel_name.py` จึงตั้ง target = "PCSEV"
> ให้ตรงกับชื่อจริง (ดู `scripts/test_channel_name_live.py` ที่กันการเพี้ยนกลับ).
> แบรนด์อาร์ตยังคงคอนเซปต์ "เกร็ดความรู้" (หลอดไฟ + ?).

รีดีไซน์ 2026-11-16 หลัง pivot genre **เรื่องเล่าอบอุ่นใจ → เกร็ดความรู้รอบตัว**
อาร์ตเก่า (ห้องนั่งเล่น + ถ้วยชาไอน้ำหัวใจ) ล้าสมัยแล้ว จึงวาดใหม่เป็นสไตล์
**knowledge** (แบนราบ สว่าง ไม่ใช้ภาพถ่าย) ด้วย `scripts/make_branding.py --style knowledge`.

## คอนเซปต์ (จาก panel ที่ปรึกษา 5 คน, 2026-11-16)

- **สัญลักษณ์:** หลอดไฟมีเครื่องหมาย **?** = "ความคิด/เกร็ดความรู้" (มินิมอล กลางวงกลม)
- **พื้นหลังสว่าง** (กฎ K ห้ามพื้นมืด) — ไล่เฉดฟ้าอ่อน → ครีมอุ่น, มีเรขาคณิตจาง ๆ
- **สี:** ตัวอักษรน้ำเงินเข้ม `#0A192F` ตัดพื้นสว่าง · เน้นส้ม `#FF6F00`
- **คำโปรย:** "เรื่องน่ารู้ชวนคิด · มีคำตอบให้ทุกวัน"

| ไฟล์ | ขนาด | ใช้ที่ไหน | สถานะ |
|---|---|---|---|
| `banner_2560x1440.jpg` | 2560×1440 | ภาพแบนเนอร์ช่อง | ⏳ ติดตั้งผ่าน Studio (หรือ API เมื่อ quota ว่าง) |
| `avatar_800x800.jpg` | 800×800 | รูปโปรไฟล์ (ไอคอนหลอดไฟ ไม่มีคน) | ⏳ ต้องอัปโหลดใน Studio (API ไม่มี) |

## ทำซ้ำ

```
python3 scripts/make_branding.py --style knowledge \
  --out-dir assets/branding/ch4 \
  --title "เกร็ดความรู้รอบตัว" --subtitle "เรื่องน่ารู้ชวนคิด · มีคำตอบให้ทุกวัน"
python3 scripts/test_ch4_branding.py     # ต้องผ่าน (สว่าง + มีสไตล์ knowledge)
```

## อัปโหลด (อวตารไม่มี API — ต้องทำใน Studio)

1. เปิด **studio.youtube.com** → เลือกช่อง **เกร็ดความรู้รอบตัว**
2. **Customization** → **Branding**
3. **Picture** → Change → อัปโหลด `avatar_800x800.jpg` · **Banner image** → อัปโหลด `banner_2560x1440.jpg`
4. **Publish**

**แบนเนอร์** ตั้งผ่าน API ได้ด้วย `scripts/set_channel_art.py --channel ch4`
(แต่ quota Data API หมดก่อน 08:00 UTC → ถ้า 403 ให้รอหลัง reset)
**อวตาร** ไม่มีเมธอดใดตั้งได้ (ตรวจ discovery document แล้ว: `profileImageUrl` read-only)

## ลิงก์ดาวน์โหลดตรง (สำหรับทำใน Studio บนเครื่อง K)

- อวตาร: https://raw.githubusercontent.com/kongkeat938/ai-content-lab/main/assets/branding/ch4/avatar_800x800.jpg
- แบนเนอร์: https://raw.githubusercontent.com/kongkeat938/ai-content-lab/main/assets/branding/ch4/banner_2560x1440.jpg
