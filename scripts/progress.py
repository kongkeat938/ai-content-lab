#!/usr/bin/env python3
"""Report progress toward the goal, so the watching is visible.

K's ask (2026-11-07): show that the work is being done at full effort -- watched
and improved continuously. This turns the raw measurements into one page anyone
can read: how far each channel is from the YPP threshold (1,000 subs + 4,000
watch-hours) and from the $500/month target, and which way each number moved
since the last sample.

It reads docs/watch_hours.json (written by the watch-hours rail) and the public
subscriber counts, and writes docs/PROGRESS.md. With --issue it also opens or
updates one GitHub issue, so the report arrives without anyone opening a file.

    python3 scripts/progress.py                 # print
    python3 scripts/progress.py --write         # write docs/PROGRESS.md
    python3 scripts/progress.py --write --issue # also open/update the issue

No secrets needed: watch-hours come from the committed history, subscribers from
public pages (best effort; falls back to docs/subs.json).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# The goal, in one place.
SUBS_TARGET = 1000
HOURS_TARGET = 4000          # qualified watch-hours in 12 months (YPP)
REVENUE_TARGET = 500         # USD per month, per channel
RPM = 2.0                    # USD per 1,000 long-form views (Thai, mid estimate)

HANDLES = {
    "genx": "tatagenxgeny",
    "dharma": "farmmer-n9t",
    "kongkeat": "kongkeatpratumma",
}
LABEL = {"genx": "ตาต้า GenX", "dharma": "Farmmer", "kongkeat": "เรื่องเล่าการ์ตูน"}
ISSUE_TITLE = "ความคืบหน้าถึงเป้า $500/เดือน — รายงานล่าสุด"


def load(rel: str, default):
    path = os.path.join(ROOT, rel)
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def scrape_subs() -> dict:
    """Public subscriber counts, best effort. Falls back to docs/subs.json."""
    out = {}
    for slug, handle in HANDLES.items():
        try:
            req = urllib.request.Request(
                f"https://www.youtube.com/@{handle}",
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            html = urllib.request.urlopen(req, timeout=25).read().decode("utf-8", "replace")
            m = (re.search(r'"subscriberCountText":\{"simpleText":"([\d.,]+[KM]?)', html)
                 or re.search(r'([\d.,]+[KM]?)\s*subscribers', html))
            if m:
                raw = m.group(1).replace(",", "")
                mult = {"K": 1_000, "M": 1_000_000}.get(raw[-1:], 1)
                out[slug] = int(float(raw.rstrip("KM")) * mult)
        except Exception:
            pass
    if not out:
        out = load("docs/subs.json", {})
    return out


def build() -> dict:
    hist = load("docs/watch_hours.json", {"samples": []})
    samples = hist.get("samples", [])
    latest = samples[-1] if samples else {}
    prev = samples[-2] if len(samples) > 1 else None
    subs = scrape_subs()

    rows = []
    tot_h = tot_v = tot_s = tot_lf = 0
    for slug in HANDLES:
        ch = latest.get("channels", {}).get(slug, {})
        hours = ch.get("watch_hours", 0.0)
        # Only long-form counts toward the YPP 4,000-hour bar. A sample written
        # before the split existed has no longform field: fall back to the channel
        # total but mark it, so a stale sample is visible rather than silently
        # inflating the number (genx measured 39% vs a true 0.4%).
        lf = ch.get("longform_watch_hours")
        lf_exact = lf is not None
        lf = lf if lf_exact else hours
        views = ch.get("views", 0)
        s = subs.get(slug, 0)
        # A 28-day window scaled to a year is the honest annual pace this rail runs at.
        annual_lf = lf * 365 / max(latest.get("days", 28), 1)
        month_views = views * 30 / max(latest.get("days", 28), 1)
        rows.append({
            "slug": slug, "label": LABEL[slug], "subs": s, "hours": lf,
            "hours_all": hours, "lf_exact": lf_exact, "views": views,
            "annual_hours": annual_lf,
            "subs_pct": 100 * s / SUBS_TARGET,
            "hours_pct": 100 * annual_lf / HOURS_TARGET,
            "revenue": month_views / 1000 * RPM,
            "prev": (prev or {}).get("channels", {}).get(slug, {}),
        })
        tot_h += lf
        tot_v += views
        tot_s += s
        tot_lf += lf
    return {"measured_at": latest.get("measured_at", "?"), "days": latest.get("days", 28),
            "rows": rows, "total": {"subs": tot_s, "hours": tot_h, "views": tot_v},
            "samples": len(samples)}


def fmt(n: float) -> str:
    return f"{n:,.0f}" if abs(n) >= 10 else f"{n:,.1f}"


def render(d: dict) -> str:
    L = ["# ความคืบหน้าถึงเป้า — $500/เดือน/ช่อง", ""]
    L.append(f"วัดล่าสุด: {d['measured_at']} · หน้าต่าง {d['days']} วัน · "
             f"ตัวอย่างสะสม {d['samples']} ครั้ง")
    L.append("")
    L.append(f"เกณฑ์ YPP: **{SUBS_TARGET:,} subs + {HOURS_TARGET:,} watch-hours/12 เดือน** · "
             f"เป้ารายได้ **${REVENUE_TARGET}/เดือน/ช่อง** (ที่ RPM ${RPM:.0f})")
    L.append("")
    L.append("> **หมายเหตุสำคัญ:** คอลัมน์ watch-hours นับ **เฉพาะ long-form** เพราะ YPP วัดเฉพาะ "
             "long-form (Shorts มีเส้นทางแยก 10M วิว/90 วัน และ **ไม่นับ** เข้า 4,000 ชม.). "
             "ตัวเลขรวมทุกประเภทจะสูงเกินจริง — วัด 2026-11-09: genx รวม = 39% แต่ long-form จริง = **0.4%**")
    L.append("")
    L.append("| ช่อง | subs | ถึง 1,000 | ชม.ดู long-form/28วัน | เทียบ 4,000/ปี | ประมาณรายได้/เดือน |")
    L.append("|---|---:|---:|---:|---:|---:|")
    for r in d["rows"]:
        star = "" if r.get("lf_exact", True) else " *(รวม Shorts)*"
        L.append(f"| {r['label']} | {r['subs']:,} | {r['subs_pct']:.0f}% | "
                 f"{fmt(r['hours'])}{star} | {r['hours_pct']:.1f}% | ${r['revenue']:,.0f} |")
    t = d["total"]
    L.append(f"| **รวม** | **{t['subs']:,}** | **{100*t['subs']/SUBS_TARGET:.0f}%** | "
             f"**{fmt(t['hours'])}** | **{100*t['hours']*365/max(d['days'],1)/HOURS_TARGET:.1f}%** | — |")
    L.append("")
    L.append("## อ่านตัวเลขนี้ยังไง")
    L.append("- **ชม.ดู/28วัน → เทียบ 4,000/ปี** คือเข็มหลัก: ขยายหน้าต่าง 28 วันเป็นรายปี "
             "แล้วเทียบเป้า 4,000 ชั่วโมง")
    L.append("- **รายได้/เดือน** = วิวต่อเดือน ÷ 1,000 × RPM (ประมาณการ ไม่ใช่ตัวเลขจ่ายจริง)")
    L.append("- **Shorts ไม่นับ** watch-hours → เพิ่มได้จาก long-form ที่คนดูจนจบเท่านั้น")
    L.append("")
    L.append("_ไฟล์นี้สร้างอัตโนมัติโดย `scripts/progress.py` — ห้ามแก้ด้วยมือ_")
    return "\n".join(L) + "\n"


def upsert_issue(body: str) -> None:
    repo = os.environ.get("GITHUB_REPOSITORY", "kongkeat938/ai-content-lab")
    try:
        listed = subprocess.run(["gh", "issue", "list", "--repo", repo,
                                 "--state", "open", "--search", ISSUE_TITLE,
                                 "--json", "number,title"], capture_output=True,
                                text=True, check=True)
        for it in json.loads(listed.stdout or "[]"):
            if it["title"] == ISSUE_TITLE:
                subprocess.run(["gh", "issue", "comment", str(it["number"]),
                                "--repo", repo, "--body", body], check=True)
                print(f"updated issue #{it['number']}")
                return
        subprocess.run(["gh", "issue", "create", "--repo", repo,
                        "--title", ISSUE_TITLE, "--body", body], check=True)
        print("opened the progress issue")
    except Exception as exc:  # never fail the rail over a report
        print(f"issue update skipped: {exc}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true", help="write docs/PROGRESS.md")
    ap.add_argument("--issue", action="store_true", help="open/update the GitHub issue")
    a = ap.parse_args()
    d = build()
    text = render(d)
    if a.write:
        path = os.path.join(ROOT, "docs/PROGRESS.md")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"wrote {path}")
        subs_path = os.path.join(ROOT, "docs/subs.json")
        with open(subs_path, "w", encoding="utf-8") as fh:
            json.dump({r["slug"]: r["subs"] for r in d["rows"]}, fh, indent=2)
    if a.issue:
        upsert_issue(text)
    if not a.write:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
