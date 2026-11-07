# เรื่องเล่าอบอุ่นใจ (ch4 @OonjaistoryTH) — ภาพแบรนด์ช่อง

สร้างเมื่อ 2026-11-07 ด้วยเครื่องมือฟรีทั้งหมด: ภาพจากคลัง Commons/Flickr ที่รีโปมีอยู่แล้ว
(`assets/images/`) + ตัวอักษรและเอฟเฟกต์จาก `scripts/make_branding.py`
(ฟอนต์ Kanit/Prompt ใน `assets/fonts/`).

สไตล์ **lavish** (อลังการ): เกรดสีอุ่นแบบฟิล์ม + spotlight กลางภาพ + กรอบทอง
 ornaments มุม + ชื่อเรื่องสีทองเรืองแสง + เกรนฟิล์มบาง ๆ

| ไฟล์ | ขนาด | ใช้ที่ไหน | สถานะ |
|---|---|---|---|
| `banner_2560x1440.jpg` | 2560×1440 | ภาพแบนเนอร์ช่อง | ✅ **ติดตั้งผ่าน API แล้ว** |
| `avatar_800x800.jpg` | 800×800 | รูปโปรไฟล์ | ⏳ ต้องอัปโหลดเองใน Studio (API ไม่มี) |

## แบนเนอร์ติดตั้งผ่าน API ได้ — อวตารไม่ได้

- **แบนเนอร์:** `scripts/set_channel_art.py --channel ch4` อัปโหลดผ่าน
  `channelBanners.insert` แล้วผูกด้วย `channels.update?part=brandingSettings`
  (ส่ง `brandingSettings.channel` เดิมกลับทั้งก้อน ไม่งั้น description/keywords หาย)
  → **ติดตั้งให้แล้ว 2026-11-07**
- **อวตาร:** YouTube ไม่มี API สำหรับรูปโปรไฟล์ (ไม่ใช่ฟิลด์ที่เขียนได้ใน
  `brandingSettings` และไม่มีเมธอดอัปโหลด) → **ต้องเปลี่ยนใน Studio**

## ขั้นตอนอัปโหลดอวตารเอง (K ทำ 2 นาที)

1. เปิด **studio.youtube.com** → เลือกช่อง **เรื่องเล่าอบอุ่นใจ**
2. เมนูซ้าย **Customization** → แท็บ **Branding**
3. หัวข้อ **Picture** → **Change** → อัปโหลดไฟล์ `avatar_800x800.jpg` จากโฟลเดอร์นี้
4. **Publish**

## เครดิตภาพ (ต้องคงไว้ — ใบอนุญาต BY 2.0 ต้องให้เครดิต)

| ไฟล์ที่ใช้ | ชื่อภาพ | ผู้สร้าง | ใบอนุญาต | แหล่ง |
|---|---|---|---|---|
| `img00_00.jpg` (แบนเนอร์) | Chanukah: First Candle | Flavio~ | CC BY 2.0 | https://www.flickr.com/photos/37873897@N06/4177957143 |
| `img02_01.jpg` (อวตาร) | Richmond Lock and Weir (Apr 2011) | Gareth1953 All Right Now | CC BY 2.0 | https://www.flickr.com/photos/40837632@N05/5637639901 |

## ทำซ้ำ / ทำช่องอื่น

```
python3 scripts/make_branding.py \
  --banner-art <ภาพดิบ> --avatar-art <ภาพดิบ> --out-dir assets/branding/<ช่อง> \
  --title "..." --kicker "..." --subtitle "..." --style lavish
python3 scripts/set_channel_art.py --channel <ch1|ch2|ch4>
```

## ดาวน์โหลดอวตารไปที่เครื่อง Windows (ลิงก์ตรง)

ไฟล์อยู่ใน pod ไม่ได้อยู่ในเครื่อง K — ดาวน์โหลดจากลิงก์นี้ได้เลย:

- **อวตาร 800×800:** https://raw.githubusercontent.com/kongkeat938/ai-content-lab/main/assets/branding/ch4/avatar_800x800.jpg
- แบนเนอร์ (ติดตั้งบนช่องแล้ว): https://raw.githubusercontent.com/kongkeat938/ai-content-lab/main/assets/branding/ch4/banner_2560x1440.jpg

เปิดลิงก์อวตารในเบราว์เซอร์ → คลิกขวา → **Save image as…** (หรือกด Ctrl+S)

## ทำไมอวตารต้องทำใน Studio (พิสูจน์แล้ว)

ดึง discovery document ทางการ (`googleapis.com/discovery/v1/apis/youtube/v3/rest`) แล้ว:
เมธอดอัปโหลดรูปมีแค่ `channelBanners` · `thumbnails` · `playlistImages` เท่านั้น
ส่วน `ChannelProfileDetails.profileImageUrl` เป็น **read-only** → **ไม่มีเมธอดใดตั้งอวตารได้**.
ทางอื่น: ขับเบราว์เซอร์ PC1 (ที่ล็อกอิน) ก็ลองแล้ว — ปลายทางตอบ **502** (ออฟไลน์).
→ **เหลือทางเดียว = Studio** (ตรงกับที่ YouTube Help ระบุไว้).
