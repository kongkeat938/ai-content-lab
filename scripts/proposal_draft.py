#!/usr/bin/env python3
"""Turn a public request into a ready-to-send message — and stop there.

    python3 scripts/proposal_draft.py --top 10
    python3 scripts/proposal_draft.py --report

Each draft quotes the buyer's own headline, picks the package that fits their
budget, and names the sample that matches the brief. Everything it says about
us is checkable (price from content/packages.json, samples we made ourselves).

Nothing here sends anything: there is no mail, no POST, no browser. A draft is a
file a human reads and sends, and `status` starts at "draft" and only changes
when a human says so.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROSPECTS = os.environ.get("PROSPECT_STORE") or os.path.join(ROOT, "content", "prospects_external.json")
OUTDIR = os.environ.get("PROPOSAL_DIR") or os.path.join(ROOT, "content", "proposals")
PORTFOLIO = "https://kongkeat938.github.io/ai-content-lab/portfolio/"
USD_THB = 35.0

FIT = ("9:16", "vertical", "short", "reel", "tiktok", "reels", "shorts", "30 second", "60 second",
       "15 second", "20 second", "instagram", "youtube short")
VOLUME = ("per week", "weekly", "monthly", "batch", "series", "multiple", "ongoing", "daily")
THAI = re.compile(r"[\u0e00-\u0e7f]")
# We cut clips out of footage a client already owns. Work that needs animation,
# avatars, 3D or a whole production pipeline is not ours to promise.
NOT_OURS = ("animat", "avatar", "3d ", "motion graphic", "explainer", "whiteboard", "vfx",
            "website", "app development", "logo design", "voice over artist", "ai film",
            "ai video generator", "ai animation", "game", "seo", "backlink")


def load(path: str, default):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def budget_thb(text: str) -> float | None:
    if not text:
        return None
    m = re.search(r"([$฿€£])\s?([\d,]+(?:\.\d+)?)", text)
    if m:
        val = float(m.group(2).replace(",", ""))
        return val if m.group(1) == "฿" else val * USD_THB
    m = re.search(r"([\d,]+(?:\.\d+)?)\s?(thb|usd)", text, re.I)
    if m:
        val = float(m.group(1).replace(",", ""))
        return val if m.group(2).lower() == "thb" else val * USD_THB
    return None


def fits_service(item: dict) -> tuple[bool, str]:
    blob = f"{item.get('title','')} {item.get('text','')}".lower()
    bad = [t for t in NOT_OURS if t in blob]
    if bad:
        return False, f"not our service: {bad[0]}"
    good = [t for t in ("edit", "cut", "clip", "reel", "short", "tiktok", "youtube") if t in blob]
    if not good:
        return False, "no editing vocabulary"
    return True, ""


def score(item: dict) -> tuple[int, list[str]]:
    """0-100. Every component is visible in `why` so a ranking can be argued with."""
    why, s = [], 0
    blob = f"{item.get('title','')} {item.get('text','')}".lower()
    b = budget_thb(item.get("budget_text", ""))
    if b is None:
        why.append("no budget stated (+0)")
    elif b >= 1000:
        s += 30; why.append(f"budget ≈{b:.0f} THB (+30)")
    elif b >= 500:
        s += 22; why.append(f"budget ≈{b:.0f} THB (+22)")
    elif b >= 250:
        s += 14; why.append(f"budget ≈{b:.0f} THB (+14)")
    else:
        s += 6; why.append(f"budget ≈{b:.0f} THB — below pack A (+6)")
    if any(t in blob for t in FIT):
        s += 25; why.append("brief names a short-form format (+25)")
    if any(t in blob for t in VOLUME):
        s += 15; why.append("repeat/batch work mentioned (+15)")
    if "verified" in (item.get("contact_public") or "").lower():
        s += 10; why.append("payment method verified by the platform (+10)")
    days = re.search(r"(\d+)\s+days?\s+left", item.get("deadline_text", ""))
    if days and int(days.group(1)) >= 3:
        s += 10; why.append(f"{days.group(1)} days left (+10)")
    return min(s, 100), why


def pick_package(b: float | None, packages: list[dict]) -> dict:
    """The pack that fits the stated budget without discounting below pack A."""
    primary = next(p for p in packages if p.get("primary"))
    if b is None:
        return primary
    for p in sorted(packages, key=lambda p: p["price"]):
        if p["price"] <= b:
            best = p
    return locals().get("best", packages[0])


def sample_for(item: dict) -> str:
    blob = f"{item.get('title','')} {item.get('text','')}".lower()
    if any(t in blob for t in ("product", "shop", "sale", "promo", "advert", "launch")):
        return "sample_product_45s.mp4 — a 45s product-sales cut (self-produced)"
    if any(t in blob for t in ("image", "photo", "still", "slideshow", "narration")):
        return "sample_still_30s.mp4 — stills + Thai narration + captions (self-produced)"
    return "sample_promo_20s.mp4 — a 20s vertical promo (self-produced)"


def draft_text(item: dict, pkg: dict, packs: dict, samples: list[str]) -> str:
    thai = bool(THAI.search(f"{item.get('title','')} {item.get('text','')}"))
    headline = item["title"].strip()
    budget = item.get("budget_text") or "not stated"
    if thai:
        return (
            f"สวัสดีครับ เห็นประกาศ “{headline}” (งบที่แจ้ง: {budget})\n\n"
            f"ผมรับตัดคลิปแนวตั้ง 9:16 ความยาว 30–60 วินาที จากไฟล์ต้นฉบับของคุณ — "
            f"{packs['scope_th']}\n\n"
            f"ราคา: แพ็ก {pkg['id']} — {pkg['clips']} คลิป {pkg['price']} บาท "
            f"(แก้ไขได้ {packs['revisions']} ครั้ง/คลิป) · งานด่วนกว่า 5 คลิปใช้แพ็ก B\n"
            f"ระยะเวลา: {packs['turnaround']}\n"
            f"ตัวอย่างงาน (ผลิตเองทั้งหมด ไม่ใช่งานลูกค้ารายใด): {PORTFOLIO}\n"
            f"  - {samples[0]}\n\n"
            f"ถ้าสนใจ ส่งลิงก์ไฟล์ต้นฉบับ + ตัวอย่างคลิปที่ชอบมาได้เลยครับ "
            f"ผมจะส่งคลิปแรกให้ดูก่อนตัดสินใจ\n"
        )
    return (
        f"Hi — I saw your post “{headline}” (budget listed: {budget}).\n\n"
        f"What I deliver: vertical 9:16 clips, 30-60s, {packs['scope_en_short']}, "
        f"{packs['revisions']} revision rounds per clip.\n\n"
        f"Pack {pkg['id']}: {pkg['clips']} clips — {pkg['price']} THB.\n"
        f"Turnaround: {packs.get('turnaround_en', '')}\n"
        f"Samples (all produced by me to show the craft — not client work): {PORTFOLIO}\n"
        f"  - {samples[0]}\n\n"
        f"If it fits, send the source footage and one clip you like; I will cut the first "
        f"clip for you to judge before you commit.\n"
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    packs = load(os.path.join(ROOT, "content", "packages.json"), {})
    index_path = os.path.join(OUTDIR, "index.json")
    index = load(index_path, {"drafts": []})

    if a.report:
        drafts = index["drafts"]
        print(f"drafts stored : {len(drafts)}")
        print(f"status        : " + ", ".join(
            f"{k}={sum(1 for d in drafts if d['status'] == k)}"
            for k in sorted({d["status"] for d in drafts})) if drafts else "status        : -")
        print(f"sent by agent : 0  (this program has no send path)")
        return 0

    db = load(PROSPECTS, {"items": []})
    open_items = []
    for i in db.get("items", []):
        if i.get("status") != "open":
            continue
        ok, why_not = fits_service(i)
        if ok:
            open_items.append(i)
        else:
            index.setdefault("skipped", []).append(
                {"prospect_id": i["id"], "url": i["url"], "reason": why_not})
    scored = sorted(((score(i), i) for i in open_items), key=lambda t: -t[0][0])
    done = {d["prospect_id"] for d in index["drafts"]}
    made = 0
    os.makedirs(OUTDIR, exist_ok=True)
    for (sc, why), item in scored:
        if made >= a.top:
            break
        if item["id"] in done:
            continue
        pkg = pick_package(budget_thb(item.get("budget_text", "")), packs["packages"])
        samples = [sample_for(item)]
        body = draft_text(item, pkg, packs, samples)
        path = os.path.join(OUTDIR, f"{item['id']}.md")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(f"<!-- prospect: {item['url']} | source: {item['source']} | "
                     f"score {sc}/100 | status: draft -->\n\n{body}")
        index["drafts"].append({
            "prospect_id": item["id"], "prospect_url": item["url"], "source": item["source"],
            "title": item["title"][:160], "score": sc, "why": why, "package": pkg["id"],
            "price": pkg["price"], "sample": samples[0], "status": "draft",
            "file": os.path.relpath(path, ROOT), "sent_at": None,
        })
        made += 1
        print(f"{sc:>3}/100  pack {pkg['id']}  {item['title'][:60]}")
    index["updated_at"] = __import__("time").strftime("%Y-%m-%dT%H:%M:%SZ", __import__("time").gmtime())
    with open(index_path, "w", encoding="utf-8") as fh:
        json.dump(index, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")
    print(f"\n{made} new draft(s); total {len(index['drafts'])}; nothing was sent")
    return 0


if __name__ == "__main__":
    sys.exit(main())
