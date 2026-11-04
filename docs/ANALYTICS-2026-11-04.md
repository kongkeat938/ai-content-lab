# ตัวเลขวัดจริงจาก YouTube Analytics — 2026-11-04

ที่มา: `scripts/analytics.py` (รันด้วย token เดิม scope `youtube`). นี่คือ **watch-hour จริง**
ไม่ใช่การเดาจาก duration × views.

## ช่อง (28 วัน / 365 วัน)

| ช่อง | วิว 28ด | watch-h 28ด | watch-h 365ด | subs +28ด | subs รวม |
|---|---|---|---|---|---|
| genx (ตาต้า) | 2,036 | 9.3 | 10.2 | +5 | 26 |
| dharma (Farmmer) | 4,185 | 8.5 | 8.5 | +12 | 22 |
| kongkeat | 2,088 | 12.3 | 12.3 | +6 | 7 |
| **รวม** | **8,309** | **30.1** | **31.0** | **+23** | **55** |

**watch-hour/วิว = 31 / 20,015 = 0.0015** — วิวส่วนใหญ่ดูไม่จบ.

## คลิปที่เก็บ watch-hour สูงสุด (เรียงจริง)

| คลิป | ช่อง | วิว | watch-h | avg view % |
|---|---|---|---|---|
| `udi7bekVJiA` | kongkeat | 1,083 | **8.12** | 103.6% ⟳ |
| `WA8g6zCiMmo` | genx | 914 | **6.70** | 353.7% ⟳ |
| `g0eWYjCEYTc` | kongkeat | 460 | **3.10** | 115.1% ⟳ |
| `oyrWvxdnImY` | dharma | 1,239 | 2.85 | 115.4% ⟳ |
| `oIsloIKa0J4` | dharma | 1,302 | 2.72 | 56.4% |
| `CAIFSg_Edxg` | dharma | 23 | 0.07 | **289.9%** ⟳ |
| `exm1OwwngzI` | dharma | 24 | 0.03 | 104.7% ⟳ |

**⟳ = avg view % > 100% แปลว่าคนดูวนซ้ำ/ดูเกินความยาวคลิป.**

## บทเรียนที่วัดได้ (ไม่เดา)

1. **watch-hour มาจากคลิปที่ "วน"** — 4 ใน 5 คลิปที่ watch-h สูงสุดมี avg% > 100%.
2. **kongkeat ให้ watch-h/วิว สูงสุด** (0.0075) รองลงมา genx (0.0073) — dharma วิวเยอะแต่ดูสั้น (0.0021).
3. **ห้ามใช้ duration × views เป็นตัวแทน watch-hour** — มันเกินจริง 11 เท่า (348 vs 31).

## ข้อจำกัดที่ยืนยันแล้ว

- `impressions` / `impressionClickThroughRate` = metric ไม่ถูกต้องใน API v2 → วัด CTR ตรง ๆ ไม่ได้.
- **comment API (commentThreads) = 403 insufficient scope** → ตั้ง pinned comment ผ่าน API ไม่ได้
  (ต้องใช้ scope `youtube.force-ssl` ซึ่ง token เราไม่มี). ทางที่ทำได้คือ **ใส่ funnel ใน description** แทน.
