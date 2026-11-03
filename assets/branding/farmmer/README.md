# Farmmer — ภาพแบรนด์ช่อง (ch2 @farmmer-n9t)

สร้างเมื่อ 2026-11-03 ด้วยเครื่องมือฟรีทั้งหมด: ภาพจาก Gemini เว็บ + ตัวอักษรจาก
`scripts/make_branding.py` และ `scripts/make_thumbnail.py` (ฟอนต์ Kanit/Prompt ใน
`assets/fonts/`).

| ไฟล์ | ขนาด | ใช้ที่ไหน | สถานะ |
|---|---|---|---|
| `banner_2560x1440.jpg` | 2560×1440 | ภาพแบนเนอร์ช่อง | **เผยแพร่แล้ว** |
| `avatar_800x800.png` | 800×800 | รูปโปรไฟล์ | **เผยแพร่แล้ว** |
| `thumbs/<video_id>.jpg` | 1280×720 | ภาพปกคลิปยาว 6 คลิป | รอติดตั้ง (ดูด้านล่าง) |

## ติดตั้งภาพปกเองผ่าน Studio ไม่ได้ — แต่ติดตั้งผ่าน API ได้

กดปุ่ม "อัปโหลดไฟล์" ใน Studio แล้วขึ้นไดอะล็อก **"สร้างประวัติของช่อง"** ทุกครั้ง
ลิงก์ในไดอะล็อกคือ `support.google.com/youtube/?p=rfa_no_idv` = ต้องยืนยันเบอร์โทร
ก่อน ช่องใหม่จึงยังติดตั้งภาพปกเองจาก UI ไม่ได้

**ทางแก้ที่ทำงานได้จริงโดยไม่ต้องรอใคร:** YouTube Data API `thumbnails.set` ไม่ติด
เงื่อนไขนั้น ใช้แค่ refresh token (ตั้งเป็น repo secret แล้ว) และมีโควตารายวันแยก
100 ครั้ง ไม่นับรวม 10,000 units ที่ตัวอื่นใช้

```
python3 scripts/set_thumbnails.py --dry-run     # ดูว่าจะตั้งอะไร
python3 scripts/set_thumbnails.py               # ตั้งทุกคลิปใน manifest
python3 scripts/set_thumbnails.py --check       # ดูว่าติดตั้งไปหรือยัง
```

`.github/workflows/set-thumbnails.yml` รัน `set_thumbnails.py` เองทุกวัน
08:07/09:07/10:07/11:07 UTC (หลังโควตารีเซ็ตเที่ยงคืนแปซิฟิก = 08:00 UTC) และรัน
เมื่อ manifest หรือไฟล์ภาพเปลี่ยน `thumbnails.set` เป็น idempotent รันซ้ำได้ไม่มีผลเสีย

manifest: `content/ch2_thumbnails.json` (video_id → ไฟล์ภาพ) เพิ่มคลิปใหม่ได้เลย
workflow จะติดตั้งให้เองในรอบถัดไป

## ทำซ้ำ / ทำช่องอื่น

```
python3 scripts/make_branding.py \
  --banner-art <ภาพดิบ> --avatar-art <ภาพดิบ> --out-dir <โฟลเดอร์ออก> \
  --title "Farmmer" --subtitle "ธรรมะก่อนนอน" \
  --tagline "วางความทุกข์ไว้ตรงนี้ แล้วพักใจให้สบาย"

python3 scripts/make_thumbnail.py --art <ภาพดิบ> --out <ออก.jpg> \
  --line "หยุดคิด" --line "แล้วพักใจ"
```
