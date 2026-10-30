# RUNBOOK — ทำอย่างไรให้ "งานคุณภาพต่อเนื่อง"

คู่มือทำซ้ำได้ ทุกขั้นมีคำสั่งจริงและเกณฑ์ที่วัดได้ ไม่ใช่ความเห็น
อ่านคู่กับ `COMPETITOR-STRATEGY.md` (กลยุทธ์) และ `docs/GOAL.md` (โจทย์)

---

## วงจรต่อ 1 ตอน (ทำตามนี้ทุกครั้ง)

```
1. CLAIM        python3 scripts/claims.py claim ep03 --as <account> --push
2. COPYRIGHT    ยืนยันผู้แต่งเสียชีวิต > 50 ปี + แหล่งอ้างอิง → docs/CONTENT-PLAN.md
3. SCRIPT       เขียน narration_th.txt (1 ประโยค/บรรทัด, เลขเป็นคำไทย)
4. AUDIO        python3 scripts/make_audio.py ...  → ได้ -14 LUFS / TP ≤ -3
5. IMAGES       python3 scripts/fetch_images.py queries.json assets/images
6. VIDEO        python3 scripts/make_video.py episodes/<ep>
7. PACKAGING    แก้ episodes/<ep>/meta.json ตามสูตร §5.2 ของกลยุทธ์
8. CHANNEL      python3 scripts/build_api.py
9. GATE         python3 work/research/quality_gate.py episodes/<ep> --channel chX
                → ต้อง 0 hard failure ก่อนไปต่อ
10. RELEASE     scripts/publish_release.sh episodes/<ep>   (URL ถาวร)
11. PUBLISH     scripts/publish_episode.sh episodes/<ep> private
12. RECORD      python3 scripts/claims.py done <ep> --as <account> --url <link>
```

**ขั้นที่ 9 ห้ามข้าม.** ขั้นนี้คือสิ่งที่ทำให้ "คุณภาพต่อเนื่อง" เป็นจริง —
มันเปลี่ยนคำว่า "น่าจะโอเค" ให้เป็นตัวเลขที่ตรวจได้

---

## ก่อนบอกว่า "เสร็จ" — เช็กลิสต์

รัน `quality_gate.py` แล้วดูว่า **ไม่มี ✗** ที่ระดับ FAIL อย่างน้อยต้องผ่าน:

- [ ] `narration.no-digits` — ไม่มีเลขอารบิกในสคริปต์
- [ ] `timing.all-lines-matched` — ทุกบรรทัดมี timing ครบ (n/n)
- [ ] `audio.lufs` — อยู่ที่ -14 ± 1 LUFS
- [ ] `audio.true-peak` — ≤ -3 dBFS
- [ ] `scenes.images-exist` — ภาพทุกการ์ดมีจริง
- [ ] `packaging.title` — ไม่เกิน 100 ตัวอักษร
- [ ] `packaging.source` + `packaging.attribution` — มีครบ (กฎข้อ 2 และ 4)
- [ ] `video.pix-fmt=yuv420p` + `video.color-range=tv` (ถ้า build video ในเครื่องนี้)

WARN ที่ควรเก็บให้หมด (ไม่บังคับแต่มีผลกับ discovery):
- [ ] `packaging.tags` ≥ 5 · `packaging.hook` ≥ 20 ตัวอักษร
- [ ] `audio.length` อยู่ในช่วงเป้าของช่อง
- [ ] `narration.line-length` ไม่มีบรรทัดยาวเกิน 90 ตัวอักษร

---

## วัดผลทุก 2 สัปดาห์

```bash
# 1) รีเฟรชข้อมูลคู่แข่ง (เผื่อตลาดขยับ)
python3 work/research/collect.py

# 2) วัดช่องเราเทียบเป้า
python3 work/research/measure.py
```

`measure.py` พิมพ์ median views ของ 50 อัปโหลดล่าสุดของเราแต่ละช่อง เทียบเป้าใน §6
ของกลยุทธ์ พร้อม views-per-subscriber เทียบกับคู่แข่งอ้างอิง (`hiphoplanla` = 5.4%)

**ตัดสินจาก median ไม่ใช่ยอดรวม** — คลิปเดียวที่พุ่งบอกว่า hook ดี แต่ยังทำซ้ำไม่ได้

---

## นิยาม "คุณภาพ" ของโปรเจกต์นี้ (จาก docs/GOAL.md)

