# เกร็ดความรู้รอบตัว (ch4 @OonjaistoryTH) — ภาพแบรนด์ช่อง

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
