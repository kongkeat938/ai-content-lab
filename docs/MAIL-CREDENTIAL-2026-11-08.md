# เก็บรหัสผ่านเมล์ยังไง (K ถาม 2026-11-08)

K: *"จะกรอกรหัสผ่านเมล์ไว้ให้ใช้ แต่จะกรอกให้ครั้งเดียว ... รหัสนี้ใช้กับทุกบัญชี"*

## คำตอบสั้น

**เก็บที่ GitHub Repository Secret** (ไม่ใช่ไฟล์ในเครื่อง, ไม่ใช่ใน git — repo นี้ **public**).
ใส่ **ครั้งเดียว** ในชื่อ `IMAP_ACCOUNTS` แล้วใส่ได้ทุกบัญชีในค่าเดียว. โค้ดพร้อมใช้แล้ว
(`scripts/mail_watch.py`) + มีเทสต์กันรหัสหลุด.

## ⚠️ ความจริงที่ต้องรู้ก่อน: "รหัสเดียวใช้ได้ทุกบัญชี" ไม่มีใน Gmail

Google ไม่ยอมให้ใช้ "รหัสผ่านเมล์ตัวจริง" ผ่าน IMAP — **ต้องเป็น App Password** และ
App Password ของ Google **ผูกกับบัญชีเดียว** (ยืนยันจากเอกสาร Google, 2026-11-08:
*"An app password is a 16-digit passcode that gives a less secure app ... access to your
Google Account"*, *"can only be used with 2-Step Verification"*). **ฉะนั้น:**

- ถ้า K หมายถึง **รหัสผ่าน login ตัวจริงที่ใช้ซ้ำทุกบัญชี** → ใช้กับ IMAP ไม่ได้
- สิ่งที่ทำได้ = **1 บัญชี 1 App Password** แต่ใส่ทุกตัวใน **secret เดียว** ⇒ K ยังกรอกครั้งเดียว

## ทางเลือก (เรียงตามแนะนำ)

| # | วิธี | ต้องมี | ข้อดี |
|---|---|---|---|
| 1 | **App Password ต่อบัญชี** ใส่ใน secret `IMAP_ACCOUNTS` อันเดียว | เปิด 2FA ทุกบัญชี + สร้าง app password | ได้ทุกบัญชี, เต็มความสามารถ, ไม่มีรหัสใน git |
| 2 | **Gmail Delegation** — ให้บัญชีหลักอ่านเมล์ของบัญชีอื่น | ตั้งค่าใน Gmail ของแต่ละบัญชี | อ่านได้ทุกกล่องจากที่เดียว |
| 3 | ไม่อ่านเมล์ (ใช้ layer 1) | ไม่ต้องทำอะไร | Data API จับคลิปถูกระงับ/ลบ อยู่แล้ว |

> แนะนำ **#1** — ตรงกับที่ K ต้องการ (กรอกครั้งเดียว) และปลอดภัยสุด.

## วิธีใส่ (มือถือ — กดลิงก์เดียวแล้วกรอก)

**กดลิงก์นี้** (เปิดหน้า GitHub ตรง ๆ):

👉 **https://github.com/kongkeat938/ai-content-lab/settings/secrets/actions/new**

1. ช่อง **Name** พิมพ์: `IMAP_ACCOUNTS`
2. ช่อง **Secret** วาง (บรรทัดละบัญชี — รูปแบบง่ายสุดสำหรับพิมพ์มือถือ):
```
kongkeat.938@gmail.com:xxxx xxxx xxxx xxxx
farmmer.938@gmail.com:xxxx xxxx xxxx xxxx
kongkeat.p3@gmail.com:xxxx xxxx xxxx xxxx
```
   แทน `xxxx xxxx xxxx xxxx` ด้วย App Password จริงของบัญชีนั้น
3. กด **Add secret** → เสร็จ

> รับได้ 3 แบบ: **บรรทัดละบัญชี** (`user:รหัส`), JSON list, หรือ JSON map — เลือกอันที่พิมพ์ง่ายสุด
> (บรรทัดที่ไม่มี `:` จะถูกข้าม ไม่เดา)

สร้าง App Password (ทำต่อบัญชี): 👉 **https://myaccount.google.com/apppasswords**
(ต้องเปิด 2-Step Verification ก่อน; คัดลอกได้ครั้งเดียวตอนสร้าง — วางใส่ secret ทันที)

### ถ้าไม่อยากพิมพ์เอง — ให้ ak ใส่ให้ได้
โทเคน `KONGKEAT_GH_TOKEN` ใน pod **เขียน secret ให้ได้** (วัดแล้ว 2026-11-08:
set + delete สำเร็จ). ทางเลือก:
- K บอก App Password ในแชท → ak รัน `gh secret set IMAP_ACCOUNTS` ให้ทันที
- **ข้อควรรู้:** ค่าที่พิมพ์ในแชทจะอยู่ในประวัติบทสนทนา (log) — ถ้าเลี่ยงได้ ให้ใช้ลิงก์ข้างบนปลอดภัยกว่า

## วิธีใส่ (เดิม: GitHub UI เต็ม)

1. เปิด `https://github.com/kongkeat938/ai-content-lab/settings/secrets/actions`
2. กด **New repository secret**
3. **Name:** `IMAP_ACCOUNTS`
4. **Secret:** วาง JSON นี้ (แก้รหัสเป็น app password จริงของแต่ละบัญชี):
```json
[
  {"user": "kongkeat.938@gmail.com", "app_password": "xxxx xxxx xxxx xxxx"},
  {"user": "farmmer.938@gmail.com",  "app_password": "xxxx xxxx xxxx xxxx"},
  {"user": "kongkeat.p3@gmail.com",  "app_password": "xxxx xxxx xxxx xxxx"}
]
```
5. กด **Add secret** → เสร็จ. งาน `account-watch` (รันทุกวัน 08:42 UTC) จะอ่านเมล์ทุกกล่องให้


## ✅ ผลทดสอบจริง (2026-11-08 04:33Z) — ระบบอ่าน secret ได้แล้ว แต่ Gmail ปฏิเสธรหัส

รันงาน `account-watch` จริง → อ่าน `IMAP_ACCOUNTS` ได้ → ลอง login **ครบทั้ง 3 บัญชี** →
Gmail ตอบกลับ**เหมือนกันทั้ง 3**:

```
IMAP failed for kongkeat.938@gmail.com: this account requires an app password
(the normal login password is refused) -- create one at
https://myaccount.google.com/apppasswords
```

**แปลว่า:** รหัสที่ใส่ = **รหัสผ่าน login ตัวจริง** ซึ่ง Gmail **ห้ามใช้ผ่าน IMAP** (ตามที่เตือน)
⇒ **ต้องสร้าง App Password แทน** — และเพราะ app password ผูกกับบัญชีเดียว
ถ้า 3 บัญชีใช้รหัส login เดียวกัน ก็ยังต้องสร้าง **3 app password**

> หมายเหตุ: Google **ยกเลิก** "Less secure app access" ไปแล้ว (2022) — ไม่มีทางลัดให้ใช้รหัส login

## 🔑 ขั้นตอนที่ K ต้องทำ (มือถือ)

ทำ 3 ครั้ง (บัญชีละครั้ง):
1. เปิด 👉 **https://myaccount.google.com/apppasswords** (บัญชีนั้น)
   - ถ้ายังไม่เปิด 2-Step Verification → เปิดก่อนที่ `myaccount.google.com/security`
2. ตั้งชื่อ เช่น `ai-content-lab` → กด **Create**
3. **คัดลอกรหัส 16 หลัก** ที่ขึ้นมา (คัดลอกได้ครั้งเดียว)

จากนั้นแก้ secret `IMAP_ACCOUNTS` เป็น (บรรทัดละบัญชี):
```
kongkeat.938@gmail.com:<app password ของบัญชีนี้>
farmmer.938@gmail.com:<app password ของบัญชีนี้>
kongkeat.p3@gmail.com:<app password ของบัญชีนี้>
```
(แก้ที่ 👉 https://github.com/kongkeat938/ai-content-lab/settings/secrets/actions → กด `IMAP_ACCOUNTS` → **Update**)

**หรือให้ ak ใส่ให้:** ส่ง app password ทั้ง 3 มาในแชท แล้ว ak รัน `gh secret set IMAP_ACCOUNTS` ให้ทันที

## ปลอดภัยแค่ไหน (วัดแล้ว)

| คำถาม | คำตอบ |
|---|---|
| รหัสจะหลุดลง git ไหม | **ไม่** — เก็บใน GitHub Secret เท่านั้น; เทสต์ `test_mail_credentials.py` ยืนยันว่ารหัสไม่โผล่ในรายงาน |
| Agent อ่านรหัสกลับได้ไหม | **ไม่ได้** — GitHub Secret เป็น write-only (อ่านกลับไม่ได้) |
| โผล่ใน log ไหม | ไม่ — GitHub mask ค่า secret ใน log อัตโนมัติ |
| รายงานที่ commit ลง public เก็บอะไร | แค่ "มีอีเมลเตือน N ฉบับ" — **ไม่เก็บผู้ส่ง/หัวเรื่อง**; รายละเอียดไปไฟล์ส่วนตัวนอก repo |

## ถ้าไม่อยากให้รหัสผ่านบัญชีเลย (ทางเลือกที่ปลอดภัยสุด)

เพิ่ม scope `https://www.googleapis.com/auth/gmail.readonly` ตอนทำ OAuth consent แล้วใช้
**refresh token อ่านเมล์** (เหมือนที่ทำกับ YouTube อยู่แล้ว) — ไม่มีรหัสผ่านเก็บเลย.
แต่ต้องทำ OAuth flow ใหม่ต่อบัญชี ⇒ **#1 เร็วกว่า** จึงแนะนำ #1 ก่อน.

## ไฟล์ที่เกี่ยว

- `scripts/mail_watch.py` — อ่าน `IMAP_ACCOUNTS` (หรือ `IMAP_USER`/`IMAP_APP_PASSWORD` แบบเดิม)
- `scripts/test_mail_credentials.py` — guard: secret เดียว→หลายบัญชี, กันรหัสหลุด
- `.github/workflows/account-watch.yml` — ส่ง secret เข้างานรายวัน