1. **เนื้อหา** — วรรณคดีไทยสาธารณสมบัติ ผู้แต่งเสียชีวิต > 50 ปี (มีหลักฐาน)
2. **เสียง** — -14 LUFS, true peak ≤ -3 dBFS, เพลงใต้เสียงแบบ duck
3. **ภาพ** — การ์ดโปสเตอร์ ไม่มีข้อความล้น 1920×1080 yuv420p tv
4. **จังหวะ** — ทุกบรรทัดมี timing, จุดตัดฉากตรงบรรทัดที่เปิดฉาก
5. **แพ็กเกจจิ้ง** — ชื่อ/คำอธิบาย/แท็ก ตามสูตรที่วัดได้ (§5.2)
6. **ความสม่ำเสมอ** — 1 long-form/สัปดาห์ + 2–3 Shorts ต่อช่อง

ข้อ 1–5 ตรวจด้วย `quality_gate.py` ได้ ข้อ 6 ตรวจด้วย `measure.py` + วินัยการปล่อย

---

## เมื่อ gate ล้ม — แก้ที่ต้นเหตุ ไม่ใช่ปิด gate

| อาการ | ต้นเหตุที่พบบ่อย | แก้ |
|---|---|---|
| `narration.no-digits` ล้ม | พิมพ์เลขในสคริปต์ | เขียนเป็นคำไทย (ดู `docs/RECIPE.md`) |
| `timing.all-lines-matched` < 100% | บรรทัดถูกตัดคำตอน TTS / มีอักขระแปลก | ตรวจบรรทัดที่ไม่แมตช์ เขียนใหม่ให้ตรงเสียง |
| `audio.lufs` เพี้ยน | loudnorm รอบเดียว | ต้อง two-pass (`docs/RECIPE.md`) |
| `scenes.images-exist` ล้ม | ภาพยังไม่ fetch หรือ path ผิด | รัน `fetch_images.py` แล้วตรวจ `scenes.json` |
| `packaging.*` ล้ม | ยังไม่ใส่ `meta.json` | เติม `source`/`attribution`/`tags` |
| `video.matches-audio` ล้ม | ป้อนภาพนิ่งเข้า concat demuxer ตรง ๆ — มันตัดท้ายทิ้ง ~14 วิ | แก้แล้วใน `make_video.py` (encode การ์ดเป็นคลิปแล้วค่อย concat) |

---

## ตัด Short (ท่อดึงคนใหม่) — `make_short.py`

long-form คือสินค้า, Short คือท่อที่พาคนแปลกหน้ามาหา มัน (กลยุทธ์ §5.3)

```bash
# ดูช่วงบรรทัดก่อน (วินาทีที่บรรทัดเริ่ม)
python3 - <<'PY'
import json; L=json.load(open("episodes/ep02_manthana_phatha/timing.json"))["lines"]
for i,l in enumerate(L[:12]): print(i, round(l["start"],1), l["text"])
PY
# ตัด 15-45 วิ (เครื่องมือบังคับ 10-59 วิ), 1080x1920 tv, เผาแคปชัน
python3 work/research/make_short.py episodes/ep02_manthana_phatha \
    --lines 4:9 --out site/media/ep02_short_hook.mp4 \
    --hook "เรื่องของดอกกุหลาบที่กลายเป็นหญิงสาว"
```

ผลลัพธ์: `1080x1920`, `yuv420p`, `color_range=tv`, มี `faststart`
(เช็กด้วย `ffprobe` ทุกครั้ง — ขนาดถูกไม่แปลว่า range ถูก)

## อัป Short ขึ้นช่อง — `scripts/publish_short.py`

`#Shorts` ในชื่อคือสิ่งที่บอก YouTube ว่าเป็น Short และ **ลิงก์ long-form ถูกดึง
จาก `receipts/receipts.jsonl` อัตโนมัติ** (เพราะฉะนั้นอัป long-form ให้เสร็จก่อน
Short จะได้มีปลายทางให้คนกด) ใช้ channel guard เดียวกับ `publish_youtube.py` —
token ผิดช่องจะถูกปฏิเสธก่อนอัป

```bash
# ดูสิ่งที่จะโพสต์ก่อน (ไม่ต้องมี token)
python3 scripts/publish_short.py ep02_manthana_phatha \
    --file site/media/ep02_short_hook.mp4 --channel ch4-story --privacy public --dry-run

# อัปจริง — public สำหรับ Short (มันคือท่อดึงคน, ต้องเห็นได้)
python3 scripts/publish_short.py ep02_manthana_phatha \
    --file site/media/ep02_short_hook.mp4 --channel ch4-story --privacy public \
    --base http://127.0.0.1:12000
```

`--base` คือ URL ของเซิร์ฟเวอร์ที่รันอยู่ ถ้าไม่ใส่ receipt จะถูกเขียนลงไฟล์ตรง ๆ
(ไม่ error) — เผื่อไว้ให้รันแบบไม่มีเซิร์ฟเวอร์ได้
