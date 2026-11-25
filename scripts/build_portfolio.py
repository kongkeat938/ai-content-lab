#!/usr/bin/env python3
"""Build the public portfolio page from the price file and the sample list.

    python3 scripts/build_portfolio.py           # write docs/portfolio/index.html
    python3 scripts/build_portfolio.py --check   # fail if the page is stale

The page is generated so a price change cannot leave the website quoting an old
number: `--check` rebuilds in memory and compares, and CI runs it. Nothing on the
page claims a client, a testimonial or a result we cannot show.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "portfolio", "index.html")
MEDIA = os.path.join(ROOT, "docs", "portfolio", "media")
SAMPLES = (
    ("sample_product_45s.mp4", "วิดีโอขายสินค้า 45 วินาที",
     "โครง 6 ฉาก: เปิดสินค้า → จุดเด่น → รีวิว → ราคา → วิธีสั่ง → ปิดการขาย · เสียงบรรยายไทย"),
    ("sample_promo_20s.mp4", "โปรโมทสั้น 20 วินาที",
     "ตัวหนังสือเคลื่อนไหว 4 ฉาก ตัดจังหวะเร็ว · ไม่ใช้เสียงบรรยาย (เพลงประกอบสร้างเอง)"),
    ("sample_still_30s.mp4", "ภาพนิ่ง + ข้อความ + เสียงบรรยาย 30 วินาที",
     "4 ภาพ ข้อความพาดหัว และคำบรรยายใต้ภาพ · เหมาะกับสินค้าที่ยังไม่มีวิดีโอ"),
)


def page(packs: dict) -> str:
    pk = packs["packages"]
    rows = "\n".join(
        f"      <tr{' class=\"primary\"' if p.get('primary') else ''}>"
        f"<td>{p['name_th']}</td><td>{p['clips']} คลิป</td>"
        f"<td><b>{p['price']:,} บาท</b></td>"
        f"<td>{p['price'] / p['clips']:.0f} บาท/คลิป</td>"
        f"<td>{'แนะนำ' if p.get('primary') else ('ทดลอง' if p['id'] == 'A' else 'เปิดเมื่อส่งงานครบ 3 ออเดอร์')}</td></tr>"
        for p in pk)
    vids = "\n".join(
        f"""    <figure>
      <video controls preload="metadata" playsinline poster="">
        <source src="media/{f}" type="video/mp4">
      </video>
      <figcaption><b>{title}</b><br><span>{desc}</span></figcaption>
    </figure>"""
        for f, title, desc in SAMPLES)
    return f"""<!doctype html>
<html lang="th">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>รับตัดคลิปสั้นจากคลิปยาว · 9:16 · 30-60 วินาที</title>
<meta name="description" content="รับตัดคลิปแนวตั้ง 9:16 ยาว 30-60 วินาที จากไฟล์ต้นฉบับของคุณ พร้อมพาดหัว คำบรรยายใต้ภาพ และ thumbnail · แพ็ก 10 คลิป {next(p['price'] for p in pk if p.get('primary')):,} บาท">
<style>
  :root {{ --ink:#0f1420; --muted:#5a6478; --line:#e3e7ef; --accent:#0b5fff; --bg:#ffffff; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; font-family:"Noto Sans Thai",system-ui,-apple-system,"Segoe UI",sans-serif;
         color:var(--ink); background:var(--bg); line-height:1.65; }}
  header {{ padding:56px 20px 32px; max-width:980px; margin:0 auto; }}
  h1 {{ font-size:clamp(26px,5vw,42px); margin:0 0 12px; letter-spacing:-.01em; }}
  .lead {{ font-size:clamp(16px,2.4vw,20px); color:var(--muted); margin:0; }}
  .badges {{ display:flex; gap:8px; flex-wrap:wrap; margin-top:20px; }}
  .badge {{ border:1px solid var(--line); border-radius:999px; padding:6px 14px; font-size:14px; color:var(--muted); }}
  main {{ max-width:980px; margin:0 auto; padding:0 20px 80px; }}
  section {{ padding:36px 0; border-top:1px solid var(--line); }}
  h2 {{ font-size:clamp(20px,3vw,26px); margin:0 0 18px; }}
  .grid {{ display:grid; gap:20px; grid-template-columns:repeat(auto-fit,minmax(240px,1fr)); }}
  figure {{ margin:0; background:#0b0e14; border-radius:16px; overflow:hidden; }}
  video {{ width:100%; display:block; aspect-ratio:9/16; background:#0b0e14; }}
  figcaption {{ padding:14px 16px 18px; background:#fff; font-size:15px; }}
  figcaption span {{ color:var(--muted); font-size:14px; }}
  table {{ width:100%; border-collapse:collapse; font-size:15px; }}
  th,td {{ text-align:left; padding:12px 10px; border-bottom:1px solid var(--line); }}
  th {{ color:var(--muted); font-weight:600; font-size:14px; }}
  tr.primary td {{ background:#f3f7ff; }}
  ul {{ padding-left:20px; }}
  .note {{ background:#f7f8fb; border:1px solid var(--line); border-radius:12px; padding:16px 18px; font-size:14px; color:var(--muted); }}
  ol.steps li {{ margin-bottom:10px; }}
  footer {{ max-width:980px; margin:0 auto; padding:24px 20px 60px; color:var(--muted); font-size:13px; }}
</style>
</head>
<body>
<header>
  <h1>รับตัดคลิปสั้นจากคลิปยาว</h1>
  <p class="lead">ส่งไฟล์ต้นฉบับมา รับคลิปแนวตั้ง 9:16 ยาว 30-60 วินาที พร้อมพาดหัว
     คำบรรยายใต้ภาพ และภาพปก — พร้อมโพสต์</p>
  <div class="badges">
    <span class="badge">9:16 · 1080×1920</span>
    <span class="badge">30-60 วินาที</span>
    <span class="badge">แก้ไข {packs['revisions']} ครั้ง/คลิป</span>
    <span class="badge">{packs['turnaround']}</span>
    <span class="badge">ไม่ต้องจองคิวนาน</span>
  </div>
</header>

<main>
  <section>
    <h2>ตัวอย่างงาน 3 แบบ</h2>
    <div class="grid">
{vids}
    </div>
    <p class="note" style="margin-top:20px">{packs['samples_note']}
      ทุกภาพและเสียงในตัวอย่างสร้างขึ้นเอง ไม่มีฟุตเทจหรือเพลงจากแหล่งใด</p>
  </section>

  <section>
    <h2>ราคา</h2>
    <table>
      <thead><tr><th>แพ็ก</th><th>จำนวน</th><th>ราคา</th><th>ต่อคลิป</th><th>หมายเหตุ</th></tr></thead>
      <tbody>
{rows}
      </tbody>
    </table>
    <p class="note" style="margin-top:16px">ราคานี้คือราคาที่ตกลงกันก่อนเริ่มงาน
      ไม่มีค่าใช้จ่ายเพิ่มระหว่างทาง · ไฟล์ต้นฉบับของคุณยังเป็นของคุณ</p>
  </section>

  <section>
    <h2>ขอบเขตงาน</h2>
    <ul>
      <li>{packs['scope_th']}</li>
      <li>ระยะเวลาส่งงาน: {packs['turnaround']}</li>
      <li>สิ่งที่ต้องเตรียม: ไฟล์ต้นฉบับ (หรือลิงก์) + ตัวอย่างคลิปที่ชอบ 1 คลิป</li>
      <li>สิ่งที่ไม่รวม: ถ่ายทำ, ซื้อฟุตเทจ, ภาพบุคคล, เพลงลิขสิทธิ์</li>
    </ul>
  </section>

  <section>
    <h2>ขั้นตอนการจ้าง</h2>
    <ol class="steps">
      <li>ส่งไฟล์ต้นฉบับและโจทย์ (สินค้า/กลุ่มผู้ชม/ความยาวที่ต้องการ)</li>
      <li>ผมตัด <b>คลิปแรก</b> ส่งให้ดูก่อน — ไม่ถูกใจไม่ต้องจ่าย</li>
      <li>อนุมัติแนวทาง → ส่งคลิปที่เหลือภายในเวลาที่แจ้ง</li>
      <li>แก้ไขได้ {packs['revisions']} ครั้ง/คลิป แล้วปิดงาน</li>
    </ol>
  </section>

  <section>
    <h2>คำถามที่พบบ่อย</h2>
    <p><b>ไม่มีวิดีโอ มีแต่รูปสินค้า?</b> ทำได้ — ดูตัวอย่างที่ 3 (ภาพนิ่ง + ข้อความ + เสียงบรรยาย)</p>
    <p><b>อยากได้เสียงบรรยายภาษาไทย?</b> มีให้ในทุกรูปแบบ คลิปตัวอย่างที่ 1 และ 3 มีเสียงบรรยายจริง</p>
    <p><b>ส่งงานทางไหน?</b> ส่งเป็นไฟล์ MP4 ผ่านช่องทางที่คุณสะดวก</p>
  </section>
</main>

<footer>
  หน้านี้สร้างจาก <code>content/packages.json</code> ด้วย <code>scripts/build_portfolio.py</code> ·
  อัปเดตราคา {packs['updated']} · ไม่มีข้อมูลลูกค้าหรือคำรับรองที่ไม่มีหลักฐานในหน้านี้
</footer>
</body>
</html>
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    with open(os.path.join(ROOT, "content", "packages.json"), encoding="utf-8") as fh:
        packs = json.load(fh)
    html = page(packs)
    if a.check:
        if not os.path.exists(OUT):
            print("FAIL: the portfolio page has never been built")
            return 1
        with open(OUT, encoding="utf-8") as fh:
            if fh.read() != html:
                print("FAIL: docs/portfolio/index.html is stale — run scripts/build_portfolio.py")
                return 1
        print("OK: the page matches content/packages.json")
        return 0
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(html)
    missing = [f for f, _, _ in SAMPLES if not os.path.exists(os.path.join(MEDIA, f))]
    print(f"wrote {os.path.relpath(OUT, ROOT)}"
          + (f" (samples missing: {', '.join(missing)})" if missing else " (3 samples present)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
